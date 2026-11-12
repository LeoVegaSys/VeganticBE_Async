"""
scope.py -- the UI's global filters (session scope) and how they combine with
what the LLM read from the question.

Rules:
  * Network, circle and tier from the UI are hard limits. The question can narrow
    inside them, never widen them.
  * Time: a time stated in the question wins; otherwise the session's date/time
    window; otherwise the last DIP_DEFAULT_WINDOW_HOURS of data.
  * Services: read and reported, not applied yet (APPLY_SERVICES = False).

Accepted filter keys (camelCase from the UI, snake_case from ai_db.chat_sessions):
    networks, levels, circle, services, dateFrom/date_from, dateTo/date_to,
    timeStart/time_start, timeEnd/time_end   (and 'date' for a single day)
Values may be lists, JSON strings ('["MH","AP"]') or comma-separated text.
"""
import json
import re
from datetime import date, datetime, time, timedelta, timezone

from src.dip_new.config import (
    APPLY_SERVICES, CIRCLE_CODES, DEFAULT_SOURCE, DIP_DEFAULT_WINDOW_HOURS,
    NETWORK_TO_SOURCE, UI_TZ_OFFSET_MINUTES,
)

_CODES = set(CIRCLE_CODES.values())
_LOCAL_TZ = timezone(timedelta(minutes=UI_TZ_OFFSET_MINUTES))


