from config.dip import DIP_KEYWORDS

def intent_tag(q):
    ql = q.lower()
    if any(w in ql for w in ("how many", "count", "number of")): return "count"
    if any(w in ql for w in ("top", "highest", "lowest", "busiest", "rank", "most", "least")): return "ranking"
    if any(w in ql for w in ("util", "congest", "capacity")): return "utilization"
    if any(w in ql for w in ("average", "avg", "total", "sum", "per ")): return "aggregation"
    if any(w in ql for w in ("over time", "trend", "by time", "each hour", "timeline")): return "timeseries"
    return "lookup"


# Sub-graph router
def route_query(question: str) -> str:
    if any(w in question for w in DIP_KEYWORDS):
        return "run_dip"
    else:
        return "run_traffic"
    return "parse_question"