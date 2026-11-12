"""
slots.py -- the LLM reads the question and fills the dip tool's arguments.

The call is Ollama /api/generate with `format` = SLOT_SCHEMA, so the reply is
forced into this JSON shape (structured output). clean_slots() then checks
every value: anything out of range, unknown or contradictory is dropped with a
warning, so a bad LLM reply can narrow the answer but never break the SQL.
"""
import json
import math
import re
from datetime import datetime

from src.dip_new.config import FLAGS, LINK_SUBTYPES, LINK_TYPES
from src.dip_new.scope import circle_code, tier_code, to_list
from src.dip_new.tool.dip_engine import LEVELS, MAX_LIMIT, METRICS, UNIT_LABEL

# question field -> view column
FILTER_KEYS = {
    "circle": "Circle", "tier": "Tier", "city": "City", "vendor": "Vendor",
    "link_type": "LinkType", "link_subtype": "LinkSubType", "flag": "Flag",
    "node": "Node Name", "interface": "Interface Name", "ring": "Ring Name",
}

_STR_LIST = {"type": "array", "items": {"type": "string"}}
SLOT_SCHEMA = {
    "type": "object",
    "properties": {
        "direction": {"type": "string", "enum": ["dip", "surge"]},
        "threshold_pct": {"type": "number"},
        "pct_range": {"type": "array", "items": {"type": "number"}},
        "max_pct": {"type": "number"},
        "around_pct": {"type": "number"},
        "time_in_question": {"type": "boolean"},
        "window_hours": {"type": "number"},
        "start": {"type": "string"},
        "end": {"type": "string"},
        "level": {"type": "string", "enum": list(LEVELS)},
        "metric": {"type": "string", "enum": list(METRICS)},
        **{k: _STR_LIST for k in FILTER_KEYS},
        "min_util_pct": {"type": "number"},
        "min_change_kbps": {"type": "number"},
        "limit": {"type": "integer"},
        "unit": {"type": "string", "enum": list(UNIT_LABEL)},
        "with_series": {"type": "boolean"},
    },
    "required": ["direction", "time_in_question"],
}

_PROMPT = """You fill the arguments of a traffic dip / surge finder for an MPLS network,
from a network engineer's question. Reply with ONE JSON object only.
Put a field ONLY when the question states it. Leave every other field out.

Newest data in the database: <<LATEST>> (the data is not live; "now" means this time).

Fields:
- direction: "dip" for dip / drop / fall / decrease / loss / outage;
  "surge" for surge / spike / rise / increase / jump.
- How big the change is. Use at most ONE of:
    threshold_pct  "more than 40%", "over 40", "at least 40%", "dip of 40%"  -> 40
    pct_range      "between 40 and 70%"                                     -> [40, 70]
    max_pct        "less than 30%", "at most 30%", "under 30%"              -> 30
    around_pct     "around / about / approximately 70%"                     -> 70
- time_in_question: true only if the question gives a time or a period, else false.
- Time. Use window_hours OR start + end, never both:
    window_hours   "last 2 hours" -> 2, "last 3 days" -> 72, "last 30 minutes" -> 0.5
    start, end     "YYYY-MM-DD HH:MM". "today" -> start "<<DAY>> 00:00", end "<<LATEST_HM>>".
                   "yesterday 9 to 10 am" -> the day before <<DAY>>, 09:00 to 10:00.
- level: "interface" unless the question asks about the TOTAL traffic of a group:
  "did MH circle's total traffic dip" -> "circle"; "node-level dips" -> "node";
  also "city", "linktype", "vendor", "tier", "ring".
- metric: "in" for inbound / ingress only, "out" for outbound / egress only. Else leave out.
- circle: circle names or codes as written, e.g. ["Maharashtra"] or ["MH"].
- tier: e.g. ["T1", "T2"].
- city, vendor, node, interface, ring: as written in the question.
- link_type: from <<LINK_TYPES>>.
- link_subtype: from <<LINK_SUBTYPES>>  ("4G NNI" -> link_type MPLS-EPT-NPT-NNI, link_subtype 4G).
- flag: from <<FLAGS>>.
- min_util_pct: "on links above 30% utilization" -> 30.
- min_change_kbps: "that lost at least 100 Mbps" -> 100000 (Kbps).
- limit: "top 10" -> 10.
- unit: "bps" / "kbps" / "mbps" / "gbps", only when the user asks for a unit.
- with_series: true when the user asks for a graph, chart, plot or trend.

Examples:
Q: which links dipped more than 40% in the last 2 hours
A: {"direction": "dip", "threshold_pct": 40, "time_in_question": true, "window_hours": 2}
Q: show traffic dip of more than 5 %
A: {"direction": "dip", "threshold_pct": 5, "time_in_question": false}
Q: T5-Ring surges in Maharashtra above 50% with a graph
A: {"direction": "surge", "threshold_pct": 50, "time_in_question": false, "link_type": ["T5-Ring"], "circle": ["Maharashtra"], "with_series": true}
Q: top 10 Cisco interfaces whose inbound traffic fell between 30 and 60 percent
A: {"direction": "dip", "pct_range": [30, 60], "time_in_question": false, "vendor": ["Cisco"], "metric": "in", "limit": 10}

Q: <<QUESTION>>
A:"""


