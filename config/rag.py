# ===============================
# V3 CONFIG — Standards RAG
# ===============================

# ===============================
# SOURCE DATA
# ===============================
STANDARDS_ROOT = "/spindlepart/DilipCheck/rag_sources/standards"

SOURCE_DIRS = {
    "ietf": [
        "ietf-drafts",
        "ietf-wg",
    ],
    "rfc": [
        "rfcs",
    ],
}

# File types to index (others are skipped)
INDEXABLE_EXTENSIONS = {".txt", ".html"}
