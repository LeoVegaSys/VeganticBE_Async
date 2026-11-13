from typing import Any, Dict, List
from typing_extensions import TypedDict


class CustomerReportState(TypedDict, total=False):
    # input
    question: str
    summarize: bool
    session_id: str
    ui_filters: Dict[str, Any]          # global filters from the UI (or chat_sessions)
    # fill_slots / apply_scope
    ui: Dict[str, Any]
    first: str                          # oldest sample in the traffic table
    latest: str                         # newest sample ("now"; the data is not live)
    slots: Dict[str, Any]               # what the LLM read from the question (checked)
    llm_raw: str
    cr_args: Dict[str, Any]             # final report arguments (slots + UI scope)
    scope_used: Dict[str, Any]
    warnings: List[str]                 # each node returns the full list
    # run_report / summarize
    sql_query: str
    sql_valid: bool
    sql_issues: str
    results: List[Any]
    columns: List[str]
    row_count: int
    params_used: Dict[str, Any]
    intent: str
    chart_intent: str
    summary: str
    error: str


class CustomerReportOutputState(TypedDict, total=False):
    sql_query: str
    sql_valid: bool
    sql_issues: str
    results: List[Any]
    columns: List[str]
    row_count: int
    params_used: Dict[str, Any]
    warnings: List[str]
    intent: str
    chart_intent: str
    summary: str
    error: str
