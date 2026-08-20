import re
import orjson
import asyncio

from langchain.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage

from managers.database.db import DatabaseManager
from managers.models.llm import LLMManager
from utils.logs import FileLogger
from config.dip import DIP_HIGH_UTIL, DIP_MIN_DROP
from config.traffic import TRAFFIC_TABLE_NAME
from config.llm import SUMMARY_MODEL
from utils.prompts import summarize_prompt, fallback_summarize


class DipAgent:
    def __init__(self, rid: str, sid: str, uid: str):
        self.db_manager = DatabaseManager()
        self.llm_manager = LLMManager()
        self.log = FileLogger().get_logger()
        self.request_id = rid
        self.session_id = sid
        self.user_id = uid

    def _get_dip_sql_query(self, window_hours, linktype_filter, util_filter,
                           min_drop, max_drop_filter, limit):
        return f'''WITH data_end AS (SELECT MAX("Time") AS t FROM {TRAFFIC_TABLE_NAME}),
            windowed AS (
                SELECT NodeName, InterfaceName, LinkType, BWKb, "Time",
                    InTrafficKbps, OutTrafficKbps
                FROM {TRAFFIC_TABLE_NAME}, data_end
                WHERE "Time" >= data_end.t - INTERVAL '{window_hours} hours'
                {linktype_filter}
            ),
            ranked AS (
                SELECT *, ROW_NUMBER() OVER (
                    PARTITION BY NodeName, InterfaceName ORDER BY "Time" DESC
                ) AS rn
                FROM windowed
            ),
            current AS (SELECT * FROM ranked WHERE rn = 1),
            baseline AS (
                SELECT NodeName, InterfaceName,
                    AVG(GREATEST(InTrafficKbps, OutTrafficKbps)) AS baseline_val
                FROM ranked WHERE rn > 1
                GROUP BY NodeName, InterfaceName
            )
            SELECT
                c.NodeName AS "Node Name",
                c.InterfaceName AS "Interface Name",
                c.LinkType AS "LinkType",
                c."Time" AS "Latest Time",
                ROUND(GREATEST(c.InTrafficKbps, c.OutTrafficKbps), 2) AS "Current (Kbps)",
                ROUND(b.baseline_val, 2) AS "Baseline (Kbps)",
                ROUND((b.baseline_val - GREATEST(c.InTrafficKbps, c.OutTrafficKbps))
                    / NULLIF(b.baseline_val, 0) * 100, 2) AS "Dip %",
                ROUND(GREATEST(c.InTrafficKbps, c.OutTrafficKbps)
                    / NULLIF(c.BWKb, 0) * 100, 2) AS "Current Utilization %"
            FROM current c
            JOIN baseline b
            ON b.NodeName = c.NodeName AND b.InterfaceName = c.InterfaceName
            WHERE b.baseline_val > 0
            AND (b.baseline_val - GREATEST(c.InTrafficKbps, c.OutTrafficKbps))
                / NULLIF(b.baseline_val, 0) * 100 >= {min_drop}
            {max_drop_filter}
            {util_filter}
            ORDER BY "Dip %" DESC
            LIMIT {limit}'''

    async def _get_link_types(self) -> list:
        """ Returns list of valid link types """
        query = f'SELECT DISTINCT "LinkType" FROM {TRAFFIC_TABLE_NAME}'
        result = await self.db_manager._execute_query(uuid=self.request_id, query=query)
        return [r[0] for r in result["rows"] if r[0]]

    def _extract_limit(self, default=10):
        m = re.search(r'\b(?:limit|top)\s*(\d+)\b', self.qn_low)
        return int(m.group(1)) if m else default

    async def _extract_linktype(self):
        if "all linktype" in self.qn_low or "across all" in self.qn_low:
            return None
        
        valid_linktypes = await self._get_link_types()
        for lt in valid_linktypes:
            if lt and lt.lower() in self.qn_low:
                return lt
        return None

    def _extract_pct(self, keyword_pattern, default):
        """Pull an explicit percentage threshold out of the question, e.g.
        'dip of at least 30%' -> 30.0, 'utilization above 90' -> 90.0.
        Falls back to `default` if the question doesn't specify one."""
        m = re.search(rf'{keyword_pattern}\D{{0,15}}?(\d+(?:\.\d+)?)\s*%?', self.qn_low)
        return float(m.group(1)) if m else default

    def _extract_dip_range(self):
        """Parse the dip threshold as a (floor, ceiling) range:
          'between 20 and 50%'  -> (20.0, 50.0)
          'less than 50%'       -> (DIP_MIN_DROP, 50.0)   # below/under/at most/up to/no more than
          'at least 30%'        -> (30.0, None)           # more than/above/over/>=
          bare 'dip of 40%'     -> (40.0, None)
        Order matters: check 'between' and ceiling phrasings BEFORE the permissive
        floor branch, otherwise 'less than 50' would be read as a >= 50 floor."""
        ql = self.qn_low
        trig = r'(?:dip|drop|fell|fall)\w*'
        m = re.search(
            rf'{trig}\D{{0,15}}?between\s*(\d+(?:\.\d+)?)\s*%?\s*(?:and|to|-)\s*(\d+(?:\.\d+)?)',
            ql
        )
        if m:
            lo, hi = float(m.group(1)), float(m.group(2))
            return (min(lo, hi), max(lo, hi))
        m = re.search(
            rf'{trig}\D{{0,20}}?(?:less than|below|under|at most|up to|no more than|<=|<)\s*(\d+(?:\.\d+)?)',
            ql
        )
        if m:
            return (float(DIP_MIN_DROP), float(m.group(1)))
        m = re.search(
            rf'{trig}\D{{0,20}}?(?:at least|more than|above|over|greater than|>=|>)?\s*(\d+(?:\.\d+)?)',
            ql
        )
        if m:
            return (float(m.group(1)), None)
        return (float(DIP_MIN_DROP), None)
    
    def _extract_window_hours(self, default=1):
        """Pull a time window out of the question. Defaults to last 1 hour of
        the interface's OWN history (per handoff doc Section 3 default),
        measured from the dataset's own latest timestamp, not wall-clock now()."""
        ql = self.qn_low
        m = re.search(r'last\s*(\d+)\s*hour', ql)
        if m: 
            return int(m.group(1))
        m = re.search(r'last\s*(\d+)\s*day', ql)
        if m: 
            return int(m.group(1)) * 24
        if 'today' in ql: 
            return 24
        if 'this week' in ql: 
            return 24 * 7
        return default    

    async def summarize(self, state: dict) -> dict:
        """Provide additional summary"""
        
        self.log.debug(f"\ndip_agent :: summarize :: state :: {state}")
        if state["summarize"]:
            try:
                summary_prompt = summarize_prompt(state)
                if summary_prompt:
                    summary = await self.llm_manager.call(
                        prompt=summary_prompt,
                        model=SUMMARY_MODEL,
                        temperature=0.2
                    )
                else:
                    summary = fallback_summarize(state)
                return {
                    "messages": [
                        SystemMessage(content=summary_prompt),
                        AIMessage(content=summary)
                    ],
                    "summary": summary
                    }
            except Exception as e:
                summary = fallback_summarize(state)
                _error = f"LLM summary unavailable. Issue encountered : {e}"
            return {
                "messages": AIMessage(content=summary),
                "summary": summary,
                "error": _error
                }
        return {}


    async def dip_detect(self, state: dict):
        """Find interfaces whose latest sample dropped sharply vs their own recent
        baseline (baseline = avg of earlier samples within the window, excluding
        the latest sample itself). If the question also mentions utilization/high,
        additionally require the CURRENT sample to be at/above the utilization
        threshold -- this answers "dip before high utilization" style questions:
        recently dipped AND currently running hot.
        All thresholds (drop %, utilization %, window hours) can be overridden by
        the question text; effective values used are returned in `params_used`
        so the caller/frontend can show exactly what filter was applied.
        Returns (sql, cols, rows, ms, params_used)."""
        self.log.debug(f"\ndip_agent :: dip_detect :: state :: {state}")
        self.question = state['question']
        self.qn_low = self.question.lower()

        ### Parameters calculation ###
        limit = self._extract_limit()
        linktype_coro = asyncio.create_task(self._extract_linktype())
        window_hours = self._extract_window_hours()

        want_high_util = any(w in self.qn_low for w in ("util", "congest", "high", "capacity"))
        min_drop, max_drop = self._extract_dip_range()
        high_util = self._extract_pct(
            keyword_pattern=r'(?:util(?:ization)?|congest\w*)\s*(?:of|is|at least|above|>=)?', 
            default=DIP_HIGH_UTIL
        ) if want_high_util else None

        linktype = await linktype_coro
        linktype_filter = f'AND "LinkType" = {linktype}' if linktype else ""
        util_filter = (
            f'AND GREATEST(c.InTrafficKbps, c.OutTrafficKbps) '
            f'/ NULLIF(c.BWKb, 0) * 100 >= {high_util}'
        ) if want_high_util else ""
        max_drop_filter = (
            f'AND (b.baseline_val - GREATEST(c.InTrafficKbps, c.OutTrafficKbps)) '
            f'/ NULLIF(b.baseline_val, 0) * 100 <= {max_drop}'
        ) if max_drop is not None else ""

        # Window is measured from the DATASET's own latest sample, not wall-clock
        # now() -- this dataset is historical/fixed, not a live stream.
        sql = self._get_dip_sql_query(window_hours, linktype_filter, util_filter,
                                        min_drop, max_drop_filter, limit)
        try:
            result = await self.db_manager._execute_query(uuid=self.request_id, query=sql)
        except Exception as e:
            return {"sql_query": sql, "sql_valid": False, "sql_issues": str(e), "error": str(e)}

        summary = ""
        if not result["rows"]:
            extra = f" and current utilization >= {high_util:.0f}%" if high_util else ""
            ceiling = f" and at most {max_drop:.0f}%" if max_drop is not None else ""
            summary = (
                f"No interfaces found with a dip of at least {min_drop:.0f}%{ceiling} vs their baseline \
                last {window_hours}h, linktype={linktype or 'ALL'}{extra}.")
            
        return {
            "messages": [
                HumanMessage(content=state["question"]),
                ToolMessage(
                    content=orjson.dumps(result["data"]).decode('utf-8'),
                    tool_call_id=result["tool_id"],
                    name=result["tool_name"],
                ),
                AIMessage(content=summary)
            ],
            "sql_query": sql, 
            "sql_valid": True, 
            "summary" : summary,
            "row_count": result["rowCount"],
            "results": result["data"],
            "columns": result["columns"],
            }