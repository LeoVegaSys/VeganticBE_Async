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

from src.start_with_rag.state import InputState, OutputState
from src.start_with_rag.agent import RAGAgent
from config.store import (REDIS_HOST, REDIS_PORT, STORE_DB, CLEAR_USER_STORE,
                          HISTORY)
from config.checkpointer import *
from utils.context import Context, QueryRequest, NewQueryRequest
from utils.store import (manage_store, write_to_store, get_ttl_config,
clear_store, create_memory_payload)


class RAGWorkflowManager:
    def __init__(
            self,
            request_id : str,
            session_id: str,
            user_id: str,
            source: str
            ):
        self.agent = RAGAgent(
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
        wf.add_node("run_sql", self.agent.run_sql)
        wf.add_node("review", self.agent.review)
        wf.add_node("visualize", self.agent.visualize)

        wf.add_edge("warmup", "get_from_rag")
        wf.add_edge("get_from_rag", "run_sql")
        wf.add_edge("run_sql", "visualize")
        # workflow.add_edge("run_sql", "review")
        # workflow.add_edge("review", "visualize")
        wf.add_edge("visualize", END)
        
        wf.set_entry_point("warmup")

        return wf

    def return_graph(self):
        return self.create().compile()

    async def answer_query(self, data: dict) -> dict:
        """
        Run the agent workflow and return the formatted answer.
        """
        rq : NewQueryRequest = NewQueryRequest(body=data)
        print(f"\nRAG Graph :: answer_query :: req {rq.__dict__}")

        '''
        store_uri = f"{STORE_DB}://{REDIS_HOST}:{REDIS_PORT}"
        pg_uri = f"{CHECKPOINTER_DB}://{PG_USER}:{PG_PWD}@{PG_HOST}:{PG_PORT}/{PG_DB_NAME}"
        conn_kwargs = {"autocommit": True, "prepare_threshold": 0}

        async with AsyncRedisStore.from_conn_string(store_uri, ttl=get_ttl_config()) as store:
            async with AsyncConnectionPool(conninfo=pg_uri, max_size=20,
                                            kwargs=conn_kwargs) as pool:
                checkpointer = AsyncPostgresSaver(pool)

                if CLEAR_THREAD_CHECKPOINTER:
                    await checkpointer.adelete_thread(thread_id=rq.session_id)
                if CLEAR_USER_STORE:
                    await clear_store(user_id=rq.user_id)
        '''
        # app = self.create_workflow().compile(store=store, checkpointer=checkpointer)
        # app = self.create_workflow().compile(store=store)
        app = self.create_workflow().compile()

        _uuid = rq.request_id or uuid4().hex[:12]
        config: RunnableConfig = {
            "configurable": {"thread_id": rq.session_id}
            } if rq.session_id else None
        context = Context(user_id=rq.user_id) if rq.user_id else None

        if rq.user_response:
            result = await app.ainvoke(
                Command(resume=rq.user_response),
                config=config, context=context)
        else:
            result = await app.ainvoke(
                input={"question": rq.question, "request_id": _uuid,
                    "session_id": rq.session_id, "user_id": rq.user_id,
                    "summarize": rq.summarize,
                    "data_source": rq.data_source},
                config=config, context=context)

        # snapshot = await app.aget_state(config)
        # if snapshot.interrupts:
        #     result["user_input_required"] = snapshot.interrupts[0].value

        print(f"\nRAG graph :: answer_query :: result :: {result}")
        return result