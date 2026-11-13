from langgraph.graph import StateGraph, END

from src.customer_report.state import CustomerReportState, CustomerReportOutputState
from src.customer_report.agent import CustomerReportAgent


class CustomerReportWorkflowManager:
    def __init__(self, rid: str, sid: str, uid: str, source: str):
        self.agent = CustomerReportAgent(req_id=rid, sess_id=sid, usr_id=uid, db_name=source)

    def create_workflow(self) -> StateGraph:
        wf = StateGraph(state_schema=CustomerReportState,
                        input_schema=CustomerReportState,
                        output_schema=CustomerReportOutputState)
        wf.add_node("fill_slots", self.agent.fill_slots)        # LLM -> report arguments
        wf.add_node("apply_scope", self.agent.apply_scope)      # + UI global filters
        wf.add_node("run_report", self.agent.run_report)        # deterministic SQL via MCP
        wf.add_node("summarize_report", self.agent.summarize)

        wf.add_edge("fill_slots", "apply_scope")
        wf.add_edge("apply_scope", "run_report")
        wf.add_edge("run_report", "summarize_report")
        wf.add_edge("summarize_report", END)
        wf.set_entry_point("fill_slots")
        return wf

    def returnGraph(self):
        return self.create_workflow().compile()

    async def run_report_agent(self, question: str, summarize: bool,
                               filters: dict = None, session_id: str = "") -> dict:
        print(f"\nCustomerReportGraph :: run_report_agent :: Q {question} :: F {filters}")
        # Fresh sub-graph state per question (no checkpointer=True), as in dip_new.
        app = self.create_workflow().compile()
        result = await app.ainvoke({
            "question": question, "summarize": summarize,
            "ui_filters": filters or {}, "session_id": str(session_id or ""),
            "warnings": [], "error": "",
        })
        print(f"\nCustomerReportGraph :: run_report_agent :: result :: {result}")
        return result
