# ===============================
# CUSTOMER_REPORT: settings for the customer traffic report tool (src/customer_report)
# Built from the CustomerTrafFilter_reporting_hist procedure, calculated from the
# 5-minute traffic table (no daily / hourly tables, no temp tables, no OUTFILE).
# ===============================
from config.llm import SQL_MODEL

# Route customer-report questions here (True), or leave them to the traffic graph (False).
USE_CUSTOMER_REPORT = True

# Model that turns the question into tool arguments (JSON, schema-constrained).
CR_SLOT_MODEL = SQL_MODEL

# When /ask carries no filters, read them from ai_db.chat_sessions by session id.
CR_LOAD_SESSION_FILTERS = True

# ---------------------------------------------------------------------------
# Tables per data source.
#   customers: CUSTOMER_VRF_TBL (one row per customer port; IfSpeed = subscribed Kb)
#   traffic:   5-minute samples, RcvOctets / TxOctets already in bps
#   inventory: optional, for the UI circle / tier filter (APortID, ACircle, ATier)
# On DEMO_MPLS the customer ports are in SCALE1_TBL (6861 of 7052), not in _B.
# ---------------------------------------------------------------------------
CR_TABLES = {
    "demo_mpls": {
        "customers": "CUSTOMER_VRF_TBL",
        "traffic": "ROUTERTRAFFIC_VLANPRT_SCALE1_TBL",
        "inventory": "NODEANDIF_STATIC_TBL",
    },
}

POLL_SECONDS = 300                 # one sample = 5 minutes (volume = rate x 300 s)

# ---------------------------------------------------------------------------
# Rules (utilization = traffic / subscribed bandwidth, In and Out separately;
# a port's utilization is the higher of the two)
# ---------------------------------------------------------------------------
THRESHOLD_PCT = 80                 # "threshold breach" / Exceed Count
SATURATION_PCT = 100               # "100% BW reached"
SATURATED_MIN_SAMPLES = 3          # saturated = at least 3 samples (15 min) at >= 100%
UPGRADE_MIN_SHARE = 0.10           # upgrade = >= 10% of samples above THRESHOLD_PCT ...
UPGRADE_MIN_PEAK_PCT = 70          # ... and peak utilization >= 70%
OVER_SUBSCRIBED_PCT = 200          # flag: peak far above the subscribed bandwidth
UNDERUTILIZED_PCT = 10             # downgrade candidate: average utilization below 10%

DEFAULT_LIMIT = 50
MAX_LIMIT = 500
HOURLY_MAX_ROWS = 500

# Which customer ports count (same as the procedure): active, real port, LSI > 100, no loopback.
# ---------------------------------------------------------------------------

# Location: what the user may say -> the spellings stored in CUSTOMER_VRF_TBL.Location.
# Matching is case-insensitive. Amaravati (AP) and Amravati (MH) are different cities.
LOCATION_ALIASES = {
    "delhi": ["NEW DELHI", "Delhi"],
    "new delhi": ["NEW DELHI", "Delhi"],
    "varanasi": ["Varanasi", "BANARAS"],
    "banaras": ["Varanasi", "BANARAS"],
    "benares": ["Varanasi", "BANARAS"],
    "bhubaneswar": ["Bhuwneshwar", "BHUWNESWAR"],
    "bhuwneshwar": ["Bhuwneshwar", "BHUWNESWAR"],
    "vijayawada": ["VIJAYAWADA", "Vijaywada"],
    "vijaywada": ["VIJAYAWADA", "Vijaywada"],
    "sanchore": ["Sanchore", "SANCHOR"],
    "sanchor": ["Sanchore", "SANCHOR"],
    "bathinda": ["Bhatinda"],
    "bhatinda": ["Bhatinda"],
    "proddatur": ["Proddattur"],
    "proddattur": ["Proddattur"],
    "ahmedpur": ["AHAMEDPUR"],
    "ahamedpur": ["AHAMEDPUR"],
    "kudligi": ["Kudilgi"],
    "kudilgi": ["Kudilgi"],
    "amaravati": ["Amaravati"],
    "amravati": ["AMRAVATI"],
}

# Stored locations on DEMO_MPLS (for "did you mean" when a name matches nothing).
KNOWN_LOCATIONS = [
    "Adoni", "AHAMEDPUR", "Amaravati", "AMRAVATI", "Baddi", "BANARAS", "BARGAWAN",
    "Bhatinda", "Bhuwneshwar", "BHUWNESWAR", "Bolangir", "BWM", "BWT", "BWTG", "CHENNAI",
    "Delhi", "GPLU", "Hyderabad", "Indore", "Jabalpur", "JAG", "Jagalur", "Jodhpur", "KDI",
    "Kudilgi", "Ludhiana", "MHN", "NEW DELHI", "Pachpadra", "PAINT", "Proddattur", "SANCHOR",
    "Sanchore", "SATHYAVEDU", "Shahjahanpur", "Ukani viram rai", "Uthukottai", "Varanasi",
    "VIJAYAWADA", "Vijaywada",
]

# Words that send a question to this tool (checked after the dip keywords).
CR_KEYWORDS = (
    "customer", "customers", "circuit", "circuits", "lsi", "vrf", "upgrade", "downgrade",
    "breach", "breaches", "threshold", "exceed", "exceeded", "saturate", "saturated",
    "saturation", "nld", "subscribed", "100% bandwidth", "100% bw",
)
