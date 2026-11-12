"""
dip_engine.py -- builds the dip / surge SQL. No LLM, no network calls, no state.
================================================================================
Extracted from Dip_Agent/dip.py (2026.09.04-4) and the helpers it used from
intent.py. For the same parameters it emits the same SQL as the agent, minus
the debug modes (--diag / --calibrate / --coverage) and the CEN / demo sources.

The method, per interface (or per group, see "level"):
    baseline = average of the previous N readings        (N = baseline_points, default 3)
    dip %    = (baseline - current) / baseline * 100      (surge = same, sign flipped)
A reading is judged only when it has N earlier readings and the baseline is above
the source's floor (base_floor_kbps), so near-idle ports do not flood the result.

SQL pipeline (one statement, MySQL 8 window functions):
    windowed  rows of the view in [lead_start, range_end], filters applied
    rated     traffic -> Kbps, plus the gap to the previous poll
    clean     drop readings whose gap is outside [gap_lo_s, gap_hi_s]
    grouped   (level != interface) sum ports per group per 5-min bucket
    stable    (level != interface) keep buckets where >= min_port_coverage of the
              group's ports reported, so a missing poll is not read as a dip
    rolled    trailing AVG over the previous N rows = the baseline
    final     dip% filter, optional utilization / absolute-loss filters, LIMIT
"""
import os
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Defaults (env overrides, same names the agent used)
# ---------------------------------------------------------------------------
DIP_MIN_DROP        = float(os.environ.get("QA_DIP_MIN_DROP", "20"))       # % when none given
DIP_BASELINE_POINTS = int(os.environ.get("QA_DIP_BASELINE_POINTS", "3"))
DIP_ABS_TOLERANCE   = float(os.environ.get("QA_DIP_ABS_TOLERANCE", "5"))   # "around X%" = X +/- 5
MAX_LIMIT           = int(os.environ.get("QA_ROW_LIMIT", "500"))

METRICS    = ("in", "out", "max", "sum", "either")
LEVELS     = ("interface", "node", "city", "circle", "linktype", "vendor", "tier", "ring")
FILTER_OPS = ("=", "!=", "like", "in", ">", "<", ">=", "<=")

# ---------------------------------------------------------------------------
# Sources. A source is a view with these column names (see sql/ in Dip_Agent
# for the CREATE VIEW). `In Traffic` / `Out Traffic` are already a rate in bps.
# ---------------------------------------------------------------------------
_DIMS = ["Circle", "Tier", "City", "Vendor", "LinkType",
         "LinkSubType", "Flag", "Class", "Oper Status", "Admin Status"]
_FREE_TEXT = ["Node Name", "Interface Name", "Interface Alias", "Ring Name"]
_LEVEL_COLS = {"node": "`Node Name`", "city": "`City`", "circle": "`Circle`",
               "linktype": "`LinkType`", "vendor": "`Vendor`",
               "tier": "`Tier`", "ring": "`Ring Name`"}


def _mpls_source(table, anchor_table):
    return {
        "table": table,                          # the view
        "anchor_table": anchor_table,            # base table: MAX(Time_1) = "now"
        "anchor_time_col": "Time_1",
        "cols": {"node": "`Node Name`", "iface": "`Interface Name`",
                 "in": "`In Traffic`", "out": "`Out Traffic`",
                 "bw": "`BW(Kb)`", "time": "`Time`", "key": "`Port ID`"},
        "partition": ["`Port ID`"],
        "carry": ["`LinkType`", "`Circle`", "`Tier`", "`Vendor`", "`Flag`"],
        "display_unit": "mbps",
        "bw_unit": "kb",                         # BW(Kb): 100G = 100000000
        "poll_interval_s": 300,
        "gap_lo_s": 30, "gap_hi_s": 1800,        # reject only nonsense gaps
        "bucket_seconds": 300,
        "base_floor_kbps": 50,
        "min_port_coverage": 0.80,
        "max_exec_ms": 120000,
        "dims": list(_DIMS),
        "free_text": list(_FREE_TEXT),
        "levels": dict(_LEVEL_COLS),
    }


