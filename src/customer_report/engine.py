"""
engine.py -- customer traffic report SQL (from CustomerTrafFilter_reporting_hist).

build_report_sql(args, tables) -> (sql, params, meta)

One SELECT (CTEs, MySQL 8, ONLY_FULL_GROUP_BY safe). No temp tables, no OUTFILE,
no session settings, so it runs through the read-only MCP arun_query.

    cust  active customer ports (RemoveTime NULL, PortID > 0, IfSpeed > 0, LSI > 100,
          no loopback), filtered, ONE row per PortID (newest ProvisionTime)
    s     5-minute samples per port in [start, end): max / avg / sum, threshold and
          100% counts, peak time
    r     per-port numbers: Kbps, MB, utilization % (traffic / subscribed bandwidth)
    f     + flags: upgrade, saturated, over-subscribed, underutilized, has data
    then  circuits | customers | locations | totals | hourly

Units: traffic columns are bps; IfSpeed is the subscribed bandwidth in Kb.
    util %  = bps / (IfSpeed * 1000) * 100 = bps / (IfSpeed * 10)
    volume  = SUM(bps) * POLL_SECONDS / 8 bytes -> MB
Every value goes in as a %s parameter; column names come only from this file.
"""
from src.customer_report.config import (
    HOURLY_MAX_ROWS, LOCATION_ALIASES, MAX_LIMIT, OVER_SUBSCRIBED_PCT, POLL_SECONDS,
    SATURATED_MIN_SAMPLES, SATURATION_PCT, THRESHOLD_PCT, UNDERUTILIZED_PCT,
    UPGRADE_MIN_PEAK_PCT, UPGRADE_MIN_SHARE,
)

REPORTS = ("circuits", "customers", "locations", "totals", "hourly")
ONLY = ("upgrade", "breach", "saturated", "underutilized", "over_subscribed", "no_data")
SORTS = ("utilization", "avg_utilization", "exceed", "saturation", "volume", "traffic",
         "time_above", "upgrade")
NLD = ("include", "exclude", "only")
HOURLY_BY = ("circuit", "customer")

# --- per-port sort keys (columns of f) and per-group sort keys -----------------------
_SORT_PORT = {
    "utilization": "f.max_util", "avg_utilization": "f.avg_util", "exceed": "f.exceed_cnt",
    "saturation": "f.full_cnt", "volume": "(f.vol_in_mb + f.vol_out_mb)",
    "traffic": "GREATEST(f.max_in_kbps, f.max_out_kbps)", "time_above": "f.pct_over_thr",
    "upgrade": "f.pct_over_thr",
}
_SORT_GROUP = {          # aggregate expressions (not aliases) so ORDER BY is unambiguous
    "utilization": "MAX(f.max_util)", "avg_utilization": "AVG(f.avg_util)",
    "exceed": "SUM(f.exceed_cnt)", "saturation": "SUM(f.full_cnt)",
    "volume": "SUM(COALESCE(f.vol_in_mb, 0) + COALESCE(f.vol_out_mb, 0))",
    "traffic": "MAX(f.max_util)", "time_above": "SUM(f.exceed_cnt)",
    "upgrade": "SUM(f.upgrade)",
}
# default sort and direction for each "only"
_DEFAULT_SORT = {
    None: ("utilization", "desc"), "upgrade": ("upgrade", "desc"), "breach": ("exceed", "desc"),
    "saturated": ("saturation", "desc"), "underutilized": ("avg_utilization", "asc"),
    "over_subscribed": ("utilization", "desc"), "no_data": ("utilization", "desc"),
}
_ONLY_WHERE = {
    "upgrade": "f.upgrade = 1", "breach": "f.exceed_cnt > 0", "saturated": "f.saturated = 1",
    "underutilized": "f.underutil = 1", "over_subscribed": "f.over_sub = 1",
    "no_data": "f.samples = 0",
}
_ONLY_LABEL = {
    "upgrade": "needing a bandwidth upgrade", "breach": f"above the threshold at least once",
    "saturated": "that reached 100% of the subscribed bandwidth",
    "underutilized": f"below {UNDERUTILIZED_PCT}% average utilization (downgrade candidates)",
    "over_subscribed": f"peaking above {OVER_SUBSCRIBED_PCT}% of the subscribed bandwidth",
    "no_data": "with no traffic data",
}


