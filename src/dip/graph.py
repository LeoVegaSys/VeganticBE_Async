from langgraph.graph import StateGraph, START, END

from src.dip.state import DipState, DipOutputState
from src.dip.agent import DipAgent
from config.dip import DIP_MCP

class DipWorkflowManager:
    def __init__(self, rid: str, sid: str, uid: str):
        self.dip_agent=DipAgent(rid, sid, uid)

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

    
    async def run_dip_agent(self, question: str, summarize: bool) -> dict:
        print(f"\nDipGraph :: run_dip_agent :: Q {question} :: \
              DT {DIP_MCP} :: SMR {summarize}")
        app = self.create_workflow().compile(checkpointer=True)
        # app = self.create_workflow().compile()
        result = await app.ainvoke(
            {"question": question, "summarize": summarize,
             "mcp_server":DIP_MCP}
        )
        print(f"\nrun_dip_agent :: result :: {result}")
        return result