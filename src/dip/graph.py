from langgraph.graph import StateGraph, START, END

from src.dip.state import DipState, DipOutputState
from src.dip.agent import DipAgent


class DipWorkflowManager:
    def __init__(self):
        self.dip_agent=DipAgent()

    def create_workflow(self) -> StateGraph:
        """Create and configure the workflow graph."""
        workflow = StateGraph(state_schema=DipState,
                              input_schema=DipState,
                              output_schema=DipOutputState)

        # Deterministic non-LLM-using
        workflow.add_node("calculate_dip", self.dip_agent.dip_detect)
        workflow.add_node("summarize_dip", self.dip_agent.summarize)

        workflow.add_edge("calculate_dip", "summarize_dip")
        workflow.add_edge("summarize_dip", END)

        workflow.set_entry_point("calculate_dip")

        return workflow
    
    def returnGraph(self):
        return self.create_workflow().compile(checkpointer=True)

    
    async def run_dip_agent(self, question: str, mcp_server: str,
                                summarize: bool, request_id: str) -> dict:
        print(f"\nDipGraph :: run_dip_agent :: Q {question} :: \
              DT {mcp_server} :: SMR {summarize} :: ID {request_id}")
        app = self.create_workflow().compile(checkpointer=True)
        # app = self.create_workflow().compile()
        result = await app.ainvoke(
            {"question": question, "summarize": summarize,
             "request_id": request_id, "mcp_server":mcp_server}
        )
        print(f"\nrun_dip_agent :: result :: {result}")
        return result