SOURCES = {
    # Vegayan_MPLS: mpls_traffic_raw is built on ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B.
    # DEMO_MPLS: network links are in ROUTERTRAFFIC_VLANPRT_SCALE1_TBL, so set
    #   DIP_MPLS_ANCHOR=ROUTERTRAFFIC_VLANPRT_SCALE1_TBL there.
    "mpls": _mpls_source(
        os.environ.get("DIP_MPLS_VIEW", "mpls_traffic_raw"),
        os.environ.get("DIP_MPLS_ANCHOR", "ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B")),
    # DEMO_MPLS only: B2B customer ports (view mpls_b2b_traffic_raw).
    "mpls_b2b": _mpls_source(
        os.environ.get("DIP_B2B_VIEW", "mpls_b2b_traffic_raw"),
        os.environ.get("DIP_B2B_ANCHOR", "ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B")),
}


def source_columns(src):
    """Columns a filter may use."""
    return list(src["dims"]) + list(src["free_text"])


# ---------------------------------------------------------------------------
# Units. Inside the SQL every rate is Kbps; output is scaled to the asked unit.
# ---------------------------------------------------------------------------
UNIT_BPS = {"bps": 1.0, "kbps": 1e3, "mbps": 1e6, "gbps": 1e9}
UNIT_LABEL = {"bps": "bps", "kbps": "Kbps", "mbps": "Mbps", "gbps": "Gbps"}
_BW_TO_KBPS = {"kb": 1.0, "kbps": 1.0, "bps": 0.001, "mb": 1000.0}


def _disp(expr, to_u):
    """Kbps expression -> ROUND(expr in `to_u`)."""
    f = UNIT_BPS["kbps"] / UNIT_BPS[to_u]
    dp = {1e-9: 6, 1e-6: 4, 1e-3: 3}.get(f, 2)
    inner = expr if f == 1.0 else f"({expr}) * {f:g}"
    return f"ROUND({inner}, {dp})"


def _util_expr(src, cur):
    b = _BW_TO_KBPS[src.get("bw_unit", "kb")]
    den = "bw_val" if b == 1.0 else f"bw_val * {b:g}"
    return f"{cur} / NULLIF({den}, 0) * 100"


# ---------------------------------------------------------------------------
# Filters and thresholds
# ---------------------------------------------------------------------------
def build_filter_sql(filters, allowed_columns):
    """[{column, op, value}] -> ("AND `col` = %s ...", [params]).
    Columns are checked against the whitelist; values are always parameters."""
    allowed = set(allowed_columns or [])
    frags, params = [], []
    for f in filters or []:
        col, op, val = f.get("column"), f.get("op", "="), f.get("value")
        if col not in allowed or op not in FILTER_OPS:
            continue
        if op == "in":
            vals = [v for v in (val if isinstance(val, list) else [val]) if v is not None]
            if not vals:
                continue
            frags.append(f"AND `{col}` IN ({', '.join(['%s'] * len(vals))})")
            params.extend(vals)
        elif op == "like":
            frags.append(f"AND `{col}` LIKE %s")
            params.append(f"%{val}%")
        else:
            frags.append(f"AND `{col}` {op} %s")
            params.append(val)
    return "\n    ".join(frags), params


def drop_clause(mode, expr, direction="dip"):
    """dip% predicate. A surge is a negative dip%, so only the inequality flips."""
    if mode in ("range", "absolute"):
        return f"{expr} BETWEEN %s AND %s"
    if direction == "surge":
        return f"{expr} >= %s" if mode == "ceiling" else f"{expr} <= %s"
    return f"{expr} <= %s" if mode == "ceiling" else f"{expr} >= %s"


def drop_params(mode, lo, hi, direction="dip"):
    """Parameters for drop_clause(); negated (and swapped) for surges."""
    if direction == "surge":
        if mode == "range":
            return [-(hi if hi is not None else lo), -(lo if lo is not None else hi)]
        if mode == "ceiling":
            return [-hi]
        if mode == "absolute":
            return [-(lo + DIP_ABS_TOLERANCE), -(hi - DIP_ABS_TOLERANCE)]
        return [-lo]
    if mode == "range":
        return [lo, hi]
    if mode == "ceiling":
        return [hi]
    if mode == "absolute":
        return [lo - DIP_ABS_TOLERANCE, hi + DIP_ABS_TOLERANCE]
    return [lo]