def _location_case(col):
    """SQL CASE that merges the stored spellings of one place (NEW DELHI / Delhi)."""
    groups, seen = [], set()
    for variants in LOCATION_ALIASES.values():
        key = tuple(sorted(v.upper() for v in variants))
        if len(variants) > 1 and key not in seen:
            seen.add(key)
            groups.append(variants)
    if not groups:
        return col, []
    parts, params = ["CASE"], []
    for v in groups:
        parts.append(f" WHEN UPPER({col}) IN ({', '.join(['%s'] * len(v))}) THEN %s")
        params += [x.upper() for x in v] + [v[0]]
    parts.append(f" ELSE {col} END")
    return "".join(parts), params


def _customer_where(a, tables):
    """WHERE parts on CUSTOMER_VRF_TBL c (and the inventory table) -> (sql, params)."""
    w, p = [], []
    flt = a.get("filters") or {}

    if flt.get("customer"):
        ors = []
        for v in flt["customer"]:
            ors.append("(c.VpnName = %s OR c.CustomerFullName LIKE CONCAT('%', %s, '%')"
                       " OR c.CircuitID LIKE CONCAT(%s, '-%'))")
            p += [v, v, v]
        w.append("(" + " OR ".join(ors) + ")")
    if flt.get("lsi"):
        w.append(f"c.LSI IN ({', '.join(['%s'] * len(flt['lsi']))})")
        p += list(flt["lsi"])
    if flt.get("circuit_id"):
        ors = []
        for v in flt["circuit_id"]:
            if v.count("-") >= 3:
                ors.append("c.CircuitID = %s")
                p.append(v)
            else:
                ors.append("c.CircuitID LIKE CONCAT('%', %s, '%')")
                p.append(v)
        w.append("(" + " OR ".join(ors) + ")")
    if flt.get("vrf"):
        ors = []
        for v in flt["vrf"]:
            ors.append("(c.VrfName = %s OR c.VrfName LIKE CONCAT('%', %s, '%'))")
            p += [v, v]
        w.append("(" + " OR ".join(ors) + ")")
    if flt.get("location"):
        w.append(f"c.Location IN ({', '.join(['%s'] * len(flt['location']))})")
        p += list(flt["location"])
    if flt.get("node"):
        ors = []
        for v in flt["node"]:
            ors.append("c.NodeName LIKE CONCAT('%', %s, '%')")
            p.append(v)
        w.append("(" + " OR ".join(ors) + ")")
    if flt.get("interface"):
        w.append(f"c.IfDescr IN ({', '.join(['%s'] * len(flt['interface']))})")
        p += list(flt["interface"])

    nld = a.get("nld") or "include"
    if nld == "only":
        w.append("c.CircuitID LIKE '%-NLD-%'")
    elif nld == "exclude":
        w.append("c.CircuitID NOT LIKE '%-NLD-%'")

    inv = tables.get("inventory")
    for key, col in (("circles", "ACircle"), ("tiers", "ATier")):
        vals = a.get(key) or []
        if vals and inv:
            w.append(f"EXISTS (SELECT 1 FROM {inv} n WHERE n.APortID = c.PortID "
                     f"AND n.{col} IN ({', '.join(['%s'] * len(vals))}))")
            p += list(vals)

    sql = "".join(f"\n      AND {x}" for x in w)
    return sql, p


