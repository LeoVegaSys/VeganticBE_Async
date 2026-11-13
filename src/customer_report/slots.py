"""
slots.py -- the LLM reads the question and fills the customer report's arguments.

Ollama /api/generate with `format` = SLOT_SCHEMA (structured output), then
clean_slots() checks every value. A bad LLM reply can narrow the answer or be
ignored with a warning; it can never reach the SQL unchecked.
"""
import difflib
import math
import re
from datetime import datetime, timedelta

from src.customer_report.config import KNOWN_LOCATIONS, LOCATION_ALIASES, MAX_LIMIT
from src.customer_report.engine import HOURLY_BY, NLD, ONLY, REPORTS, SORTS
from src.dip_new.scope import to_list
from src.dip_new.slots import parse_json          # noqa: F401  (re-exported for the agent)

FILTER_KEYS = ("customer", "lsi", "circuit_id", "vrf", "location", "node", "interface")

_STR_LIST = {"type": "array", "items": {"type": "string"}}
SLOT_SCHEMA = {
    "type": "object",
    "properties": {
        "report": {"type": "string", "enum": list(REPORTS)},
        "only": {"type": "string", "enum": list(ONLY) + ["all"]},
        "util_stat": {"type": "string", "enum": ["avg", "max"]},
        "util_above": {"type": "number"},
        "util_below": {"type": "number"},
        "threshold_pct": {"type": "number"},
        **{k: _STR_LIST for k in FILTER_KEYS},
        "nld": {"type": "string", "enum": list(NLD)},
        "hourly_by": {"type": "string", "enum": list(HOURLY_BY)},
        "peak_hour_only": {"type": "boolean"},
        "sort_by": {"type": "string", "enum": list(SORTS)},
        "order": {"type": "string", "enum": ["desc", "asc"]},
        "limit": {"type": "integer"},
        "time_in_question": {"type": "boolean"},
        "window_hours": {"type": "number"},
        "start": {"type": "string"},
        "end": {"type": "string"},
    },
    "required": ["report", "time_in_question"],
}