def describe(p):
    """One-line summary of what was applied, for the UI / logs."""
    w = "surge" if p.get("direction") == "surge" else "dip"
    mode = p.get("drop_mode", "floor")
    if mode == "range":
        bits = [f"{w} {p['drop_lo']:.0f}-{p['drop_hi']:.0f}%"]
    elif mode == "ceiling":
        bits = [f"{w} <= {p['drop_hi']:.0f}%"]
    elif mode == "absolute":
        bits = [f"{w} ~{p['drop_lo']:.0f}% (+/-{DIP_ABS_TOLERANCE:.0f}pt)"]
    else:
        bits = [f"{w} >= {p['drop_lo']:.0f}%"]
    if p.get("window_resolved"):
        bits.append(f"{p['window_resolved'][0]} .. {p['window_resolved'][1]}")
    bits.append(", ".join(f"{f['column']}{f['op']}{f['value']}" for f in p["filters"])
                if p.get("filters") else "all links")
    if p.get("want_high_util"):
        bits.append(f"util >= {p['high_util_pct']:.0f}%")
    bits.append(f"metric={p.get('metric', 'either')}")
    return " | ".join(bits)


# ---------------------------------------------------------------------------
# Time window
# ---------------------------------------------------------------------------
def latest_time(con, src):
    """Newest poll in the anchor table (the data may be historical)."""
    cur = con.cursor()
    cur.execute(f"SELECT MAX(`{src['anchor_time_col']}`) FROM {src['anchor_table']}")
    latest = cur.fetchone()[0]
    cur.close()
    if latest is None:
        raise RuntimeError(f"{src['anchor_table']} is empty")
    return latest


def window_last_hours(latest, hours, src, baseline_points):
    """(lead_start, range_start, range_end) for 'the last N hours of data'.
    lead_start reaches back far enough for the first reading to have a baseline."""
    lead = timedelta(seconds=(baseline_points + 2) * src["poll_interval_s"])
    start = latest - timedelta(hours=hours)
    return start - lead, start, latest


def window_between(start, end, src, baseline_points):
    lead = timedelta(seconds=(baseline_points + 2) * src["poll_interval_s"])
    return start - lead, start, end