def _base_ctes(a, tables):
    """cust, s, r, f CTEs -> (sql, params)."""
    thr = float(a.get("threshold_pct") or THRESHOLD_PCT)
    cw, cp = _customer_where(a, tables)
    cust_t, traf_t = tables["customers"], tables["traffic"]
    params = [a["end"]] + cp

    sql = f"""WITH cust AS (
  SELECT PortID, CircuitID, VpnName, CustomerFullName, VrfName, LSI, Location,
         NodeName, IfDescr, ifAlias, IfSpeed
  FROM (
    SELECT c.PortID, c.CircuitID, c.VpnName, c.CustomerFullName, c.VrfName, c.LSI,
           c.Location, c.NodeName, c.IfDescr, c.ifAlias, c.IfSpeed,
           ROW_NUMBER() OVER (PARTITION BY c.PortID
                              ORDER BY c.ProvisionTime DESC, c.T_id DESC) AS rn
    FROM {cust_t} c
    WHERE c.RemoveTime IS NULL AND c.PortID > 0 AND c.IfSpeed > 0 AND c.LSI > 100
      AND COALESCE(c.IfDescr, '') NOT LIKE 'Loop%'
      AND (c.ProvisionTime IS NULL OR c.ProvisionTime < %s){cw}
  ) x
  WHERE rn = 1
),
s AS (
  SELECT t.PortID,
         COUNT(*)           AS samples,
         MAX(t.RcvOctets)   AS max_in,  MAX(t.TxOctets) AS max_out,
         AVG(t.RcvOctets)   AS avg_in,  AVG(t.TxOctets) AS avg_out,
         SUM(t.RcvOctets)   AS sum_in,  SUM(t.TxOctets) AS sum_out,
         SUM(GREATEST(t.RcvOctets, t.TxOctets) >  %s * c.IfSpeed * 10) AS exceed_cnt,
         SUM(GREATEST(t.RcvOctets, t.TxOctets) >= %s * c.IfSpeed * 10) AS full_cnt,
         SUBSTRING_INDEX(GROUP_CONCAT(t.Time_1
             ORDER BY GREATEST(t.RcvOctets, t.TxOctets) DESC), ',', 1) AS peak_time
  FROM cust c
  JOIN {traf_t} t ON t.PortID = c.PortID
  WHERE t.Time_1 >= %s AND t.Time_1 < %s
  GROUP BY t.PortID
),
r AS (
  SELECT c.PortID AS port_id, c.CircuitID AS circuit_id, c.LSI AS lsi,
         c.VpnName AS customer, c.CustomerFullName AS customer_name, c.VrfName AS vrf,
         c.Location AS location, c.NodeName AS node, c.IfDescr AS interface,
         c.ifAlias AS if_alias, c.IfSpeed AS bw_kbps,
         COALESCE(s.samples, 0) AS samples,
         ROUND(s.max_in / 1000, 2)  AS max_in_kbps,  ROUND(s.max_out / 1000, 2) AS max_out_kbps,
         ROUND(s.avg_in / 1000, 2)  AS avg_in_kbps,  ROUND(s.avg_out / 1000, 2) AS avg_out_kbps,
         ROUND(s.sum_in  * {POLL_SECONDS} / 8 / 1000000, 2) AS vol_in_mb,
         ROUND(s.sum_out * {POLL_SECONDS} / 8 / 1000000, 2) AS vol_out_mb,
         ROUND(s.max_in  / (c.IfSpeed * 10), 2) AS max_in_util,
         ROUND(s.max_out / (c.IfSpeed * 10), 2) AS max_out_util,
         ROUND(s.avg_in  / (c.IfSpeed * 10), 2) AS avg_in_util,
         ROUND(s.avg_out / (c.IfSpeed * 10), 2) AS avg_out_util,
         ROUND(GREATEST(s.max_in, s.max_out) / (c.IfSpeed * 10), 2) AS max_util,
         ROUND(GREATEST(s.avg_in, s.avg_out) / (c.IfSpeed * 10), 2) AS avg_util,
         COALESCE(s.exceed_cnt, 0) AS exceed_cnt,
         COALESCE(s.full_cnt, 0)   AS full_cnt,
         ROUND(100 * s.exceed_cnt / s.samples, 1) AS pct_over_thr,
         s.peak_time
  FROM cust c
  LEFT JOIN s ON s.PortID = c.PortID
),
f AS (
  SELECT r.*,
         (r.samples > 0 AND r.exceed_cnt >= %s * r.samples AND r.max_util >= %s) AS upgrade,
         (r.full_cnt >= %s)                       AS saturated,
         (r.samples > 0 AND r.max_util >= %s)     AS over_sub,
         (r.samples > 0 AND r.avg_util < %s)      AS underutil
  FROM r
)"""
    params += [thr, float(SATURATION_PCT), a["start"], a["end"],
               float(UPGRADE_MIN_SHARE), float(UPGRADE_MIN_PEAK_PCT),
               int(SATURATED_MIN_SAMPLES), float(OVER_SUBSCRIBED_PCT), float(UNDERUTILIZED_PCT)]
    return sql, params


