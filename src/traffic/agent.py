import orjson
import asyncio
from datetime import timedelta

from memoize.configuration import MutableCacheConfiguration, DefaultInMemoryCacheConfiguration
from memoize.storage import LocalInMemoryCacheStorage
from memoize.wrapper import memoize
from memoize.key import EncodedMethodNameAndArgsKeyExtractor
from memoize.eviction import LeastRecentlyUpdatedEvictionStrategy

from langgraph.types import Command
from langgraph.runtime import Runtime
from langchain.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.output_parsers import JsonOutputParser

from managers.database.db import DatabaseManager
from managers.models.llm import LLMManager
from utils.logs import FileLogger
from utils.skills import get_business
from utils.context import Context
from utils.clean import clean_sql
from utils.categorize import intent_tag
from utils.store import warmup_done, get_conversation_history
from utils.prompts import (summarize_prompt, fallback_summarize, review_prompt,
sql_repair_prompt, conversation_prompt, sql_generate_prompt)
from config.traffic import TRAFFIC_TABLE_NAME, QA_MAX_REPAIRS, CHART_INTENT_ALIASES
from config.mcp import MCP_DB_TYPE
from config.llm import SQL_MODEL, SUMMARY_MODEL

m_cfg = MutableCacheConfiguration.initialized_with(
    DefaultInMemoryCacheConfiguration()).set_method_timeout(
        timedelta(minutes=5)).set_eviction_strategy(
            LeastRecentlyUpdatedEvictionStrategy(
                capacity=20)).set_key_extractor(
                    EncodedMethodNameAndArgsKeyExtractor(
                        skip_first_arg_as_self=True)).set_storage(
                            LocalInMemoryCacheStorage())


