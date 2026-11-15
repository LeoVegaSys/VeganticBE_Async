import re

def replace_selections_in_q(
        question: str, 
        filters: dict = {}, 
        context: list = [], 
        values: list = []):
    """
    For a given question, 
    add filters data in natural text form to the start of question,
    replace labels in question with corresponding values,
    append missing relevant values to the end of question
    so LLM gets complete user-intended context
    """
    pre_q = process_filters(filters)
    if not values and not context:
        return f"{pre_q}{question}"
    new_q = pre_q + replace_labels(question, context, values)
    return new_q


def replace_labels(question: str, context: list, values: list):
    """
    Replace labels if any in question with corresponding values and
    maintain a list of non-matched values and
    append them to the end of the question
    [{
        "type": "node",
        "label": "R1",
        "value": "MUM-XYZ-123-RWE",
    },...]
    """
    all_values = context + values
    non_matched_values = []
    suffix = ""
    expanded_q = question

    for v in all_values:
        if re.search(r'\b' + re.escape(v["label"]) + r'\b', expanded_q):
            expanded_q = re.sub(
                r'\b' + re.escape(v["label"]) + r'\b', v["value"], expanded_q)
        else: # Add to non-matched list only if part of original values list
            if v in values:
                non_matched_values.append(v)

    if non_matched_values:
        suffix += ",".join(
            [f" {i["type"]} {i["value"]}" for i in non_matched_values])
    expanded_q += suffix  # Append values whose labels are absent in question
    return expanded_q


def process_filters(filters: dict):
    """
    Add prefix to question by converting filters data structure into 
    natural text form
    {
        "filters": {
            "networks": ["MPLS"],
            "levels": ["T1"],
            "circle": ["Maharashtra"],
            "services": ["Mobility"],
            "dateFrom": "2026-09-29",
            "dateTo": "2026-09-29",
            "timeStart": "09:00",
            "timeEnd": "10:00"
  },
  """
    placeholder = "For "
    pre_text = placeholder
    if "levels" in filters and filters["levels"]:
        pre_text += f"Tier {",".join(filters["levels"])}, "
    if "circle" in filters and filters["circle"]:
        pre_text += f"Circle {",".join(filters["circle"])}, "
    if "services" in filters and filters["services"]:
        pre_text += f"Service {",".join(filters["services"])}, "

    s_dt = filters.get("dateFrom", None)
    e_dt = filters.get("dateTo", None)
    s_tm = filters.get("timeStart", None)
    e_tm = filters.get("timeEnd", None)
    if all((s_dt, e_dt, s_tm, e_tm)):
        pre_text += f"Between {s_dt} {s_tm} and {e_dt} {e_tm}, "
    if pre_text != placeholder:
        return pre_text
    return ""