def _filter_where(a):
    """'only' and utilization filters on f -> (sql, params)."""
    w, p = [], []
    if a.get("only"):
        w.append(_ONLY_WHERE[a["only"]])
    u = a.get("util") or {}
    col = "f.avg_util" if u.get("stat") == "avg" else "f.max_util"
    if u.get("above") is not None:
        w.append(f"{col} >= %s")
        p.append(float(u["above"]))
    if u.get("below") is not None:
        w.append(f"{col} < %s")
        p.append(float(u["below"]))
    return (" WHERE " + " AND ".join(w)) if w else "", p


def _order(a, keys, default_key):
    only = a.get("only")
    d_key, d_dir = _DEFAULT_SORT.get(only, _DEFAULT_SORT[None])
    key = a.get("sort_by") or d_key
    direction = (a.get("order") or d_dir).upper()
    direction = "ASC" if direction == "ASC" else "DESC"
    expr = keys.get(key) or keys[default_key]
    return f"({expr} IS NULL), {expr} {direction}"


_CIRCUIT_COLS = """f.circuit_id AS `Circuit ID`, f.lsi AS `LSI`, f.customer AS `Customer`,
       f.customer_name AS `Customer Name`, f.vrf AS `VRF`, f.location AS `Location`,
       f.node AS `Node Name`, f.interface AS `Interface`, f.if_alias AS `Interface Alias`,
       f.bw_kbps AS `Bandwidth (Kbps)`,
       f.max_in_kbps AS `Max In (Kbps)`, f.max_out_kbps AS `Max Out (Kbps)`,
       f.avg_in_kbps AS `Avg In (Kbps)`, f.avg_out_kbps AS `Avg Out (Kbps)`,
       f.vol_in_mb AS `Volume In (MB)`, f.vol_out_mb AS `Volume Out (MB)`,
       f.max_in_util AS `Max In Util (%)`, f.max_out_util AS `Max Out Util (%)`,
       f.avg_in_util AS `Avg In Util (%)`, f.avg_out_util AS `Avg Out Util (%)`,
       f.exceed_cnt AS `Exceed Count`, f.pct_over_thr AS `Time Above Threshold (%)`,
       f.full_cnt AS `Times 100% Reached`, f.peak_time AS `Peak Time`,
       IF(f.upgrade, 'Yes', 'No') AS `BW Upgrade Needed`,
       IF(f.saturated, 'Yes', 'No') AS `Saturated`,
       IF(f.over_sub, 'Yes', 'No') AS `Far Above Subscribed BW`,
       IF(f.underutil, 'Yes', 'No') AS `Underutilized`,
       f.samples AS `Samples`"""