# ---------------------------------------------------------------------------
# The dip SQL
# ---------------------------------------------------------------------------
def build_dip_sql(src, p, filter_sql, filter_params, window):
    """Return (sql, params). `p` keys:
        direction ('dip'|'surge'), drop_mode ('floor'|'ceiling'|'range'|'absolute'),
        drop_lo, drop_hi, metric (METRICS), level (LEVELS), baseline_points,
        want_high_util, high_util_pct, min_drop_abs (Kbps or None),
        display_rate_unit (UNIT_LABEL key or None), limit.
    Sets p['display_unit_effective'], p['level_effective'], p['window_resolved'],
    and appends to p['notes'] when it has to fall back."""
    c, bp, metric = src["cols"], p["baseline_points"], p["metric"]
    floor = src.get("base_floor_kbps", 0)
    surge = p.get("direction") == "surge"
    CH, MOVED = ("Surge", "Gain") if surge else ("Dip", "Lost")

    out_u = p.get("display_rate_unit") or src["display_unit"]
    if out_u not in UNIT_LABEL:
        out_u = src["display_unit"]
    p["display_unit_effective"] = out_u
    U = UNIT_LABEL[out_u]

    level = p.get("level", "interface")
    level_col = src["levels"].get(level)
    if level != "interface" and level_col is None:
        p.setdefault("notes", []).append(f"no '{level}' level on this source; used interface")
        level = "interface"
    grouping = level != "interface"
    p["level_effective"] = level

    part_cols = [x for x in src["partition"] if x not in src["carry"]]
    carry_list = list(src["carry"]) + part_cols
    if grouping and level_col not in carry_list:
        carry_list.append(level_col)
    carry_sel = (", ".join(carry_list) + ",") if carry_list else ""

    lead_start, range_start, range_end = window
    p["window_resolved"] = (str(range_start), str(range_end))

    # 1. rows in the window (+ the lead-in needed for the first baseline)
    windowed = f"""windowed AS (
    SELECT {carry_sel} {c['node']} AS node_name, {c['iface']} AS iface_name,
           {c['bw']} AS bw_val, {c['time']} AS ts,
           {c['in']} AS in_raw, {c['out']} AS out_raw,
           ({c['time']} >= %s) AS in_range
    FROM {src['table']}
    WHERE {c['time']} >= %s AND {c['time']} <= %s
    {filter_sql}
)"""
    params = [range_start, lead_start, range_end] + list(filter_params)

    # 2. bps -> Kbps; the gap to the previous poll is a data-quality filter only
    rate_stage = f""",
rated AS (
    SELECT {carry_sel} node_name, iface_name, bw_val, ts, in_range,
           in_raw  / 1000 AS in_kbps,
           out_raw / 1000 AS out_kbps,
           TIMESTAMPDIFF(SECOND, LAG(ts) OVER w, ts) AS gap_s
    FROM windowed
    WINDOW w AS (PARTITION BY {", ".join(src["partition"])} ORDER BY ts)
),
clean AS (
    SELECT * FROM rated
    WHERE gap_s BETWEEN {src['gap_lo_s']} AND {src['gap_hi_s']}
)"""
    base, in_col, out_col = "clean", "in_kbps", "out_kbps"

    # 3. optional grouping (circle / city / node / ...)
    if grouping:
        cov = src.get("min_port_coverage", 0.95)
        bucket = int(src.get("bucket_seconds") or src["poll_interval_s"])
        bucket_expr = f"FROM_UNIXTIME(FLOOR(UNIX_TIMESTAMP(ts) / {bucket}) * {bucket})"
        group_stage = f""",
grouped AS (
    SELECT {level_col} AS grp, {bucket_expr} AS ts, MAX(in_range) AS in_range,
           SUM({in_col}) AS in_kbps, SUM({out_col}) AS out_kbps,
           SUM(bw_val)   AS bw_val,
           COUNT(*)      AS port_n
    FROM {base}
    WHERE {level_col} IS NOT NULL
    GROUP BY {level_col}, {bucket_expr}
),
covered AS (
    SELECT g.*, MAX(port_n) OVER (PARTITION BY grp) AS peak_port_n
    FROM grouped g
),
stable AS (
    SELECT * FROM covered WHERE port_n >= peak_port_n * {cov}
)"""
        base, in_col, out_col = "stable", "in_kbps", "out_kbps"
        part_by, carry_roll = "grp", ""
        ident_sel = "    grp AS `Group`,\n    port_n AS `Ports`,\n"
        ident_cols = "grp, port_n"
    else:
        group_stage = ""
        part_by, carry_roll = ", ".join(src["partition"]), carry_sel
        ident_sel = ("    node_name AS `Node Name`,\n    iface_name AS `Interface Name`,\n"
                     + "".join(f"    {x},\n" for x in src["carry"]))
        ident_cols = "node_name, iface_name"

    # 4. baseline = average of the previous N readings
    frame = f"PARTITION BY {part_by} ORDER BY ts ROWS BETWEEN {bp} PRECEDING AND 1 PRECEDING"
    if metric == "either":                       # judge in and out separately
        rolled = f""",
rolled AS (
    SELECT {carry_roll} {ident_cols}, bw_val, ts, in_range,
           {in_col}  AS cur_in,  {out_col} AS cur_out,
           AVG({in_col})  OVER w AS base_in,
           AVG({out_col}) OVER w AS base_out,
           COUNT(*)       OVER w AS base_n
    FROM {base}
    WINDOW w AS ({frame})
)"""
        dip_in = f"CASE WHEN base_in  > {floor} THEN (base_in  - cur_in)  / base_in  * 100 END"
        dip_out = f"CASE WHEN base_out > {floor} THEN (base_out - cur_out) / base_out * 100 END"
        if surge:
            dip_expr = f"LEAST(COALESCE({dip_in}, 1e9), COALESCE({dip_out}, 1e9))"
            dir_case = (f"CASE WHEN COALESCE({dip_in}, 1e9) <= COALESCE({dip_out}, 1e9) "
                        f"THEN 'IN' ELSE 'OUT' END")
        else:
            dip_expr = f"GREATEST(COALESCE({dip_in}, -1e9), COALESCE({dip_out}, -1e9))"
            dir_case = (f"CASE WHEN COALESCE({dip_in}, -1e9) >= COALESCE({dip_out}, -1e9) "
                        f"THEN 'IN' ELSE 'OUT' END")
        cur_expr = "GREATEST(cur_in, cur_out)"
        have_base = f"(base_in > {floor} OR base_out > {floor})"
        detail = (f"    {_disp('base_in', out_u)}  AS `Baseline In ({U})`,\n"
                  f"    {_disp('cur_in', out_u)}   AS `Current In ({U})`,\n"
                  f"    {_disp('base_out', out_u)} AS `Baseline Out ({U})`,\n"
                  f"    {_disp('cur_out', out_u)}  AS `Current Out ({U})`,\n"
                  f"    {dir_case} AS `Direction`,\n")
        moved_expr = ("GREATEST(cur_in - base_in, cur_out - base_out)" if surge
                      else "GREATEST(base_in - cur_in, base_out - cur_out)")
    else:                                        # one series: in, out, max or sum
        expr = {"in": in_col, "out": out_col,
                "max": f"GREATEST({in_col}, {out_col})",
                "sum": f"({in_col} + {out_col})"}[metric]
        rolled = f""",
rolled AS (
    SELECT {carry_roll} {ident_cols}, bw_val, ts, in_range,
           {expr} AS cur_val,
           AVG({expr}) OVER w AS baseline_val,
           COUNT(*)    OVER w AS base_n
    FROM {base}
    WINDOW w AS ({frame})
)"""
        dip_expr = "(baseline_val - cur_val) / NULLIF(baseline_val, 0) * 100"
        cur_expr = "cur_val"
        have_base = f"baseline_val > {floor}"
        detail = (f"    {_disp('baseline_val', out_u)} AS `Baseline ({U})`,\n"
                  f"    {_disp('cur_val', out_u)}      AS `Current ({U})`,\n")
        moved_expr = "(cur_val - baseline_val)" if surge else "(baseline_val - cur_val)"

    pct_expr = f"-1 * ({dip_expr})" if surge else dip_expr     # a 60% surge reads 60
    min_lost = p.get("min_drop_abs") or 0
    lost_filter = f"AND {moved_expr} >= %s" if min_lost else ""
    util_expr = _util_expr(src, cur_expr)
    util_filter = f"AND {util_expr} >= %s" if p.get("want_high_util") else ""
    hint = f"/*+ MAX_EXECUTION_TIME({int(src['max_exec_ms'])}) */ " if src.get("max_exec_ms") else ""

    # 5. final selection
    sql = f"""WITH {windowed}{rate_stage}{group_stage}{rolled}
SELECT {hint}
{ident_sel}    ts AS `{CH} At`,
{detail}    ROUND({pct_expr}, 2) AS `{CH} %`,
    {_disp(moved_expr, out_u)} AS `{MOVED} ({U})`,
    ROUND({util_expr}, 2) AS `Current Utilization %`
FROM rolled
WHERE in_range = 1
  AND base_n = {bp}
  AND {have_base}
  AND {drop_clause(p['drop_mode'], dip_expr, p.get('direction', 'dip'))}
  {lost_filter}
  {util_filter}
ORDER BY `{CH} %` DESC
LIMIT %s"""

    params += drop_params(p["drop_mode"], p["drop_lo"], p["drop_hi"], p.get("direction", "dip"))
    if min_lost:
        params.append(min_lost)
    if p.get("want_high_util"):
        params.append(p["high_util_pct"])
    params.append(p["limit"])
    return sql, params


