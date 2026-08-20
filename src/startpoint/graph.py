from uuid import uuid4

from langgraph.store.redis.aio import AsyncRedisStore
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from langgraph.graph import END, START
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime
from langgraph.types import interrupt, Command
from langchain_core.runnables import RunnableConfig

from src.startpoint.state import InputState, OutputState
from src.traffic.graph import TrafficWorkflowManager
from src.dip.graph import DipWorkflowManager
from utils.store import manage_store, add_to_memories, get_ttl_config
from utils.categorize import route_query
from utils.context import Context, QueryRequest
from config.store import REDIS_HOST, REDIS_PORT, STORE_DB
from config.checkpointer import *

async def classify_query(state: dict, runtime: Runtime[Context]) -> str:
    print(f"\nget_query_type :: state :: {state}")

    ## TODO Implement LLM question parser for additional user input required
    ## Set up interrupt-resume cycle below
    #is_approved = interrupt("Do you want to proceed with this action?")

    await manage_store(user_id=runtime.context.user_id)
    return route_query(question=state["question"].lower())


async def call_traffic_graph(state: InputState, runtime: Runtime[Context]):
    print(f"\ncall_traffic_graph :: state :: {state}")
    result = await TrafficWorkflowManager(
        rid=state["request_id"], sid=state["session_id"], uid=state["user_id"]
    ).run_traffic_agent(
        question=state["question"], summarize=state["summarize"],
        mcp_server=state["mcp_server"])
    
    # Write question to store
    await add_to_memories(user_id=runtime.context.user_id,
                          param_key="question",
                          data=state["question"])
    # Write result (from fields_to_copy in data) to store
    await add_to_memories(user_id=runtime.context.user_id, param_key="answer",
                          data=result,
                          fields_to_copy=["sql_query", "summary", "error"])

    print(f"\ntrafficGraph :: call_traffic_graph :: result :: {result}")
    return result


async def call_dip_graph(state: InputState, runtime: Runtime[Context]):
    print(f"\ncall_dip_graph :: state :: {state}")
    result = await DipWorkflowManager(
        rid=state["request_id"], sid=state["session_id"], uid=state["user_id"]
    ).run_dip_agent(
        question=state["question"], summarize=state["summarize"],
        mcp_server=state["mcp_server"])
        
    # Write question to store
    await add_to_memories(user_id=runtime.context.user_id,
                            param_key="question",
                            data=state["question"])
    # Write result (from fields_to_copy in data) to store
    await add_to_memories(user_id=runtime.context.user_id, param_key="answer",
                            data=result,
                            fields_to_copy=["sql_query", "summary", "error"])
    print(f"\ndipGraph :: ncall_dip_graph :: result :: {result}")
    return result



class WorkflowManager:
    def __init__(self):
        pass

    def create_workflow(self) -> StateGraph:
        """Create and configure the workflow graph."""
        workflow = StateGraph(state_schema=InputState, input=InputState, output=OutputState)

        workflow.add_conditional_edges(START, classify_query)
        # Add nodes from the Traffic graph
        workflow.add_node("run_traffic", call_traffic_graph)
        workflow.add_node("run_dip", call_dip_graph)
        # Define edges
        workflow.add_edge("run_traffic", END)
        workflow.add_edge("run_dip", END)

        return workflow
    
    def returnGraph(self):
        return self.create_workflow().compile()

    async def answer_query(self, rq: QueryRequest) -> dict:
        """
        Run the agent workflow and return the formatted answer.
        """
        print(f"\nGraph :: answer_query :: req {rq.__dict__}")

        store_uri = f"{STORE_DB}://{REDIS_HOST}:{REDIS_PORT}"
        pg_uri = f"{CHECKPOINTER_DB}://{PG_USER}:{PG_PWD}@{PG_HOST}:{PG_PORT}/{PG_DB_NAME}"
        conn_kwargs = {"autocommit": True, "prepare_threshold": 0}

        async with AsyncRedisStore.from_conn_string(store_uri, ttl=get_ttl_config()) as store:
            async with AsyncConnectionPool(conninfo=pg_uri, max_size=20,
                                           kwargs=conn_kwargs) as pool:
                checkpointer = AsyncPostgresSaver(pool)

                app = self.create_workflow().compile(store=store, checkpointer=checkpointer)
                # app = self.create_workflow().compile(store=store)

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
                            "mcp_server": rq.mcp_server},
                        config=config, context=context)

                snapshot = await app.aget_state(config)
                if snapshot.interrupts:
                    result["user_input_required"] = snapshot.interrupts[0].value

                print(f"\ngraph :: answer_query :: result :: {result}")
                return result