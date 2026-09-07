from langchain_core.prompts import ChatPromptTemplate


def sql_generate_prompt() -> ChatPromptTemplate:
    _prompt = ChatPromptTemplate.from_messages([
        # ('system', """You are an expert telecom analyst writing {db_type} SQL. Use this context: Relevant past information:"""),
        # ('placeholder', "{conversation_history}"),
        ('system', """You are a helpful assistant for the Vegayan CEN network monitoring database (MySQL 5.7). You talk to network engineers about the data, and you write SQL when they want to see some . but you dont give the query away directly .
If the user wants to view traffic Nodename Interface_Name and which Unit it wants to view you have to ask . only after all three paramters are given by the user you will form the query around those paramters .
{schema}
{business_facts}
Use this context: Relevant past information:
"""),
        ('placeholder', "{last_conversation}"),
        ("human", """Question: {question}"""),
        ('system', """Write ONE {db_type} SQL query that answers the question.
Return ONLY the SQL — no markdown, no comments, no explanation.
If there is not enough information to write a SQL query, respond with "NOT_ENOUGH_INFO".""")
    ])
    return _prompt