_GROUP_COLS = """COUNT(*) AS `Circuits`, SUM(f.samples > 0) AS `Circuits With Data`,
       SUM(f.upgrade) AS `Circuits Needing Upgrade`, SUM(f.exceed_cnt > 0) AS `Circuits Breaching`,
       SUM(f.exceed_cnt) AS `Exceed Count`, SUM(f.saturated) AS `Circuits Saturated`,
       SUM(f.full_cnt) AS `Times 100% Reached`, SUM(f.over_sub) AS `Far Above Subscribed BW`,
       SUM(f.underutil) AS `Underutilized`,
       ROUND(SUM(f.vol_in_mb), 2) AS `Volume In (MB)`, ROUND(SUM(f.vol_out_mb), 2) AS `Volume Out (MB)`,
       MAX(f.max_util) AS `Max Util (%)`, ROUND(AVG(f.avg_util), 2) AS `Avg Util (%)`"""


def _limit(a, cap=MAX_LIMIT, default=50):
    try:
        n = int(a.get("limit") or default)
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, cap))


def _hourly_sql(a, tables):
    """Per circuit or per customer, per hour. Not built on f (no flags needed)."""
    thr_sql, cp = _customer_where(a, tables)
    cust_t, traf_t = tables["customers"], tables["traffic"]
    params = [a["end"]] + cp
    cust = f"""WITH cust AS (
  SELECT PortID, CircuitID, VpnName, CustomerFullName, LSI, Location, NodeName, IfDescr, IfSpeed
  FROM (
    SELECT c.PortID, c.CircuitID, c.VpnName, c.CustomerFullName, c.LSI, c.Location,
           c.NodeName, c.IfDescr, c.IfSpeed,
           ROW_NUMBER() OVER (PARTITION BY c.PortID
                              ORDER BY c.ProvisionTime DESC, c.T_id DESC) AS rn
    FROM {cust_t} c
    WHERE c.RemoveTime IS NULL AND c.PortID > 0 AND c.IfSpeed > 0 AND c.LSI > 100
      AND COALESCE(c.IfDescr, '') NOT LIKE 'Loop%'
      AND (c.ProvisionTime IS NULL OR c.ProvisionTime < %s){thr_sql}
  ) x
  WHERE rn = 1
)"""
    peak_only = bool(a.get("peak_hour_only"))
    limit = _limit(a, cap=HOURLY_MAX_ROWS, default=HOURLY_MAX_ROWS)

    if a.get("hourly_by") == "customer":
        sql = cust + f""",
bw AS (
  SELECT VpnName, ANY_VALUE(CustomerFullName) AS customer_name, SUM(IfSpeed) AS bw_kbps,
         COUNT(*) AS circuits
  FROM cust GROUP BY VpnName
),
slot AS (
  SELECT c.VpnName,
         FROM_UNIXTIME(FLOOR(UNIX_TIMESTAMP(t.Time_1) / {POLL_SECONDS}) * {POLL_SECONDS}) AS ts,
         SUM(t.RcvOctets) AS i, SUM(t.TxOctets) AS o
  FROM cust c
  JOIN {traf_t} t ON t.PortID = c.PortID
  WHERE t.Time_1 >= %s AND t.Time_1 < %s
  GROUP BY c.VpnName, ts
),
h AS (
  SELECT VpnName, DATE_FORMAT(ts, '%Y-%m-%d %H:00') AS hr,
         MAX(i) AS mi, MAX(o) AS mo, AVG(i) AS ai, AVG(o) AS ao
  FROM slot GROUP BY VpnName, hr
),
o AS (
  SELECT h.VpnName AS `Customer`, bw.customer_name AS `Customer Name`,
         bw.circuits AS `Circuits`, bw.bw_kbps AS `Total Bandwidth (Kbps)`, h.hr AS `Hour`,
         ROUND(h.mi / 1000, 2) AS `Max In (Kbps)`, ROUND(h.mo / 1000, 2) AS `Max Out (Kbps)`,
         ROUND(h.ai / 1000, 2) AS `Avg In (Kbps)`, ROUND(h.ao / 1000, 2) AS `Avg Out (Kbps)`,
         ROUND(GREATEST(h.mi, h.mo) / (bw.bw_kbps * 10), 2) AS `Max Util (%)`,
         ROW_NUMBER() OVER (PARTITION BY h.VpnName ORDER BY GREATEST(h.mi, h.mo) DESC) AS rk
  FROM h JOIN bw ON bw.VpnName = h.VpnName
)
SELECT `Customer`, `Customer Name`, `Circuits`, `Total Bandwidth (Kbps)`, `Hour`,
       `Max In (Kbps)`, `Max Out (Kbps)`, `Avg In (Kbps)`, `Avg Out (Kbps)`, `Max Util (%)`
FROM o{" WHERE rk = 1" if peak_only else ""}
ORDER BY {"`Max Util (%)` DESC" if peak_only else "`Customer`, `Hour`"}
LIMIT {limit}"""
    else:
        sql = cust + f""",
h AS (
  SELECT t.PortID, DATE_FORMAT(t.Time_1, '%Y-%m-%d %H:00') AS hr,
         MAX(t.RcvOctets) AS mi, MAX(t.TxOctets) AS mo,
         AVG(t.RcvOctets) AS ai, AVG(t.TxOctets) AS ao, COUNT(*) AS n
  FROM cust c
  JOIN {traf_t} t ON t.PortID = c.PortID
  WHERE t.Time_1 >= %s AND t.Time_1 < %s
  GROUP BY t.PortID, hr
),
o AS (
  SELECT c.CircuitID AS `Circuit ID`, c.LSI AS `LSI`, c.VpnName AS `Customer`,
         c.Location AS `Location`, c.NodeName AS `Node Name`, c.IfDescr AS `Interface`,
         c.IfSpeed AS `Bandwidth (Kbps)`, h.hr AS `Hour`,
         ROUND(h.mi / 1000, 2) AS `Max In (Kbps)`, ROUND(h.mo / 1000, 2) AS `Max Out (Kbps)`,
         ROUND(h.ai / 1000, 2) AS `Avg In (Kbps)`, ROUND(h.ao / 1000, 2) AS `Avg Out (Kbps)`,
         ROUND(GREATEST(h.mi, h.mo) / (c.IfSpeed * 10), 2) AS `Max Util (%)`,
         h.n AS `Samples`,
         ROW_NUMBER() OVER (PARTITION BY h.PortID ORDER BY GREATEST(h.mi, h.mo) DESC) AS rk
  FROM h JOIN cust c ON c.PortID = h.PortID
)
SELECT `Circuit ID`, `LSI`, `Customer`, `Location`, `Node Name`, `Interface`,
       `Bandwidth (Kbps)`, `Hour`, `Max In (Kbps)`, `Max Out (Kbps)`, `Avg In (Kbps)`,
       `Avg Out (Kbps)`, `Max Util (%)`, `Samples`
FROM o{" WHERE rk = 1" if peak_only else ""}
ORDER BY {"`Max Util (%)` DESC" if peak_only else "`Circuit ID`, `Hour`"}
LIMIT {limit}"""
    params += [a["start"], a["end"]]
    return sql, params


