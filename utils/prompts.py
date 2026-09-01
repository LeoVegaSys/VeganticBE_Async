from langchain_core.prompts import ChatPromptTemplate


def summarize_prompt() -> ChatPromptTemplate:
    _prompt = ChatPromptTemplate.from_messages([
        ('system', """You are a telecom NOC result summarizer.

Answer the USER QUESTION using ONLY the RESULT.
- Be concise, natural, and directly relevant.
- Mention important entities, values, metrics, comparisons, or trends.
- Use appropriate units; convert Kbps to Mbps/Gbps when useful.
- Flag utilization >100% as a likely stale-BW issue.
- Do not explain SQL or repeat the full result.
- Never invent missing information.
- If the result cannot answer the question, state what is missing.

USER QUESTION: {question}
COLUMNS: {cols}
RESULT: {preview}
""")
    ])
    return _prompt


def fallback_summarize(state: dict) -> str:
    rows = state["results"] if "results" in state else ""
    if not rows: 
        return "No matching rows."
    return f"Returned {len(rows)} row(s). Top row: {rows[0]}"


def review_prompt() -> ChatPromptTemplate:
    _prompt = ChatPromptTemplate.from_messages([
        ('system', """You review whether a SQL result ANSWERS the question. Reply ONLY JSON.

Question: {question}
SQL: {query}
Columns: {cols}
Sample rows: {preview}

Return JSON:
{{"ok": true/false,
  "notes": "one short phrase",
  "suggested_fix": "if not ok, a SHORT instruction to fix the SQL, else empty"}}

Fail (ok=false) if the query shape doesn't match the question (e.g. asked a count
of circles but got a list of links), a requested filter is missing, or an OR
clause dropped a filter. Otherwise ok=true.""")
    ])
    return _prompt


def sql_repair_prompt() -> ChatPromptTemplate:
    _prompt = ChatPromptTemplate.from_messages([
        ("system", "{business_facts}"),
        ("system", """Fix this {db_type} SQL. Return ONLY corrected SQL.
SCHEMA: {schema}
QUESTION: {question}
BROKEN SQL: {bad_sql}
ERROR: {err}
If there is not enough information to write a SQL query, respond with "NOT_ENOUGH_INFO".
Corrected SQL:"""),
    ])
    return _prompt


def memories_to_chat_msgs(memories: list[dict]) -> list:
    _msgs = []
    if memories:
        for m in memories:
            payload = m.value
            if payload["type"] == 'question':
                _msgs.append(('human', payload["data"]))
            if payload["type"] == "answer":
                _msgs.append(('ai', payload["data"]))
    return _msgs
