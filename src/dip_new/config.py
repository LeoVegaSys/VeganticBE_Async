# ===============================
# DIP_NEW: settings for the LLM-filled dip tool (src/dip_new)
# The old dip sub-graph (src/dip) is untouched; USE_DIP_NEW picks which one runs.
# ===============================
from config.llm import SQL_MODEL

# Route dip questions to src/dip_new (True) or the old src/dip (False).
USE_DIP_NEW = True

# Model that turns the question into tool arguments (JSON, schema-constrained).
DIP_SLOT_MODEL = SQL_MODEL

DIP_DEFAULT_WINDOW_HOURS = 1      # used when neither the question nor the UI gives a time
DIP_DEFAULT_LIMIT = 50
DIP_BASELINE_POINTS = 3           # baseline = average of the previous N readings
DIP_SERIES_MAX_PAIRS = 20         # max interfaces returned with chart points

# When /ask carries no filters, read them from ai_db.chat_sessions by session id.
DIP_LOAD_SESSION_FILTERS = True

# UI dates sent as ISO with a time zone (e.g. '2026-09-28T18:30:00.000Z') are
# converted to this offset before taking the date. 330 = IST.
UI_TZ_OFFSET_MINUTES = 330

# ---------------------------------------------------------------------------
# Traffic views per data source: source name -> (view, anchor table).
# The anchor table's MAX(Time_1) is "now" (the data is not live).
# Create the DEMO_MPLS views with src/dip_new/sql/demo_mpls_dip_views.sql.
# ---------------------------------------------------------------------------
DEFAULT_SOURCE = "mpls"
DIP_VIEWS = {
    "demo_mpls": {
        "mpls":     ("mpls_traffic_raw",     "ROUTERTRAFFIC_VLANPRT_SCALE1_TBL"),
        "mpls_b2b": ("mpls_b2b_traffic_raw", "ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B"),
    },
    "vegayan_mpls": {
        "mpls": ("mpls_traffic_raw", "ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B"),
    },
    "mpls_traffic_raw": {
        "mpls": ("mpls_traffic_raw", "ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B"),
    },
}

# UI "Network" value (lower-case, letters and digits only) -> source above.
# CEN etc. have no traffic view yet; the reply says so.
NETWORK_TO_SOURCE = {
    "mpls": "mpls",
}

# The UI "Services" filter is on hold: it is read and reported, not applied.
APPLY_SERVICES = False

# ---------------------------------------------------------------------------
# Circle names -> ACircle codes. Keys are lower-case letters/digits only, so
# 'Maharashtra', 'MAHARASHTRA' and 'Maha-rashtra' all match 'maharashtra'.
# Codes from the glossary; check against: SELECT DISTINCT ACircle FROM NODEANDIF_STATIC_TBL;
# A value that is already a code (MH) passes through.
# ---------------------------------------------------------------------------
CIRCLE_CODES = {
    "andhrapradesh": "AP", "andhra": "AP", "telangana": "AP", "aptelangana": "AP",
    "bihar": "BHJH", "jharkhand": "BHJH", "biharjharkhand": "BHJH", "biharandjharkhand": "BHJH",
    "gujarat": "GUJ",
    "haryana": "HAR",
    "jammukashmir": "JK", "jammuandkashmir": "JK", "jammu": "JK", "kashmir": "JK",
    "karnataka": "KK",
    "kerala": "KL",
    "maharashtra": "MH", "maharashtragoa": "MH", "maharashtraandgoa": "MH", "goa": "MH",
    "mumbai": "MUM",                                   # confirm: separate circle or part of MH?
    "madhyapradesh": "MPCG", "chhattisgarh": "MPCG", "chattisgarh": "MPCG",
    "madhyapradeshchhattisgarh": "MPCG", "madhyapradeshandchhattisgarh": "MPCG",
    "delhi": "NCR", "newdelhi": "NCR", "delhincr": "NCR", "nationalcapitalregion": "NCR",
    "northeast": "NESA", "assam": "NESA", "northeastassam": "NESA", "northeastandassam": "NESA",
    "punjab": "PB",
    "rajasthan": "RAJ",
    "tamilnadu": "TN",
    "uttarpradesheast": "UPE", "upeast": "UPE",
    "westbengal": "WB",
}

# Known values, used to check what the LLM returns.
LINK_TYPES = [
    "BRAS", "CMN-VOLTE", "Domestic Backbone", "Domestic BackToBack", "Domestic Trunk",
    "International Backbone", "Mobility-Core", "Mobility-RAN", "MPLS Telemedia",
    "MPLS-CEN-NNI", "MPLS-EPT-NPT-NNI", "MPLS-ISP-NNI", "OTHERS", "T4 DROPNODE",
    "T4 INTRACITY", "T4-EPT-NPT-NNI", "T4-Ring", "T5-Ring", "Unidentified NNI",
]
LINK_SUBTYPES = ["2G3G", "4G", "B2B", "Mobility", "MPLS-ISP"]
FLAGS = ["Physical", "Bundle", "Bundle with Dot", "Logical"]
