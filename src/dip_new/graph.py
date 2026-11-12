from langgraph.graph import StateGraph, END

from src.dip_new.state import DipNewState, DipNewOutputState
from src.dip_new.agent import DipNewAgent


class DipNewWorkflowManager:
    def __init__(self, rid: str, sid: str, uid: str, source: str):
        self.agent = DipNewAgent(req_id=rid, sess_id=sid, usr_id=uid, db_name=source)

    def create_workflow(self) -> StateGraph:
        wf = StateGraph(state_schema=DipNewState,
                        input_schema=DipNewState,
                        output_schema=DipNewOutputState)
        wf.add_node("fill_slots", self.agent.fill_slots)        # LLM -> tool arguments
        wf.add_node("apply_scope", self.agent.apply_scope)      # + UI global filters
        wf.add_node("calculate_dip", self.agent.calculate_dip)  # deterministic SQL via MCP
        wf.add_node("summarize_dip", self.agent.summarize)

        wf.add_edge("fill_slots", "apply_scope")
        wf.add_edge("apply_scope", "calculate_dip")
        wf.add_edge("calculate_dip", "summarize_dip")
        wf.add_edge("summarize_dip", END)
        wf.set_entry_point("fill_slots")
        return wf

    def returnGraph(self):
        return self.create_workflow().compile()

    async def run_dip_agent(self, question: str, summarize: bool,
                            filters: dict = None, session_id: str = "") -> dict:
        print(f"\nDipNewGraph :: run_dip_agent :: Q {question} :: F {filters}")
        # compile() without checkpointer=True: a fresh sub-graph state per question.
        # (checkpointer=True keeps the sub-graph state across turns of a thread, so an
        # old 'error' or 'results' would leak into the next question.)
        app = self.create_workflow().compile()
        result = await app.ainvoke({
            "question": question, "summarize": summarize,
            "ui_filters": filters or {}, "session_id": str(session_id or ""),
            "warnings": [], "error": "",
        })
        print(f"\nDipNewGraph :: run_dip_agent :: result :: {result}")
        return result