# ---------------------------------------------------------------------------
# Traffic points around each dip, for charts (optional)
# ---------------------------------------------------------------------------
SERIES_LEAD = int(os.environ.get("QA_SERIES_LEAD", "4"))     # points before the dip
SERIES_LAG = int(os.environ.get("QA_SERIES_LAG", "3"))       # points after the dip


def build_series_sql(src, pairs, t_lo, t_hi):
    """Points for (node, interface) pairs, cleaned exactly like build_dip_sql."""
    c = src["cols"]
    extra = [x for x in src["partition"] if x not in (c["node"], c["iface"])]
    part_sel = (", ".join(extra) + ",") if extra else ""
    part_by = ", ".join(src["partition"])
    pair_ph = ", ".join(["(%s, %s)"] * len(pairs))
    sql = f"""WITH windowed AS (
    SELECT {part_sel} {c['node']} AS node_name, {c['iface']} AS iface_name,
           {c['time']} AS ts, {c['in']} AS in_raw, {c['out']} AS out_raw
    FROM {src['table']}
    WHERE {c['time']} >= %s AND {c['time']} <= %s
      AND ({c['node']}, {c['iface']}) IN ({pair_ph})
),
rated AS (
    SELECT node_name, iface_name, ts,
           in_raw / 1000 AS in_kbps, out_raw / 1000 AS out_kbps,
           TIMESTAMPDIFF(SECOND, LAG(ts) OVER w, ts) AS gap_s
    FROM windowed
    WINDOW w AS (PARTITION BY {part_by} ORDER BY ts)
),
clean AS (
    SELECT * FROM rated WHERE gap_s BETWEEN {src['gap_lo_s']} AND {src['gap_hi_s']}
)
SELECT node_name, iface_name, ts, in_kbps, out_kbps
FROM clean
ORDER BY node_name, iface_name, ts"""
    params = [t_lo, t_hi]
    for node, iface in pairs:
        params += [node, iface]
    return sql, params


