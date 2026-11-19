from uuid import uuid4
from functools import partial

from langgraph.store.redis.aio import AsyncRedisStore
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from langgraph.graph import END, START
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime
from langgraph.types import interrupt, Command
from langchain_core.runnables import RunnableConfig

from src.doc_rag.state import InputState, OutputState
from src.doc_rag.agent import DocRAGAgent
from config.store import (REDIS_HOST, REDIS_PORT, STORE_DB, CLEAR_USER_STORE,
                          HISTORY)
from config.checkpointer import *
from utils.context import Context, QueryRequest, NewQueryRequest
from utils.store import (manage_store, write_to_store, get_ttl_config,
clear_store, create_memory_payload)


class DocRAGWorkflowManager:
    def __init__(
            self,
            request_id : str,
            session_id: str,
            user_id: str,
            source: str
            ):
        self.agent = DocRAGAgent(
            request_id=request_id,
            session_id=session_id,
            user_id=user_id,
            db_name=source
        )


    def create(self) -> StateGraph:
        """Create and configure the workflow graph."""
        wf = StateGraph(
            state_schema=InputState,
            input_schema=InputState,
            output_schema=OutputState
            )
        
        wf.add_node("warmup", self.agent.warmup)
        wf.add_node("get_from_rag", self.agent.retrieve_rag)
        # wf.add_node("run_sql", self.agent.run_sql)
        # wf.add_node("review", self.agent.review)
        # wf.add_node("visualize", self.agent.visualize)

        wf.add_edge("warmup", "get_from_rag")
        wf.add_edge("get_from_rag", END)
        # wf.add_edge("get_from_rag", "run_sql")
        # wf.add_edge("run_sql", "visualize")
        # workflow.add_edge("run_sql", "review")
        # workflow.add_edge("review", "visualize")
        # wf.add_edge("visualize", END)
        
        wf.set_entry_point("warmup")

        return wf

    def return_graph(self):
        return self.create().compile()

    async def run_doc_rag(self, question: str, summarize: bool,
                                choices: dict) -> dict:
        """
        Run the Document RAG agent workflow and return the formatted answer.
        """
        print(f"\nRAG :: run_doc_rag :: Q {question} :: \
                      :: SMR {summarize}")
        app = self.create_workflow().compile()        
        result = await app.ainvoke(
            {"question": question, "summarize": summarize, "choices": choices}
            )
        
        print(f"\nRAG graph :: run_doc_rag :: result :: {result}")
        return result