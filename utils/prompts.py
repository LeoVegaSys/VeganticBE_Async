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


# Query Router prompts

router_intro_prompt = '''
You are a strict query classification engine.
Your task is to classify the given input query into exactly one of the following categories.

Classification Rules
'''

dip_prompt = '''
DIP Rule: Return run_dip
If the input query contains any of the following words or phrases (including their case-insensitive occurrences), return run_dip.
Keywords:{DIP_KEYWORDS}

'''

cust_rpt_prompt = '''
CUSTOMER_REPORT Rule: Return run_customer_report
If the input query contains any of the following words or phrases (including their case-insensitive occurrences), return run_cust.
Keywords:{CR_KEYWORDS}

'''

traffic_prompt = '''
DEFAULT Rule: Default classification
If the input query does not contain any matching keyword from above Rules, return run_traffic.

'''

instructions = '''
Important Instructions
Matching must be case-insensitive.
Match whole words rather than partial words. For example, fall should not match fallback.
For multiword phrases such as 100% bandwidth and 100% bw, match the complete phrase.
Return exactly one string.
Do not provide explanations, additional text, punctuation, JSON, or reasoning.
Never generate any output other than the permitted strings.
Input Query:

{input_query}

Output:
'''