def dip_series(con, src, p, rows):
    """For interface-level results: the traffic around each dip, in the display
    unit. Returns {"unit", "points": [{dip_key, node, interface, time, in, out,
    in_baseline, is_dip}, ...]} or None."""
    if not rows or p.get("level_effective") != "interface":
        return None
    at_col = next((k for k in rows[0] if k.endswith(" At")), None)
    if at_col is None:
        return None
    bp = p["baseline_points"]
    lead, lag = max(SERIES_LEAD, bp + 1), SERIES_LAG
    poll = src["poll_interval_s"]

    def parse(s):
        return datetime.strptime(str(s)[:19], "%Y-%m-%d %H:%M:%S")

    pairs = sorted({(r["Node Name"], r["Interface Name"]) for r in rows})
    times = [parse(r[at_col]) for r in rows]
    t_lo = min(times) - timedelta(seconds=(lead + 2) * poll)
    t_hi = max(times) + timedelta(seconds=(lag + 1) * poll)

    sql, params = build_series_sql(src, pairs, t_lo, t_hi)
    cur = con.cursor()
    cur.execute(sql, params)
    by_iface = {}
    for node, iface, ts, i_k, o_k in cur.fetchall():
        by_iface.setdefault((node, iface), []).append((str(ts), float(i_k or 0), float(o_k or 0)))
    cur.close()

    out_u = p.get("display_unit_effective") or src["display_unit"]
    f = UNIT_BPS["kbps"] / UNIT_BPS[out_u]
    points = []
    for r in rows:
        key = (r["Node Name"], r["Interface Name"])
        seq = by_iface.get(key) or []
        dip_at = str(r[at_col])[:19]
        idx = next((n for n, s in enumerate(seq) if s[0][:19] == dip_at), None)
        if idx is None:
            continue
        for n in range(max(0, idx - lead), min(len(seq), idx + lag + 1)):
            ts, i_k, o_k = seq[n]
            off = n - idx
            points.append({"dip_key": f"{key[0]}|{key[1]}|{dip_at}", "node": key[0],
                           "interface": key[1], "time": ts,
                           "in": round(i_k * f, 4), "out": round(o_k * f, 4),
                           "in_baseline": -bp <= off <= -1, "is_dip": off == 0})
    return {"unit": UNIT_LABEL[out_u], "group_by": "dip_key", "points": points} if points else None