def norm_key(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def to_list(v):
    """list / JSON text / 'a, b' -> ['a', 'b']; 'All' and blanks are dropped."""
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        items = list(v)
    else:
        s = str(v).strip()
        if not s:
            return []
        if s[0] == "[":
            try:
                j = json.loads(s)
                if isinstance(j, list):
                    return to_list(j)
            except ValueError:
                pass
        items = re.split(r"[,;|]", s)
    out = []
    for x in items:
        if isinstance(x, dict):
            x = x.get("value") or x.get("code") or x.get("label") or x.get("name")
        if x is None:
            continue
        x = str(x).strip().strip("'\"[]").strip()
        if x and x.lower() not in ("all", "any", "none", "null"):
            out.append(x)
    return list(dict.fromkeys(out))


def circle_code(v):
    """'Maharashtra' -> ('MH', True); 'mh' -> ('MH', True); 'Xyz' -> ('XYZ', False)."""
    s = str(v).strip()
    if s.upper() in _CODES:
        return s.upper(), True
    code = CIRCLE_CODES.get(norm_key(s))
    if code:
        return code, True
    return (s.upper() if re.fullmatch(r"[A-Za-z]{2,5}", s) else s), False


def tier_code(v):
    """'T1', 't1', 'Tier 1', 'Tier-1', '1' -> 'T1'; anything else -> None."""
    m = re.fullmatch(r"(?:t|tier)?\s*[-_ ]?\s*([1-9])", str(v).strip(), re.I)
    return f"T{m.group(1)}" if m else None


# ---------------------------------------------------------------------------
# Dates and times from the UI
# ---------------------------------------------------------------------------
_DATE_FMTS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%d-%b-%Y")
_TIME_FMTS = ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I %p", "%I%p", "%H%M")


def _local(dt):
    return dt.astimezone(_LOCAL_TZ).replace(tzinfo=None) if dt.tzinfo else dt


def parse_date(v):
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return _local(v).date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    try:
        return _local(datetime.fromisoformat(s.replace("Z", "+00:00"))).date()
    except ValueError:
        pass
    for f in _DATE_FMTS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            continue
    raise ValueError(f"unreadable date {v!r}")


def parse_time(v):
    if v in (None, ""):
        return None
    if isinstance(v, time):
        return v.replace(microsecond=0)
    if isinstance(v, timedelta):                      # MySQL TIME via aiomysql
        secs = int(v.total_seconds()) % 86400
        return time(secs // 3600, secs % 3600 // 60, secs % 60)
    if isinstance(v, datetime):
        return _local(v).time().replace(microsecond=0)
    s = str(v).strip().upper()
    for f in _TIME_FMTS:
        try:
            return datetime.strptime(s, f).time()
        except ValueError:
            continue
    try:
        return _local(datetime.fromisoformat(s.replace("Z", "+00:00"))).time().replace(microsecond=0)
    except ValueError:
        raise ValueError(f"unreadable time {v!r}")


def _first(raw, *keys):
    for k in keys:
        v = raw.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def parse_ui_filters(raw):
    """Raw UI / chat_sessions filters -> (ui dict of plain strings, warnings)."""
    raw = raw or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = {}
    warnings = []
    ui = {
        "networks": to_list(_first(raw, "networks", "network")),
        "levels":   to_list(_first(raw, "levels", "level", "tiers", "tier")),
        "circles":  to_list(_first(raw, "circle", "circles")),
        "services": to_list(_first(raw, "services", "service")),
    }
    for key, names, parse in (
            ("date_from",  ("dateFrom", "date_from", "date"), parse_date),
            ("date_to",    ("dateTo", "date_to", "date"), parse_date),
            ("time_start", ("timeStart", "time_start", "timeFrom", "time_from"), parse_time),
            ("time_end",   ("timeEnd", "time_end", "timeTo", "time_to"), parse_time)):
        v = _first(raw, *names)
        try:
            p = parse(v)
            ui[key] = p.isoformat() if p else None
        except ValueError as e:
            ui[key] = None
            warnings.append(f"Session {key.replace('_', ' ')} ignored: {e}.")
    return ui, warnings


def ui_window(ui, latest):
    """Session date/time -> (start, end) datetimes, or None when the UI set no time.
    Only a time -> that slot on the newest data's day. Only dates -> whole days."""
    d_from = date.fromisoformat(ui["date_from"]) if ui.get("date_from") else None
    d_to = date.fromisoformat(ui["date_to"]) if ui.get("date_to") else None
    t_s = time.fromisoformat(ui["time_start"]) if ui.get("time_start") else None
    t_e = time.fromisoformat(ui["time_end"]) if ui.get("time_end") else None
    if not any((d_from, d_to, t_s, t_e)):
        return None
    d_from = d_from or d_to or latest.date()
    d_to = d_to or d_from
    start = datetime.combine(d_from, t_s or time(0, 0))
    end = datetime.combine(d_to, t_e or time(23, 59, 59))
    if end <= start and t_s and t_e and d_from == d_to:     # 23:00 - 01:00 crosses midnight
        end += timedelta(days=1)
    if end <= start:
        raise ValueError(f"session window end {end} is not after start {start}")
    return start, end


# ---------------------------------------------------------------------------
# Network -> source
# ---------------------------------------------------------------------------
def resolve_source(ui):
    """(source, warnings, error). No network chosen -> DEFAULT_SOURCE."""
    nets = ui.get("networks") or []
    if not nets:
        return DEFAULT_SOURCE, [], None
    mapped, skipped = [], []
    for n in nets:
        s = NETWORK_TO_SOURCE.get(norm_key(n))
        if s:
            mapped.append(s)
        else:
            skipped.append(n)
    if not mapped:
        return None, [], (f"Dips are available only for the MPLS network for now; "
                          f"this session is set to {', '.join(nets)}.")
    warnings = ([f"Dips are not available yet for {', '.join(skipped)}; showing MPLS only."]
                if skipped else [])
    return mapped[0], warnings, None


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------
def _limit_to(col, label, q_vals, ui_vals, filters, warnings):
    """Apply a session limit: intersect with the question's values, else use the session's."""
    if not ui_vals:
        return
    if q_vals:
        inter = [v for v in q_vals if v in ui_vals]
        if inter:
            filters[col] = {"op": "in", "values": inter}
            return
        warnings.append(f"The question asks for {label} {', '.join(q_vals)}, but this session "
                        f"is limited to {', '.join(ui_vals)}; used the session's {label}.")
    filters[col] = {"op": "in", "values": list(ui_vals)}


def merge_scope(ui, slots, latest):
    """UI scope + LLM slots -> (tool args, warnings, scope_used)."""
    warnings = []
    args = {k: v for k, v in (slots or {}).items() if k not in ("filters", "time")}
    filters = {c: dict(f) for c, f in ((slots or {}).get("filters") or {}).items()}

    # circle
    ui_circles = []
    for c in ui.get("circles") or []:
        code, known = circle_code(c)
        if not known:
            warnings.append(f"Circle {c!r} is not in the circle list; used {code!r} as given.")
        ui_circles.append(code)
    ui_circles = list(dict.fromkeys(ui_circles))
    _limit_to("Circle", "circle", (filters.get("Circle") or {}).get("values"),
              ui_circles, filters, warnings)

    # tier (the UI calls it "Hierarchical level")
    ui_tiers = []
    for t in ui.get("levels") or []:
        code = tier_code(t)
        if code:
            ui_tiers.append(code)
        else:
            warnings.append(f"Level {t!r} is not a tier (T1..T5); ignored.")
    ui_tiers = list(dict.fromkeys(ui_tiers))
    _limit_to("Tier", "tier", (filters.get("Tier") or {}).get("values"),
              ui_tiers, filters, warnings)

    # services: on hold
    if ui.get("services") and not APPLY_SERVICES:
        warnings.append(f"The services filter ({', '.join(ui['services'])}) is not applied to dips yet.")

    # time
    try:
        session_win = ui_window(ui, latest)
    except ValueError as e:
        session_win = None
        warnings.append(f"Session time window ignored: {e}.")
    q_time = (slots or {}).get("time")
    if q_time:
        args.update(q_time)
        if session_win:
            warnings.append(f"Used the time in the question instead of the session window "
                            f"({session_win[0]} to {session_win[1]}).")
    elif session_win:
        args["start"], args["end"] = str(session_win[0]), str(session_win[1])
        if session_win[0] > latest:
            warnings.append(f"The session window starts after the newest data ({latest}).")
    else:
        args["window_hours"] = DIP_DEFAULT_WINDOW_HOURS

    # filters -> engine format
    out = []
    for col, f in filters.items():
        vals = [v for v in f.get("values") or [] if v not in (None, "")]
        if not vals:
            continue
        if f.get("op") == "like":
            if len(vals) > 1:
                warnings.append(f"Only the first {col} pattern ({vals[0]}) was used.")
            out.append({"column": col, "op": "like", "value": vals[0]})
        elif len(vals) == 1:
            out.append({"column": col, "op": "=", "value": vals[0]})
        else:
            out.append({"column": col, "op": "in", "value": vals})
    args["filters"] = out

    scope_used = {
        "networks": ui.get("networks") or [],
        "circles": ui_circles, "tiers": ui_tiers,
        "services_not_applied": ui.get("services") or [],
        "session_window": [str(session_win[0]), str(session_win[1])] if session_win else None,
        "time_from": "question" if q_time else ("session" if session_win else "default"),
    }
    return args, warnings, scope_used
