"""
CustomerReportAgent -- the nodes of the customer_report sub-graph.

    fill_slots    UI filters (request or chat_sessions); data range of the traffic table;
                  LLM fills the report arguments from the question (schema-forced JSON)
    apply_scope   UI network / circle / tier are hard limits; question time wins over the
                  session window; default = the newest data day
    run_report    build the report SQL (engine.py) and run it through MCP
    summarize     short answer + the rules used + warnings
"""
import time
from datetime import datetime, timedelta

import orjson

from managers.models.llm import LLMManager
from utils.logs import FileLogger
from utils.prompts import summarize_prompt, fallback_summarize
from config.llm import SUMMARY_MODEL
from db.pattern import DBFactory

from src.customer_report.config import CR_LOAD_SESSION_FILTERS, CR_SLOT_MODEL, CR_TABLES
from src.customer_report.engine import build_report_sql, describe, rules_text
from src.customer_report.slots import (SLOT_SCHEMA, clean_slots, fallback_slots,
                                       parse_json, slot_prompt)
from src.dip_new.runner import root_cause, to_dt
from src.dip_new.scope import circle_code, norm_key, parse_ui_filters, tier_code, ui_window
from src.dip_new.tool.render import render


def _s(v):
    return v.strftime("%Y-%m-%d %H:%M:%S") if isinstance(v, datetime) else v


