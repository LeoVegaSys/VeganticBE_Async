from typing import Any, Dict, List
from typing_extensions import TypedDict


class DipNewState(TypedDict, total=False):
    # input
    question: str
    summarize: bool
    session_id: str
    ui_filters: Dict[str, Any]          # global filters from the UI (or chat_sessions)
    # fill_slots / apply_scope
    ui: Dict[str, Any]                  # parsed UI filters
    source: str                         # mpls | mpls_b2b
    latest: str                         # newest poll time in the data
    slots: Dict[str, Any]               # what the LLM read from the question (checked)
    llm_raw: str
    dip_args: Dict[str, Any]            # final tool arguments (slots + UI scope)
    scope_used: Dict[str, Any]
    warnings: List[str]                 # each node returns the full list
    # calculate_dip / summarize_dip (same keys as the old dip graph, plus params_used)
    sql_query: str
    sql_valid: bool
    sql_issues: str
    results: List[Any]
    columns: List[str]
    row_count: int
    params_used: Dict[str, Any]
    formatted_data_for_visualization: Dict[str, Any]
    intent: str
    chart_intent: str
    summary: str
    error: str


class DipNewOutputState(TypedDict, total=False):
    sql_query: str
    sql_valid: bool
    sql_issues: str
    results: List[Any]
    columns: List[str]
    row_count: int
    params_used: Dict[str, Any]
    warnings: List[str]
    formatted_data_for_visualization: Dict[str, Any]
    intent: str
    chart_intent: str
    summary: str
    error: str
