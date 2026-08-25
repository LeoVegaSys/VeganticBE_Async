# ===============================
# OLLAMA
# ===============================
OLLAMA_URL="http://localhost:11434/api/generate"
OLLAMA_HOST="localhost"
OLLAMA_PORT=11434
SQL_MODEL="qwen2.5-coder:7b"
SUMMARY_MODEL="llama3.2:3b"
SUMMARIZE_MODEL="llama3.2:3b"
OLLAMA_KEEP_ALIVE="30m"
QA_TIMEOUT=180

LLM_PORT_CONFIG={
    "qwen2.5-coder:7b" : [11438, 11435, 11436, 11439],
    "llama3.2:3b" : [11437, 11435, 11436, 11439],
    "sqlcoder:7b" : [11435, 11436, 11439]
}