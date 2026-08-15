# ===============================
# QDRANT CONFIG
# ===============================
QDRANT_URL = "http://localhost:6333"

COLLECTIONS = {
    "ietf": "noc_v3_ietf",
    "rfc":  "noc_v3_rfc",
}

PENDING_COLLECTION = "noc_v3_feedback_pending"

VECTOR_SIZE = 384  # all-MiniLM-L6-v2

# ===============================
# EMBEDDING MODEL
# ===============================
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ===============================
# LLM CONFIG
# ===============================
LLM_URL  = "http://localhost:11434/api/generate"
LLM_MODEL = "llama3:8b"

# ===============================
# CHUNKING
# ===============================
CHUNK_SIZE    = 400
CHUNK_OVERLAP = 80

# ===============================
# PIPELINE SETTINGS
# ===============================
BATCH_SIZE       = 64    # vectors per upsert batch
EMBED_BATCH_SIZE = 32    # texts per embedding batch
PROGRESS_FILE    = "pipeline_progress_v3.json"  # resume checkpoint

# ===============================
# RETRIEVAL
# ===============================
TOP_K_PER_COLLECTION = 3   # fetch 3 from each collection → 6 total
TOP_K_FEEDBACK       = 2   # max feedback chunks

# ===============================
# LLM GENERATION
# ===============================
TEMPERATURE = 0.1