class CustomerReportAgent:
    def __init__(self, req_id: str, sess_id: str, usr_id: str, db_name: str):
        self.request_id = req_id
        self.session_id = sess_id
        self.user_id = usr_id
        self.data_source = db_name
        self.tables = CR_TABLES.get(db_name)
        self.db_manager = DBFactory().get(db_name=db_name).get_db_manager()
        self.llm_manager = LLMManager()
        self.log = FileLogger().get_logger()
        self.last_sql = ""

    # ------------------------------------------------------------------
    async def _run(self, sql):
        self.last_sql = sql
        try:
            return await self.db_manager._execute_query(uuid=self.request_id, query=sql)
        except Exception as e:
            raise RuntimeError(root_cause(e)) from e

    async def _data_range(self):
        res = await self._run(f"SELECT MIN(Time_1) AS first_time, MAX(Time_1) AS latest_time "
                              f"FROM {self.tables['traffic']}")
        row = (res.get("data") or [{}])[0]
        latest = to_dt(row.get("latest_time"))
        if latest is None:
            raise RuntimeError(f"{self.tables['traffic']} has no rows")
        return to_dt(row.get("first_time")), latest

    async def _session_filters(self, session_id) -> dict:
        if not CR_LOAD_SESSION_FILTERS or not str(session_id or "").isdigit():
            return {}
        try:
            from managers.user_session_db.engine import UserSessionsManager
            res = await UserSessionsManager().aget(
                "SELECT networks, levels, circle, services, date_from, date_to, "
                f"time_start, time_end FROM chat_sessions WHERE id = {int(session_id)} LIMIT 1;")
            rows = res.get("rows") or []
            return dict(rows[0]) if rows else {}
        except Exception as e:
            self.log.error(f"customer_report :: session filters not loaded :: {e}")
            return {}

    # ------------------------------------------------------------------
    async def fill_slots(self, state: dict) -> dict:
        self.log.debug(f"\ncustomer_report :: fill_slots :: state :: {state}")
        warnings = list(state.get("warnings") or [])
        if not self.tables:
            return {"warnings": warnings,
                    "error": f"The customer report is not set up for data source "
                             f"'{self.data_source}' (CR_TABLES in src/customer_report/config.py)."}

        raw = state.get("ui_filters") or await self._session_filters(state.get("session_id"))
        ui, w = parse_ui_filters(raw)
        warnings += w

        try:
            first, latest = await self._data_range()
        except Exception as e:
            return {"ui": ui, "warnings": warnings, "sql_query": self.last_sql,
                    "error": f"Could not read the traffic data range: {e}"}

        text = None
        try:
            text = await self.llm_manager.call(
                prompt=slot_prompt(state["question"], first, latest),
                model=CR_SLOT_MODEL, format=SLOT_SCHEMA, options={"temperature": 0})
        except Exception as e:
            self.log.error(f"customer_report :: slot LLM failed :: {e}")
        obj = parse_json(text)
        if obj is None:
            slots = fallback_slots(state["question"])
            warnings.append("Could not read all the details of the question; used keywords only.")
        else:
            slots, w = clean_slots(obj, latest)
            warnings += w
        self.log.debug(f"customer_report :: slots :: raw {text} :: clean {slots}")
        return {"ui": ui, "first": _s(first), "latest": _s(latest), "slots": slots,
                "llm_raw": text or "", "warnings": warnings}

    # ------------------------------------------------------------------
    async def apply_scope(self, state: dict) -> dict:
        if state.get("error"):
            return {}
        ui, slots = state.get("ui") or {}, dict(state.get("slots") or {})
        first, latest = to_dt(state.get("first")), to_dt(state["latest"])
        warnings = list(state.get("warnings") or [])
        args = {k: v for k, v in slots.items() if k != "time"}

        # network: customer VPN reports are MPLS only
        nets = ui.get("networks") or []
        if nets and not any(norm_key(n) == "mpls" for n in nets):
            return {"warnings": warnings,
                    "error": f"The customer report covers MPLS VPN customers only; "
                             f"this session is set to {', '.join(nets)}."}
        if nets and any(norm_key(n) != "mpls" for n in nets):
            warnings.append("The customer report covers MPLS only; other networks were ignored.")

        # circle / tier (UI hard limits; through the inventory table)
        circles = list(dict.fromkeys(circle_code(c)[0] for c in ui.get("circles") or []))
        tiers = list(dict.fromkeys(t for t in (tier_code(x) for x in ui.get("levels") or []) if t))
        if (circles or tiers) and not self.tables.get("inventory"):
            warnings.append("Circle / tier filters are not available for this data source; ignored.")
            circles, tiers = [], []
        args["circles"], args["tiers"] = circles, tiers
        if ui.get("services"):
            warnings.append(f"The services filter ({', '.join(ui['services'])}) is not applied "
                            f"to customer reports yet.")

        # time: question > session window > newest data day
        try:
            session_win = ui_window(ui, latest)
        except ValueError as e:
            session_win = None
            warnings.append(f"Session time window ignored: {e}.")
        q_time = slots.get("time")
        if q_time:
            start, end = to_dt(q_time["start"]), to_dt(q_time["end"])
            if session_win:
                warnings.append(f"Used the time in the question instead of the session window "
                                f"({session_win[0]} to {session_win[1]}).")
            src = "question"
        elif session_win:
            start, end = session_win
            src = "session"
        else:
            start = datetime.combine(latest.date(), datetime.min.time())
            end = latest + timedelta(seconds=1)
            src = "default"
        if start > latest:
            warnings.append(f"No traffic data after {latest}; the period asked for starts at {start}.")
        elif first and start < first:
            warnings.append(f"Traffic data only starts at {first}; the report covers {first} onwards.")
        if end <= start:
            return {"warnings": warnings, "error": f"The end time {end} is not after the start {start}."}
        args["start"], args["end"] = start, end

        if args.get("report") == "hourly":
            if args.get("only") or args.get("util"):
                warnings.append("The hourly view lists traffic only; the upgrade / breach / "
                                "utilization condition was not applied.")
                args.pop("only", None)
                args.pop("util", None)
            if not (args.get("filters") or circles or tiers):
                warnings.append("Hourly traffic for every customer circuit is long; showing the "
                                "first rows. Name a customer, LSI or circuit to narrow it.")

        scope_used = {"networks": nets, "circles": circles, "tiers": tiers,
                      "services_not_applied": ui.get("services") or [],
                      "session_window": [_s(session_win[0]), _s(session_win[1])] if session_win else None,
                      "time_from": src}
        return {"cr_args": args, "scope_used": scope_used, "warnings": warnings}

    # ------------------------------------------------------------------
    async def run_report(self, state: dict) -> dict:
        args = state.get("cr_args")
        self.log.debug(f"\ncustomer_report :: run_report :: args :: {args}")
        empty = {"results": [], "columns": [], "row_count": 0, "intent": "customer_report"}
        if state.get("error"):
            return {**empty, "sql_valid": False}
        t0 = time.time()
        try:
            sql, params, meta = build_report_sql(args, self.tables)
            sql = render(sql, params)
            res = await self._run(sql)
        except Exception as e:
            return {**empty, "sql_query": self.last_sql, "sql_valid": False,
                    "sql_issues": str(e), "error": f"{type(e).__name__}: {e}"}

        rows = res.get("data") or []
        cols = res.get("columns") or (list(rows[0].keys()) if rows else [])
        total = rows[0].get("Total Matches") if rows and "Total Matches" in rows[0] else len(rows)
        summary_line = describe(args)
        params_used = {
            "report": meta["report"], "summary": summary_line, "rules": rules_text(args),
            "window": [_s(args["start"]), _s(args["end"])], "only": args.get("only"),
            "util": args.get("util"), "filters": args.get("filters") or {},
            "nld": args.get("nld") or "include", "sort_by": args.get("sort_by"),
            "limit": meta.get("limit"), "total_matches": total,
            "data_range": [state.get("first"), state.get("latest")],
            "latest_data_time": state.get("latest"), "scope": state.get("scope_used"),
            "from_question": {k: (_s(v) if not isinstance(v, dict) else
                                  {kk: _s(vv) for kk, vv in v.items()})
                              for k, v in (state.get("slots") or {}).items()},
            "tables": self.tables, "ms": int((time.time() - t0) * 1000),
        }
        return {"sql_query": sql, "sql_valid": True, "sql_issues": "", "error": "",
                "results": rows, "columns": cols, "row_count": len(rows),
                "params_used": params_used, "intent": "customer_report",
                "chart_intent": "trend" if meta["report"] == "hourly" else "ranking",
                "warnings": list(state.get("warnings") or [])}

    # ------------------------------------------------------------------
    async def summarize(self, state: dict) -> dict:
        notes = list(dict.fromkeys(state.get("warnings") or []))
        pu = state.get("params_used") or {}
        if pu:
            notes.append(f"Rules: {pu.get('rules')}. Data available {pu['data_range'][0]} "
                         f"to {pu['data_range'][1]}.")
        tail = "".join(f"\nNote: {n}" for n in notes)
        if state.get("error"):
            return {"summary": f"{state['error']}{tail}", "warnings": notes}
        n, total = state.get("row_count", 0), pu.get("total_matches")
        shown = (f"{n} of {total}" if isinstance(total, int) and total > n else f"{n}")
        if not state.get("results"):
            return {"summary": f"Nothing found: {pu.get('summary', '')}.{tail}", "warnings": notes}
        if not state.get("summarize"):
            return {"summary": f"{shown} row(s): {pu.get('summary', '')}.{tail}", "warnings": notes}
        try:
            prompt = summarize_prompt().invoke({
                "question": (f"{state['question']}\n(Applied: {pu.get('summary', '')}; "
                             f"showing {shown} rows; {pu.get('rules')})"),
                "cols": state.get("columns") or "",
                "preview": orjson.dumps(state["results"][:40], default=str).decode("utf-8"),
            }).to_string()
            summary = await self.llm_manager.call(prompt=prompt, model=SUMMARY_MODEL, temperature=0.2)
            summary = summary or fallback_summarize(state)
        except Exception as e:
            self.log.error(f"customer_report :: summary LLM failed :: {e}")
            summary = fallback_summarize(state)
        return {"summary": f"{summary}{tail}", "warnings": notes}
