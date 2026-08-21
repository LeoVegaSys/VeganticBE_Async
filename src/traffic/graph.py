from langgraph.graph import StateGraph, START, END
from langgraph.types import RetryPolicy


from src.traffic.state import TrafficState, TrafficOutputState
from src.traffic.agent import TrafficAgent


class TrafficWorkflowManager:
    def __init__(self, rid: str, sid: str, uid: str, source: str):
        self.agent=TrafficAgent(req_id=rid, sess_id=sid, usr_id=uid,
                                db_name=source)

    def create_workflow(self) -> StateGraph:
        """Create and configure the workflow graph."""
        workflow = StateGraph(state_schema=TrafficState,
                              input_schema=TrafficState,
                              output_schema=TrafficOutputState)

        workflow.add_node("warmup", self.agent.warmup)
        workflow.add_node(
            "generate_sql", self.agent.generate_sql,
            retry_policy=RetryPolicy(max_attempts=2, initial_interval=0.5,
                                     retry_on=(Exception)))
        workflow.add_node("run_sql", self.agent.run_sql)
        workflow.add_node("repair_sql", self.agent.repair_sql)
        workflow.add_node("summarize", self.agent.summarize)
        workflow.add_node("review", self.agent.review)

        workflow.add_edge("warmup", "generate_sql")
        workflow.add_edge("generate_sql", "run_sql")
        workflow.add_edge("run_sql", "repair_sql")
        # workflow.add_edge("summarize", "review")
        # workflow.add_edge("review", END)
        workflow.add_edge("summarize", END)
        
        workflow.set_entry_point("warmup")

        return workflow
    
    def returnGraph(self):
        return self.create_workflow().compile(checkpointer=True)

    async def run_traffic_agent(self, question: str, summarize: bool) -> dict:
        print(f"\nTrafficGraph :: run_traffic_agent :: Q {question} :: \
              :: SMR {summarize}")
        app = self.create_workflow().compile(checkpointer=True)
        # app = self.create_workflow().compile()
        result = await app.ainvoke(
            {"question": question, "summarize": summarize}
        )
        print(f"\nrun_traffic_agent :: result :: {result}")
        return result
