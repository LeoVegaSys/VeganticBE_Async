from langchain_core.prompts import ChatPromptTemplate


def sql_generate_prompt() -> ChatPromptTemplate:
    _prompt = ChatPromptTemplate.from_messages([
        # ('system', """You are an expert telecom analyst writing {db_type} SQL. Use this context: Relevant past information:"""),
        # ('placeholder', "{conversation_history}"),
        ('system', """You are an expert telecom analyst writing {db_type} SQL."""),
        ('system', "{business_facts}"),
        ('system', """LIVE SCHEMA of table `{table_name}`:
{schema}
Use this context: Relevant past information:
"""),
        ('placeholder', "{last_conversation}"),
        ("human", """Question: {question}"""),
        ('system', """Write ONE {db_type} SQL query that answers the question.
Return ONLY the SQL — no markdown, no comments, no explanation.
If there is not enough information to write a SQL query, respond with "NOT_ENOUGH_INFO".""")
    ])
    return _prompt