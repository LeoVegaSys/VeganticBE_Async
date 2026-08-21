from langchain_core.prompts import ChatPromptTemplate


def sql_generate_prompt() -> ChatPromptTemplate:
    _prompt = ChatPromptTemplate.from_messages([
        ('system', """You are an expert telecom analyst writing {db_type} SQL. Use this context: Relevant past information:"""),
        ('placeholder', "{conversation_history}"),
        ('system', "{business_facts}"),
        ('system', """LIVE SCHEMA of table `{table_name}`:
{schema}
Valid "LinkType" values: {lts}
Data time range: {when}
Write ONE DuckDB SQL query that answers the question.
Return ONLY the SQL — no markdown, no comments, no explanation.
If there is not enough information to write a SQL query, respond with "NOT_ENOUGH_INFO".
"""),
        ("human", """Question: {question}""")
    ])
    return _prompt