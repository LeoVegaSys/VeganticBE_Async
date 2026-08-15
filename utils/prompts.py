import json


def summarize_prompt(state: dict) -> str:
    preview = json.dumps(state["results"][:40], default=str) if "results" in state else ""

    return f"""You are a telecom NOC analyst. Answer the question from the result ONLY.
Respond in ENGLISH, 2-4 sentences. Name the key entities with their numbers.
Convert Kbps to Mbps/Gbps when large. Flag utilization > 100 as a likely stale-BW issue.
Do not restate the whole table or explain the SQL.

QUESTION: {state["question"]}
COLUMNS: {state["columns"]}
ROWS: {preview}
"""


def fallback_summarize(rows: list) -> str:
    if not rows: 
        return "No matching rows."
    return f"Returned {len(rows)} row(s). Top row: {rows[0]}"


def conversation_prompt(prev_conv: str) -> str:
# You are a helpful assistant. Use this context: Relevant past information:\n\n{prev_conv}"""
    return f"""Use this context: Relevant past information:\n\n{prev_conv}"""


def review_prompt(state: dict) -> str:
    preview = json.dumps(state["results"][:40], default=str) if "results" in state else ""
# Filters that should be applied: {json.dumps(filters or {})}
    return f"""You review whether a SQL result ANSWERS the question. Reply ONLY JSON.

Question: {state['question']}
SQL: {state["sql_query"]}
Columns: {state["columns"]}
Sample rows: {preview}

Return JSON:
{{"ok": true/false,
  "notes": "one short phrase",
  "suggested_fix": "if not ok, a SHORT instruction to fix the SQL, else empty"}}

Fail (ok=false) if the query shape doesn't match the question (e.g. asked a count
of circles but got a list of links), a requested filter is missing, or an OR
clause dropped a filter. Otherwise ok=true."""


def sql_generate_prompt(
        db_type, business_facts, table_name, schema, lts, when, question, prev_convo):
    return f"""You are an expert telecom analyst writing {db_type} SQL.
{prev_convo}
{business_facts}
LIVE SCHEMA of table `{table_name}`:
{schema}
Valid "LinkType" values: {lts}
Data time range: {when}
Write ONE DuckDB SQL query that answers the question.
Return ONLY the SQL — no markdown, no comments, no explanation.
If there is not enough information to write a SQL query, respond with "NOT_ENOUGH_INFO".
Question: {question}
"""

def sql_repair_prompt(db_type, business_facts, schema, question, bad_sql, err):
    return f"""Fix this {db_type} SQL. Return ONLY corrected SQL.
{business_facts}
SCHEMA: {schema}
QUESTION: {question}
BROKEN SQL: {bad_sql}
ERROR: {err}
If there is not enough information to write a SQL query, respond with "NOT_ENOUGH_INFO".
Corrected SQL:"""