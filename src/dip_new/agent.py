"""
DipNewAgent -- the nodes of the dip_new sub-graph.

    fill_slots    UI filters (request or chat_sessions) -> source; newest data time;
                  LLM fills the tool arguments from the question (schema-forced JSON)
    apply_scope   merge: UI network / circle / tier are hard limits, question time wins
    calculate_dip build the dip SQL (Dip_Tool engine) and run it through MCP
    summarize_dip short answer + the warnings (what was applied, what was ignored)
"""
import orjson

from managers.models.llm import LLMManager
from utils.logs import FileLogger
from utils.prompts import summarize_prompt, fallback_summarize
from config.llm import SUMMARY_MODEL
from db.pattern import DBFactory

from src.dip_new.config import DIP_LOAD_SESSION_FILTERS, DIP_SLOT_MODEL
from src.dip_new.runner import DipRunner, to_dt
from src.dip_new.scope import merge_scope, parse_ui_filters, resolve_source
from src.dip_new.slots import (SLOT_SCHEMA, clean_slots, fallback_slots,
                               parse_json, slot_prompt)


class DipNewAgent:
    def __init__(self, req_id: str, sess_id: str, usr_id: str, db_name: str):
        self.request_id = req_id
        self.session_id = sess_id
        self.user_id = usr_id
        self.db_manager = DBFactory().get(db_name=db_name).get_db_manager()
        self.runner = DipRunner(self.db_manager, req_id, db_name)
        self.llm_manager = LLMManager()
        self.log = FileLogger().get_logger()

    # ------------------------------------------------------------------
    async def _session_filters(self, session_id) -> dict:
        """Session filters saved by the UI in ai_db.chat_sessions (when /ask sends none)."""
        if not DIP_LOAD_SESSION_FILTERS or not str(session_id or "").isdigit():
            return {}
        try:
            from managers.user_session_db.engine import UserSessionsManager
            res = await UserSessionsManager().aget(
                "SELECT networks, levels, circle, services, date_from, date_to, "
                f"time_start, time_end FROM chat_sessions WHERE id = {int(session_id)} LIMIT 1;")
            rows = res.get("rows") or []
            return dict(rows[0]) if rows else {}
        except Exception as e:
            self.log.error(f"dip_new :: session filters not loaded :: {e}")
            return {}

    # ------------------------------------------------------------------
    async def fill_slots(self, state: dict) -> dict:
        self.log.debug(f"\ndip_new :: fill_slots :: state :: {state}")
        warnings = list(state.get("warnings") or [])

        raw = state.get("ui_filters") or await self._session_filters(state.get("session_id"))
        ui, w = parse_ui_filters(raw)
        warnings += w
        source, w, err = resolve_source(ui)
        warnings += w
        if err:
            return {"ui": ui, "warnings": warnings, "error": err}

        try:
            latest = await self.runner.latest_time(self.runner.source(source))
        except Exception as e:
            return {"ui": ui, "source": source, "warnings": warnings,
                    "sql_query": self.runner.last_sql,
                    "error": f"Could not read the newest traffic time: {e}"}

        text = None
        try:
            text = await self.llm_manager.call(
                prompt=slot_prompt(state["question"], latest),
                model=DIP_SLOT_MODEL,
                format=SLOT_SCHEMA,
                options={"temperature": 0},
            )
        except Exception as e:
            self.log.error(f"dip_new :: slot LLM failed :: {e}")
        obj = parse_json(text)
        if obj is None:
            slots = fallback_slots(state["question"])
            warnings.append("Could not read the details of the question; used the defaults "
                            "(change of at least 20%) with the session filters.")
        else:
            slots, w = clean_slots(obj, latest)
            warnings += w
        self.log.debug(f"dip_new :: slots :: raw {text} :: clean {slots}")
        return {"ui": ui, "source": source, "latest": str(latest), "slots": slots,
                "llm_raw": text or "", "warnings": warnings}

    # ------------------------------------------------------------------
    async def apply_scope(self, state: dict) -> dict:
        if state.get("error"):
            return {}
        args, w, scope_used = merge_scope(state.get("ui") or {}, state.get("slots") or {},
                                          to_dt(state["latest"]))
        args["source"] = state["source"]
        return {"dip_args": args, "scope_used": scope_used,
                "warnings": list(state.get("warnings") or []) + w}

    # ------------------------------------------------------------------
    async def calculate_dip(self, state: dict) -> dict:
        self.log.debug(f"\ndip_new :: calculate_dip :: args :: {state.get('dip_args')}")
        empty = {"results": [], "columns": [], "row_count": 0, "intent": "dip"}
        if state.get("error"):
            return {**empty, "sql_valid": False}
        try:
            res = await self.runner.find(state["dip_args"], latest=state.get("latest"))
        except Exception as e:
            return {**empty, "sql_query": self.runner.last_sql, "sql_valid": False,
                    "sql_issues": str(e), "error": f"{type(e).__name__}: {e}"}

        params_used = {
            "source": res["source"], "table": res["table"], "direction": res["direction"],
            "threshold": res["threshold"], "window": res["window"], "level": res["level"],
            "metric": res["metric"], "unit": res["unit"], "limit": res["limit"],
            "filters": res["filters"], "summary": res["summary"], "method": res["method"],
            "latest_data_time": state.get("latest"), "scope": state.get("scope_used"),
            "from_question": state.get("slots"), "ms": res["ms"],
        }
        out = {"sql_query": res["sql"], "sql_valid": True, "sql_issues": "", "error": "",
               "results": res["rows"], "columns": res["columns"], "row_count": res["count"],
               "params_used": params_used, "intent": "dip",
               "chart_intent": "trend" if res.get("series") else "ranking",
               "warnings": list(state.get("warnings") or []) + res["notes"]}
        if res.get("series"):
            out["formatted_data_for_visualization"] = res["series"]
        return out

    # ------------------------------------------------------------------
    async def summarize(self, state: dict) -> dict:
        notes = list(dict.fromkeys(state.get("warnings") or []))
        tail = "".join(f"\nNote: {n}" for n in notes)
        pu = state.get("params_used") or {}
        if state.get("error"):
            return {"summary": f"{state['error']}{tail}", "warnings": notes}
        if not state.get("results"):
            what = "surges" if pu.get("direction") == "surge" else "dips"
            return {"summary": f"No {what} found ({pu.get('summary', '')}).{tail}",
                    "warnings": notes}
        if not state.get("summarize"):
            return {"summary": f"{state.get('row_count', 0)} result(s): {pu.get('summary', '')}{tail}",
                    "warnings": notes}
        try:
            prompt = summarize_prompt().invoke({
                "question": f"{state['question']}\n(Applied: {pu.get('summary', '')})",
                "cols": state.get("columns") or "",
                "preview": orjson.dumps(state["results"][:40], default=str).decode("utf-8"),
            }).to_string()
            summary = await self.llm_manager.call(prompt=prompt, model=SUMMARY_MODEL,
                                                  temperature=0.2)
            summary = summary or fallback_summarize(state)
        except Exception as e:
            self.log.error(f"dip_new :: summary LLM failed :: {e}")
            summary = fallback_summarize(state)
        return {"summary": f"{summary}{tail}", "warnings": notes}