_PROMPT = """You fill the arguments of a customer traffic report for MPLS VPN customers,
from a network engineer's question. Reply with ONE JSON object only.
Put a field ONLY when the question states it. Leave every other field out.

Data in the database: <<FIRST>> to <<LATEST>> (not live; "now" / "today" means <<DAY>>).

Fields:
- report:
    "circuits"  a list of circuits / links / ports (default)
    "customers" one row per customer: "which customers ...", "top customers by ..."
    "locations" one row per location: "in each location", "per location", "by location"
    "totals"    one row of counts: "how many circuits ...", "how many customers ..." with no
                per-location / per-customer split
    "hourly"    traffic per hour: "hourly traffic", "at what hour", "peak hour", "each hour"
- only (keep only the circuits that ...):
    "upgrade"          need a bandwidth upgrade
    "breach"           crossed / exceeded / breached the threshold
    "saturated"        hit / reached 100% bandwidth, saturated, full
    "underutilized"    underutilized, downgrade candidates
    "over_subscribed"  far above the subscribed bandwidth
    "no_data"          with no traffic data
- util_stat + util_above / util_below: "above 70% average utilization" -> util_stat "avg",
  util_above 70. "below 10% utilization" -> util_below 10. "peak above 90%" -> util_stat "max".
- threshold_pct: only when a threshold is stated: "exceed 80%" -> 80, "crossed 90%" -> 90.
- customer: customer short code or name as written: "HDFC", "Union Bank".
- lsi: LSI numbers as text: ["12345"].
- circuit_id: circuit ids as written: ["UBOI-ML3-2-9666"].
- vrf, node, interface: as written.
- location: city names as written: ["Indore"], ["New Delhi"].
- nld: "only" for "NLD circuits / NLD report"; "exclude" for "without NLD".
- hourly_by: "customer" when the hourly question is about a customer; "circuit" for a circuit.
- peak_hour_only: true for "at what hour ... peak", "peak hour".
- sort_by: "utilization", "avg_utilization", "exceed" (breaches), "saturation", "volume"
  (data / traffic volume / sent and received), "traffic", "time_above", "upgrade".
  order: "asc" for lowest / least, else leave out.
- limit: "top 10" -> 10.
- time_in_question: true only if the question gives a time or a period, else false.
- Time. Use window_hours OR start + end, never both:
    window_hours  "last 6 hours" -> 6, "last 12 hours" -> 12
    start, end    "YYYY-MM-DD HH:MM". "today" / "on 5 Nov" -> "<<DAY>> 00:00" to "<<NEXT_DAY>> 00:00".
                  "between 09:00 and 18:00" -> "<<DAY>> 09:00" to "<<DAY>> 18:00".
                  "in the evening" -> "<<DAY>> 18:00" to "<<NEXT_DAY>> 00:00".

Examples:
Q: Which customers needed a bandwidth upgrade on 5 Nov?
A: {"report": "customers", "only": "upgrade", "time_in_question": true, "start": "2026-11-05 00:00", "end": "2026-11-06 00:00"}
Q: List circuits in Indore that need an upgrade
A: {"report": "circuits", "only": "upgrade", "location": ["Indore"], "time_in_question": false}
Q: How many customer circuits need an upgrade in each location?
A: {"report": "locations", "only": "upgrade", "time_in_question": false}
Q: How many times did LSI 12345 exceed 80% today?
A: {"report": "circuits", "lsi": ["12345"], "threshold_pct": 80, "time_in_question": true, "start": "<<DAY>> 00:00", "end": "<<NEXT_DAY>> 00:00"}
Q: Top 10 customers by total traffic volume
A: {"report": "customers", "sort_by": "volume", "limit": 10, "time_in_question": false}
Q: Which customer ports in Hyderabad are above 70% average utilization?
A: {"report": "circuits", "location": ["Hyderabad"], "util_stat": "avg", "util_above": 70, "time_in_question": false}
Q: At what hour did HDFC's traffic peak?
A: {"report": "hourly", "hourly_by": "customer", "peak_hour_only": true, "customer": ["HDFC"], "time_in_question": false}
Q: Show the NLD circuit report
A: {"report": "circuits", "nld": "only", "time_in_question": false}

Q: <<QUESTION>>
A:"""


def slot_prompt(question, first, latest):
    latest = latest.replace(microsecond=0)
    day = latest.strftime("%Y-%m-%d")
    next_day = (latest + timedelta(days=1)).strftime("%Y-%m-%d")
    return (_PROMPT
            .replace("<<FIRST>>", str(first.replace(microsecond=0)) if first else "?")
            .replace("<<LATEST>>", str(latest))
            .replace("<<DAY>>", day)
            .replace("<<NEXT_DAY>>", next_day)
            .replace("<<QUESTION>>", " ".join(str(question).split())))


def _num(v, allow_zero=False):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f) or f < 0 or (f == 0 and not allow_zero):
        return None
    return f


def _dt(v):
    if not v:
        return None
    s = str(v).strip().replace("T", " ").rstrip("Z")
    try:
        return datetime.fromisoformat(s[:19]).replace(microsecond=0)
    except ValueError:
        return None


def _is_true(v):
    return v is True or str(v).strip().lower() == "true"


def resolve_locations(names):
    """User place names -> (stored Location values, warnings)."""
    out, warnings = [], []
    known_upper = {k.upper(): k for k in KNOWN_LOCATIONS}
    for n in names:
        key = " ".join(str(n).lower().split())
        if key in LOCATION_ALIASES:
            out += LOCATION_ALIASES[key]
        elif key.upper() in known_upper:
            out.append(known_upper[key.upper()])
        else:
            out.append(str(n).strip())
            if KNOWN_LOCATIONS:
                near = difflib.get_close_matches(str(n), KNOWN_LOCATIONS, n=3, cutoff=0.6)
                hint = f" Closest names: {', '.join(near)}." if near else ""
                warnings.append(f"Location {n!r} is not in the known location list.{hint}")
    return list(dict.fromkeys(out)), warnings