def build_report_sql(a, tables):
    """Checked args -> (sql with %s, params, meta)."""
    report = a.get("report") or "circuits"
    if report not in REPORTS:
        raise ValueError(f"unknown report {report!r}")
    if a.get("only") and a["only"] not in ONLY:
        raise ValueError(f"unknown filter {a['only']!r}")

    if report == "hourly":
        sql, params = _hourly_sql(a, tables)
        return sql, params, {"report": report}

    base, params = _base_ctes(a, tables)
    fw, fp = _filter_where(a)

    if report == "circuits":
        limit = _limit(a)
        sql = (f"{base}\nSELECT {_CIRCUIT_COLS},\n       COUNT(*) OVER () AS `Total Matches`"
               f"\nFROM f{fw}\nORDER BY {_order(a, _SORT_PORT, 'utilization')}, f.circuit_id"
               f"\nLIMIT {limit}")
        return sql, params + fp, {"report": report, "limit": limit}

    if report == "totals":
        # counts of every category in scope; 'only' is ignored, the counts show each one
        sql = f"{base}\nSELECT {_GROUP_COLS}\nFROM f"
        return sql, params, {"report": report}

    limit = _limit(a)
    if report == "customers":
        sql = (f"{base}\nSELECT f.customer AS `Customer`, ANY_VALUE(f.customer_name) AS `Customer Name`,"
               f"\n       {_GROUP_COLS},\n       COUNT(*) OVER () AS `Total Matches`"
               f"\nFROM f{fw}\nGROUP BY f.customer"
               f"\nORDER BY {_order(a, _SORT_GROUP, 'utilization')}, f.customer\nLIMIT {limit}")
        return sql, params + fp, {"report": report, "limit": limit}

    # locations: merge the stored spellings (NEW DELHI / Delhi) in a CTE column of its
    # own name; GROUP BY an alias would resolve to the raw f.location column first.
    loc_expr, loc_p = _location_case("f.location")
    sql = (f"{base},\nfl AS (\n  SELECT f.*, {loc_expr} AS loc_name\n  FROM f{fw}\n)"
           f"\nSELECT f.loc_name AS `Location`,\n       {_GROUP_COLS},"
           f"\n       COUNT(*) OVER () AS `Total Matches`"
           f"\nFROM fl f\nGROUP BY f.loc_name"
           f"\nORDER BY {_order(a, _SORT_GROUP, 'upgrade')}, f.loc_name\nLIMIT {limit}")
    return sql, params + loc_p + fp, {"report": report, "limit": limit}