def slot_prompt(question, latest):
    latest = latest.replace(microsecond=0)
    return (_PROMPT
            .replace("<<LATEST>>", str(latest))
            .replace("<<LATEST_HM>>", latest.strftime("%Y-%m-%d %H:%M"))
            .replace("<<DAY>>", latest.strftime("%Y-%m-%d"))
            .replace("<<LINK_TYPES>>", ", ".join(LINK_TYPES))
            .replace("<<LINK_SUBTYPES>>", ", ".join(LINK_SUBTYPES))
            .replace("<<FLAGS>>", ", ".join(FLAGS))
            .replace("<<QUESTION>>", " ".join(str(question).split())))


def parse_json(text):
    """LLM text -> dict or None. Tolerates ```json fences and text around the object."""
    if not text:
        return None
    s = re.sub(r"^```(?:json)?|```$", "", str(text).strip(), flags=re.I | re.M).strip()
    try:
        obj = json.loads(s)
    except ValueError:
        m = re.search(r"\{.*\}", s, re.S)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
        except ValueError:
            return None
    return obj if isinstance(obj, dict) else None


def _num(v):
    """Positive finite number, else None (0 / '' / junk mean 'not given')."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) and f > 0 else None


def _dt(v):
    if not v:
        return None
    s = str(v).strip().replace("T", " ").rstrip("Z")
    try:
        return datetime.fromisoformat(s[:19]).replace(microsecond=0)
    except ValueError:
        return None


def _canon(vals, known):
    """Case-insensitive match to a known list -> (canonical values, unknown values)."""
    by_key = {re.sub(r"[^a-z0-9]", "", k.lower()): k for k in known}
    good, bad = [], []
    for v in vals:
        k = by_key.get(re.sub(r"[^a-z0-9]", "", v.lower()))
        (good if k else bad).append(k or v)
    return good, bad


def _is_true(v):
    return v is True or str(v).strip().lower() == "true"


def clean_slots(obj, latest):
    """LLM JSON -> (slots, warnings). slots keys: direction, one threshold key, time,
    level, metric, unit, limit, min_util_pct, min_change_kbps, with_series, filters."""
    slots, warnings = {}, []
    slots["direction"] = "surge" if str(obj.get("direction", "")).lower() == "surge" else "dip"

    # threshold: first valid of range, ceiling, around, floor
    chosen = None
    rng = obj.get("pct_range")
    if isinstance(rng, (list, tuple)) and len(rng) == 2:
        lo, hi = _num(rng[0]), _num(rng[1])
        if lo and hi:
            lo, hi = sorted((lo, hi))
            if hi <= 100:
                chosen = ("pct_range", [lo, hi])
    for key in ("max_pct", "around_pct", "threshold_pct"):
        if chosen:
            break
        v = _num(obj.get(key))
        if v is not None:
            if v <= 100:
                chosen = (key, v)
            else:
                warnings.append(f"Ignored {key}={v}: a change cannot be over 100%.")
    if chosen:
        slots[chosen[0]] = chosen[1]

    # time
    s, e = _dt(obj.get("start")), _dt(obj.get("end"))
    wh = _num(obj.get("window_hours"))
    if s and e and e > s:
        slots["time"] = {"start": str(s), "end": str(e)}
    elif _is_true(obj.get("time_in_question")):
        if wh and wh <= 744:
            slots["time"] = {"window_hours": wh}
        elif s and not e and latest and s < latest:
            slots["time"] = {"start": str(s), "end": str(latest.replace(microsecond=0))}
        else:
            warnings.append("Could not read the time in the question; used the session or default window.")

    for key, allowed in (("level", LEVELS), ("metric", METRICS), ("unit", UNIT_LABEL)):
        v = str(obj.get(key) or "").lower()
        if v in allowed:
            slots[key] = v

    lim = _num(obj.get("limit"))
    if lim:
        slots["limit"] = max(1, min(int(lim), MAX_LIMIT))
    u = _num(obj.get("min_util_pct"))
    if u and u <= 100:
        slots["min_util_pct"] = u
    k = _num(obj.get("min_change_kbps"))
    if k:
        slots["min_change_kbps"] = k
    if _is_true(obj.get("with_series")):
        slots["with_series"] = True

    # filters: field -> {"op", "values"}
    filters = {}
    for key, col in FILTER_KEYS.items():
        vals = to_list(obj.get(key))
        if not vals:
            continue
        op = "in"
        if col == "Circle":
            vals = [circle_code(v)[0] for v in vals]
        elif col == "Tier":
            vals = [t for t in (tier_code(v) for v in vals) if t]
        elif col == "Vendor":
            vals = [v.upper() for v in vals]
        elif col in ("LinkType", "LinkSubType", "Flag"):
            known = {"LinkType": LINK_TYPES, "LinkSubType": LINK_SUBTYPES, "Flag": FLAGS}[col]
            vals, bad = _canon(vals, known)
            if bad:
                warnings.append(f"Ignored unknown {col} {', '.join(bad)}.")
        elif col == "Node Name" and len(vals) == 1 and vals[0].count("-") < 3:
            op = "like"                               # partial node name, e.g. 'MUM-PE'
        vals = list(dict.fromkeys(vals))
        if vals:
            filters[col] = {"op": op, "values": vals}
    if filters:
        slots["filters"] = filters
    return slots, warnings


def fallback_slots(question):
    """When the LLM is down or replies with junk: dip vs surge from the wording only."""
    q = str(question).lower()
    surge = any(w in q for w in ("surge", "spike", "rise", "rose", "increase", "jump"))
    return {"direction": "surge" if surge else "dip"}