class TrafficAgent:
    def __init__(self, rid: str, sid: str, uid: str):
        self.db_manager = DatabaseManager()
        self.llm_manager = LLMManager()
        self.log = FileLogger().get_logger()
        self.request_id = rid
        self.session_id = sid
        self.user_id = uid


    def repair_sql(self, state: dict) -> dict:
        """Validate and fix SQL"""
        self.log.debug(f"\ntraffic_agent :: repair_sql :: state :: {state}")
        retries = state["repairs_left"]
        ### If retries are left or issues raised in prior run, rerun loop at generate sql func
        try:
            has_sql_faults = state["sql_issues"] if "sql_issues" in state else state["error"]
        except Exception as e:
            has_sql_faults = ""
        if retries and not state["sql_valid"] and has_sql_faults:
            return Command(
                goto="generate_sql",
                update={"repairs_left": retries - 1}
            )
        ### If retries are over or no issues remaining, continue to summarize func
        return Command(
            goto="summarize",
            update={"repairs_left": 0}
        )
    
    @memoize(configuration=m_cfg)
    async def _get_schema(self) -> str:
        """ 
        Returns comma-separated string of concatenated column names and their datatypes 
        """
        query = f"SELECT column_name, data_type FROM information_schema.columns \
        WHERE table_name = '{TRAFFIC_TABLE_NAME}' ORDER BY ordinal_position"
        result = await self.db_manager._execute_query(uuid=self.request_id, query=query)
        return ", ".join(f'"{c}" {t}' for c, t in result["rows"])


    @memoize(configuration=m_cfg)
    async def _get_link_types(self) -> list:
        """ Returns list of valid link types """
        query = f'SELECT DISTINCT "LinkType" FROM {TRAFFIC_TABLE_NAME}'
        result = await self.db_manager._execute_query(uuid=self.request_id, query=query)
        return [r[0] for r in result["rows"] if r[0]]


    @memoize(configuration=m_cfg)
    async def _get_max_min_time(self) -> str:
        """ Returns max and min time if available else n/a """
        query = f'SELECT MIN("Time"), MAX("Time") FROM {TRAFFIC_TABLE_NAME}'
        try:
            result = await self.db_manager._execute_query(uuid=self.request_id, query=query)
            min, max = result["rows"][0]
            return f"{min} -> {max}"
        except Exception as e:
            return "n/a"


    @memoize(configuration=m_cfg)
    async def generate_sql(self, state: dict, runtime: Runtime[Context]) -> dict:
        """Create/Corrects SQL query for provided user question"""
        self.log.debug(f"\ntraffic_agent :: generate_sql :: state :: {state}")
        question = state["question"]

        get_schema_coro = asyncio.create_task(self._get_schema())
        get_business_coro = asyncio.create_task(get_business())
        schema = await get_schema_coro
        business_facts = await get_business_coro

        do_repair = False   #Manages SQL correction
        msgs = []

        if "sql_query" in state and state["sql_query"] and (state["error"] or state["sql_issues"]):
            sql_faults = f'Errors:{state["error"]}\nIssues:{state["sql_issues"]}\n'
            self.log.debug(f"\ntraffic_agent :: generate_sql :: sql_faults :: {sql_faults}")
            do_repair = True

        if do_repair:
            prompt = sql_repair_prompt(
                db_type=MCP_DB_TYPE, business_facts=business_facts,
                schema=schema, question=question,
                bad_sql=state["sql_query"], err=sql_faults
            )
        else:
            get_lts_coro = asyncio.create_task(self._get_link_types())
            get_when_coro = asyncio.create_task(self._get_max_min_time())
            get_conv_hist_coro = asyncio.create_task(get_conversation_history(
                user_id=runtime.context.user_id, params=["question", "answer"]))

            memory = await get_conv_hist_coro
            history = conversation_prompt(prev_conv=memory) if memory else None

            lts = await get_lts_coro
            when = await get_when_coro
            prompt = sql_generate_prompt(
                db_type=MCP_DB_TYPE, business_facts=business_facts,
                table_name=TRAFFIC_TABLE_NAME, schema=schema,
                lts=lts, when=when, question=question,
                prev_convo=history
            )

        try:
            self.log.debug(f"\ntraffic_agent :: generate_sql :: do_repair :: {do_repair} :: prompt :: {prompt}")
            print(f"\ntraffic_agent :: generate_sql :: do_repair :: {do_repair} :: prompt")
            query = await self.llm_manager.call(prompt=prompt, model=SQL_MODEL,
                                                temperature=0.0)
            if not query:   # Output generation FAILED
                return {"sql_query": "", "sql_valid": False,
                        "sql_issues": "Query creation failed",
                        "error": "Query creation failed"}

            sql_response = clean_sql(query)
            msgs = [SystemMessage(content=prompt), AIMessage(sql_response)]
            if sql_response.strip() == "NOT_ENOUGH_INFO":
                # return {"messages": msgs, "sql_query": "NOT_RELEVANT"}
                return {"sql_query": "NOT_RELEVANT"}
            else:
                # return {"messages": msgs, "sql_query": sql_response, "sql_valid": True, "sql_issues": "", "error": ""}
                return {"sql_query": sql_response, "sql_valid": True, "sql_issues": "", "error": ""}
        except Exception as e:
            _error = str(e)
            # return {"messages": msgs , "sql_query": "", "sql_valid": False, "sql_issues": "", "error": _error}
            return {"sql_query": "", "sql_valid": False, "sql_issues": "", "error": _error}


    async def review(self, state: dict):
        """Review SQL against original question"""
        self.log.debug(f"\ntraffic_agent :: review :: state :: {state}")
        output_parser = JsonOutputParser()
        try:
            _review_prompt = review_prompt(state)
            result = await self.llm_manager.call(
                prompt=_review_prompt,
                model=SQL_MODEL,
                temperature=0.0
            )
            comments = output_parser.parse(result)
            return {
                # "messages": [
                #     SystemMessage(content=review_prompt),
                #     AIMessage(content=orjson.dumps(comments).decode('utf-8'))
                #     ],
                "review": comments 
                }
        except Exception as e:
            # return {"ok": True, "notes": "review skipped", "suggested_fix": ""}
            _error = f"LLM review unavailable. Issue encountered : {e}"
            return {
                "error": _error
            }


    @memoize(configuration=m_cfg)
    async def summarize(self, state: dict) -> dict:
        """Provide summary for user question"""
        self.log.debug(f"\ntraffic_agent :: summarize :: state :: {state}")
        _error = ""
        if not state["summarize"]:
            return 
        if state["sql_query"] == "NOT_RELEVANT":
            return {"summary": f'Sorry, Please provide additional information. Original question : {state["question"]}'}

        try:
            summary_prompt = summarize_prompt(state)
            self.log.debug(f"\ntraffic_agent :: summarize :: summary_prompt :: {summary_prompt}")
            print(f"\ntraffic_agent :: summarize :: summary_prompt :: {bool(summary_prompt)}")
            if summary_prompt:
                summary = await self.llm_manager.call(
                    prompt=summary_prompt,
                    model=SUMMARY_MODEL,
                    temperature=0.2
                )
            else:
                summary = fallback_summarize(state)
            return {
                # "messages": [
                #     SystemMessage(content=summary_prompt),
                #     AIMessage(content=orjson.dumps(summary).decode('utf-8'))
                #     ],
                "summary": summary
                }
        except Exception as e:
            summary = fallback_summarize(state)
            _error = f"LLM summary unavailable. Issue encountered : {e}"
            return {
                # "messages": AIMessage(content=summary),
                "summary": summary, 
                "error": _error
            }


    async def warmup(self, state: dict, runtime: Runtime[Context]) -> dict:
        self.log.debug(f"\ntraffic_agent :: warmup :: state :: {state}")
        print(f"\ntraffic_agent :: warmup :: UID :: {runtime.context.user_id}")
        intent = intent_tag(state["question"])

        # memory = get_conversation_history(user_id=runtime.context.user_id, 
        #                                   params=["question", "answer"])
        # if memory:  # Run only if warmup is not performed
        #     prompt = get_conversation_prompt(prev_conv=memory) if memory else None
            # self.llm_manager_rest.call(warmup=True, prompt=prompt)
        
        # warmed_up = await warmup_done(user_id=runtime.context.user_id)
        # if not warmed_up:
        #     await self.llm_manager.call(warmup=True)

        return {
            # "messages" : HumanMessage(content=state["question"]),
            "repairs_left": QA_MAX_REPAIRS, 
            "intent": intent,
            "chart_intent" : CHART_INTENT_ALIASES.get(intent, intent)
        }
    

    async def run_sql(self, state: dict) -> dict:
        """Execute query"""
        self.log.debug(f"\ntraffic_agent :: run_sql :: state :: {state}")
        query = state["sql_query"]
        _lquery = query.lower().lstrip()
        if query == "NOT_RELEVANT":
            return {"sql_valid": False}
        
        if not (_lquery.startswith("select") or _lquery.startswith("with")):
            return {
                "sql_valid": False,
                "sql_issues": "Only read-only SELECT/WITH queries are allowed."
            }
        
        try:
            result = await self.db_manager._execute_query(
                uuid=self.request_id, query=query)
            return {
                # "messages": ToolMessage(
                #     content=orjson.dumps(result["data"]).decode('utf-8'),
                #     tool_call_id=result["tool_id"],
                #     name=result["tool_name"],
                # ),
                "sql_valid": True, 
                "results": result["data"],
                "row_count": result["rowCount"],
                "columns": result["columns"]
                }
        except Exception as e:
            return {"error": str(e), "sql_issues": str(e)}