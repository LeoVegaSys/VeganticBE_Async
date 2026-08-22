# ===============================
# OLLAMA
# ===============================
OLLAMA_URL="http://localhost:11434/api/generate"
OLLAMA_HOST="localhost"
OLLAMA_PORT=11434
SQL_MODEL="qwen2.5-coder:7b"
SUMMARY_MODEL="llama3.2:3b"
OLLAMA_KEEP_ALIVE="30m"
QA_TIMEOUT=180

LLM_PORT_CONFIG={
    "qwen2.5-coder:7b" : [11438, 11435, 11436, 11439],
    "llama3.2:3b" : [11437, 11435, 11436, 11439],
    "sqlcoder:7b" : [11435, 11436, 11439]
}



### UNUSED
### LLM CONFIG
PARSE_QUESTION_LLM="lllama3.2"
GET_UNIQUE_NOUNS_LLM="llama3.2"
GENERATE_SQL_LLM="llama3.2"
VALIDATE_AND_FIX_SQL_LLM="llama3.2"
EXECUTE_SQL_LLM="llama3.2"
FORMAT_RESULTS_LLM="llama3.2"
CHOOSE_VISUALIZATION_LLM="llama3.2"
FORMAT_DATA_FOR_VISUALIZATION_LLM="llama3.2"

STEP_LLMS={
    "parse_question" : "llama3.2",
    "get_unique_nouns" : "llama3.2",
    "generate_sql" : "llama3.2",
    "validate_and_fix_sql" : "llama3.2",
    "execute_sql" : "llama3.2",
    "format_results" : "llama3.2",
    "choose_visualization" : "llama3.2",
    "format_data_for_visualization" : "llama3.2",
}