def describe(a):
    """One line: what the report covers, for the reply and params_used."""
    report = a.get("report") or "circuits"
    what = {"circuits": "Customer circuits", "customers": "Customers", "locations": "Locations",
            "totals": "Totals for customer circuits", "hourly": "Hourly traffic"}[report]
    if report == "hourly":
        what += " per customer" if a.get("hourly_by") == "customer" else " per circuit"
        if a.get("peak_hour_only"):
            what = "Peak hour" + (" per customer" if a.get("hourly_by") == "customer" else " per circuit")
    parts = [what]
    if a.get("only") and report != "totals":
        parts.append(_ONLY_LABEL[a["only"]])
    u = a.get("util") or {}
    stat = "average" if u.get("stat") == "avg" else "peak"
    if u.get("above") is not None:
        parts.append(f"with {stat} utilization >= {u['above']}%")
    if u.get("below") is not None:
        parts.append(f"with {stat} utilization < {u['below']}%")
    flt = a.get("filters") or {}
    for k, label in (("customer", "customer"), ("lsi", "LSI"), ("circuit_id", "circuit"),
                     ("vrf", "VRF"), ("location", "location"), ("node", "node"),
                     ("interface", "interface")):
        if flt.get(k):
            parts.append(f"{label} {', '.join(map(str, flt[k]))}")
    if a.get("circles"):
        parts.append(f"circle {', '.join(a['circles'])}")
    if a.get("tiers"):
        parts.append(f"tier {', '.join(a['tiers'])}")
    if a.get("nld") == "only":
        parts.append("NLD circuits only")
    elif a.get("nld") == "exclude":
        parts.append("excluding NLD circuits")
    parts.append(f"from {a['start']} to {a['end']}")
    return ", ".join(parts)


def rules_text(a):
    thr = a.get("threshold_pct") or THRESHOLD_PCT
    return (f"threshold {thr:g}%; upgrade = above {thr:g}% for at least "
            f"{UPGRADE_MIN_SHARE * 100:g}% of the time and peak >= {UPGRADE_MIN_PEAK_PCT}%; "
            f"saturated = at least {SATURATED_MIN_SAMPLES} samples at >= {SATURATION_PCT}%; "
            f"utilization is against the subscribed bandwidth")
