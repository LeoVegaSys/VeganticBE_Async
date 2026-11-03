import orjson

from langgraph.runtime import Runtime

from managers.models.llm import LLMManager
from utils.logs import FileLogger
from utils.context import Context
from config.llm import SQL_MODEL, SUMMARY_MODEL
from utils.delay import async_delay
from utils.rag import query_rag

from db.pattern import DBFactory


class RAGAgent:
    def __init__(
            self,
            request_id: str,
            session_id: str,
            user_id: str,
            db_name: str):
        self.request_id = request_id
        self.session_id = session_id
        self.user_id = user_id

        self.llm_manager = LLMManager()
        self.log = FileLogger().get_logger()

        self.data_source = DBFactory().get(db_name=db_name)
        self.db_manager = self.data_source.get_db_manager()


    def warmup(self, state: dict, runtime: Runtime[Context]) -> dict:
        """Function to add initial setup/cleanup"""

        self.log.debug(f"\nRAG agent :: warmup :: state :: {state}")
        print(f"\nRAG agent :: warmup :: UID :: {runtime.context.user_id}")
        return{"sql_query": '', "sql_issues": ''}


    async def retrieve_rag(self, state: dict, runtime: Runtime[Context]) -> dict:
        self.log.debug(f"\nRAG agent :: retrieve_rag :: state :: {state}")
        result = await query_rag(question=state["question"])
        print(f"\nRAG agent :: retrieve_rag :: RAG response :: {result}")
        # return {"sql_query": sql_response, "sql_valid": True, "sql_issues": "", "error": ""}
        

    async def run_sql(self, state: dict) -> dict:
        """Execute query"""
        self.log.debug(f"\nRAG agent :: run_sql :: state :: {state}")
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


    def review(self):
        pass

    def visualize(self):
        pass
        