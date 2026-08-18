from uuid import uuid4
import asyncio

from langgraph.graph import END, START
from langgraph.graph import StateGraph
from langgraph.store.redis.aio import AsyncRedisStore
from langgraph.runtime import Runtime
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command
from langchain_core.runnables import RunnableConfig

from src.startpoint.state import InputState, OutputState
from src.traffic.graph import TrafficWorkflowManager
from utils.store import manage_store, add_to_memories, get_ttl_config
from utils.categorize import route_query
from utils.context import Context, QueryRequest
from config.redis import REDIS_HOST, REDIS_PORT

async def classify_query(state: dict, runtime: Runtime[Context]) -> str:
    print(f"\nget_query_type :: state :: {state}")

    ## TODO Implement LLM question parser for additional user input required
    ## Set up interrupt-resume cycle below
    #is_approved = interrupt("Do you want to proceed with this action?")

    await manage_store(user_id=runtime.context.user_id)
    return route_query(question=state["question"].lower())


async def call_traffic_graph(state: InputState, runtime: Runtime[Context]):
    print(f"\ncall_traffic_graph :: state :: {state}")
    result = await TrafficWorkflowManager().run_traffic_agent(
        question=state["question"], summarize=state["summarize"], 
        request_id=state["request_id"], mcp_server=state["mcp_server"])
    
    # Write question to store
    await add_to_memories(user_id=runtime.context.user_id,
                          param_key="question",
                          data=state["question"])
    # Write result to store
    await add_to_memories(user_id=runtime.context.user_id, param_key="answer",
                          data=result,
                          fields_to_copy=["sql_query", "summary", "error"])

    print(f"\ntrafficGraph :: call_traffic_graph :: result :: {result}")
    return result


async def call_dip_graph(state: InputState, runtime: Runtime[Context]):
    print(f"\ncall_dip_graph :: state :: {state}")
    pass



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

        '''
        # Deterministic non-LLM-using
        workflow.add_node("calculate_dip", self.dip_agent.dip_detect)
        workflow.add_node("summarize_dip", self.dip_agent.summarize)

        # LLM-using
        workflow.add_node("parse_question", self.sql_agent.parse_question)
        workflow.add_node("get_unique_nouns", self.sql_agent.get_unique_nouns)
        workflow.add_node("generate_sql", self.sql_agent.generate_sql)
        workflow.add_node("validate_and_fix_sql", self.sql_agent.validate_and_fix_sql)
        workflow.add_node("execute_sql", self.sql_agent.execute_sql)
        workflow.add_node("format_results", self.sql_agent.format_results)
        workflow.add_node("choose_visualization", self.sql_agent.choose_visualization)
        workflow.add_node("format_data_for_visualization", self.data_formatter.format_data_for_visualization)
        
        # Define edges
        workflow.add_conditional_edges(START, get_query_type)

        workflow.add_edge("calculate_dip", "summarize_dip")
        workflow.add_edge("summarize_dip", END)

        workflow.add_edge("parse_question", "get_unique_nouns")
        workflow.add_edge("get_unique_nouns", "generate_sql")
        workflow.add_edge("generate_sql", "validate_and_fix_sql")
        workflow.add_edge("validate_and_fix_sql", "execute_sql")
        workflow.add_edge("execute_sql", "format_results")
        workflow.add_edge("execute_sql", "choose_visualization")
        workflow.add_edge("choose_visualization", "format_data_for_visualization")
        workflow.add_edge("format_data_for_visualization", END)
        workflow.add_edge("format_results", END)
        # workflow.set_entry_point("categorize")
        '''
        return workflow
    
    def returnGraph(self):
        return self.create_workflow().compile()

    async def answer_query(self, request: QueryRequest) -> dict:
        """
        Run the agent workflow and return the formatted answer.
        """
        print(f"\nGraph :: answer_query :: req {request.__dict__}")
        
        store_uri = f"redis://{REDIS_HOST}:{REDIS_PORT}"
        checkpointer = InMemorySaver()
        async with AsyncRedisStore.from_conn_string(store_uri, ttl=get_ttl_config()) as store:
        # checkpointer = RedisSaver.from_conn_string(store_uri)

            # app = self.create_workflow().compile(store=store)
            app = self.create_workflow().compile(store=store, checkpointer=checkpointer)
            # app = self.create_workflow().compile()

            _uuid = request.request_id or uuid4().hex[:12]
            config: RunnableConfig = {
                "configurable": {"thread_id": request.session_id}
                } if request.session_id else None
            context = Context(user_id=request.user_id) if request.user_id else None

            if request.user_response:
                result = await app.ainvoke(
                    Command(resume=request.user_response),
                    config=config, context=context)
            else:
                result = await app.ainvoke(
                    input={"question": request.question, "request_id": _uuid,
                           "summarize": request.summarize,
                           "mcp_server": request.mcp_server},
                    config=config, context=context)

            snapshot = app.get_state(config)
            if snapshot.interrupts:
                result["user_input_required"] = snapshot.interrupts[0].value

            print(f"\ngraph :: answer_query :: result :: {result}")
            return result