def clean_slots(obj, latest):
    """LLM JSON -> (slots, warnings)."""
    slots, warnings = {}, []

    report = str(obj.get("report") or "circuits").lower()
    slots["report"] = report if report in REPORTS else "circuits"

    only = str(obj.get("only") or "").lower()
    if only in ONLY:
        slots["only"] = only

    util = {}
    stat = str(obj.get("util_stat") or "").lower()
    above, below = _num(obj.get("util_above")), _num(obj.get("util_below"))
    if above is not None and above <= 1000:
        util["above"] = above
    if below is not None and below <= 1000:
        util["below"] = below
    if util:
        util["stat"] = stat if stat in ("avg", "max") else "max"
        if "above" in util and "below" in util and util["above"] >= util["below"]:
            warnings.append(f"Ignored utilization range {util['above']}-{util['below']}%.")
            util = {}
    if util:
        slots["util"] = util

    thr = _num(obj.get("threshold_pct"))
    if thr is not None:
        if 1 <= thr <= 100:
            slots["threshold_pct"] = thr
        else:
            warnings.append(f"Ignored threshold {thr:g}%: it must be between 1 and 100.")

    filters = {}
    for key in FILTER_KEYS:
        vals = to_list(obj.get(key))
        if key == "lsi":
            good = [v for v in vals if re.fullmatch(r"\d{1,12}", v)]
            if len(good) < len(vals):
                warnings.append(f"Ignored LSI value(s) that are not numbers: "
                                f"{', '.join(v for v in vals if v not in good)}.")
            vals = good
        if key == "location" and vals:
            vals, w = resolve_locations(vals)
            warnings += w
        vals = [v for v in vals if len(v) <= 200]
        if vals:
            filters[key] = list(dict.fromkeys(vals))
    if filters:
        slots["filters"] = filters

    for key, allowed in (("nld", NLD), ("hourly_by", HOURLY_BY), ("sort_by", SORTS),
                         ("order", ("asc", "desc"))):
        v = str(obj.get(key) or "").lower()
        if v in allowed:
            slots[key] = v
    if _is_true(obj.get("peak_hour_only")):
        slots["peak_hour_only"] = True
        slots["report"] = "hourly"
    if slots["report"] == "hourly" and "hourly_by" not in slots:
        slots["hourly_by"] = ("customer" if filters.get("customer") and not filters.get("circuit_id")
                              and not filters.get("lsi") else "circuit")

    lim = _num(obj.get("limit"))
    if lim:
        slots["limit"] = max(1, min(int(lim), MAX_LIMIT))

    # time
    s, e = _dt(obj.get("start")), _dt(obj.get("end"))
    wh = _num(obj.get("window_hours"))
    if s and e and e > s:
        slots["time"] = {"start": s, "end": e}
    elif _is_true(obj.get("time_in_question")):
        end = latest.replace(microsecond=0) + timedelta(seconds=1)
        if wh and wh <= 24 * 92:
            slots["time"] = {"start": end - timedelta(hours=wh), "end": end}
        elif s and not e and latest and s < latest:
            slots["time"] = {"start": s, "end": end}
        else:
            warnings.append("Could not read the time in the question; used the session or default window.")
    return slots, warnings


def fallback_slots(question):
    """When the LLM is down or replies with junk: a few keywords only."""
    q = str(question).lower()
    slots = {"report": "circuits"}
    if "upgrade" in q:
        slots["only"] = "upgrade"
    elif any(w in q for w in ("breach", "exceed", "crossed", "threshold")):
        slots["only"] = "breach"
    elif any(w in q for w in ("saturat", "100%")):
        slots["only"] = "saturated"
    elif any(w in q for w in ("underutil", "downgrade")):
        slots["only"] = "underutilized"
    if "nld" in q:
        slots["nld"] = "only"
    if re.search(r"\b(which|top)\s+customers\b", q):
        slots["report"] = "customers"
    if re.search(r"\b(each|per|by)\s+location\b", q):
        slots["report"] = "locations"
    if "hour" in q:
        slots["report"] = "hourly"
        slots["hourly_by"] = "circuit"
        if "peak" in q:
            slots["peak_hour_only"] = True
    m = re.search(r"\blsi\s*(\d{3,12})\b", q)
    if m:
        slots["filters"] = {"lsi": [m.group(1)]}
    return slots
