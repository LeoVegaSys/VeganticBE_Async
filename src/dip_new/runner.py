"""
runner.py -- find_dips() for Vegantic: the Dip_Tool engine, run through the
workspace's MCP DatabaseManager instead of a direct MySQL connection.

    runner = DipRunner(db_manager, request_id, data_source="demo_mpls")
    res = await runner.find({"source": "mpls", "threshold_pct": 40, "window_hours": 2,
                             "filters": [{"column": "Circle", "op": "in", "value": ["MH"]}]})

Raises on bad arguments or a DB error; the agent turns that into an error reply.
`runner.last_sql` holds the last SQL sent, for the reply / logs.
"""
import time
from datetime import datetime, timedelta

from src.dip_new.config import (
    DIP_BASELINE_POINTS, DIP_DEFAULT_LIMIT, DIP_DEFAULT_WINDOW_HOURS,
    DIP_SERIES_MAX_PAIRS, DIP_VIEWS,
)
from src.dip_new.tool import dip_engine as E
from src.dip_new.tool.render import render


def to_dt(v):
    """datetime / 'YYYY-MM-DD HH:MM[:SS]' / ISO with T or Z -> naive datetime."""
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v.replace(microsecond=0, tzinfo=None)
    s = str(v).strip().replace("T", " ").rstrip("Z")
    return datetime.fromisoformat(s[:19])


def root_cause(e, depth=0):
    """Innermost error message: walks __cause__ / __context__ / exception groups."""
    if depth > 10:
        return f"{type(e).__name__}: {e}"
    subs = getattr(e, "exceptions", None)          # ExceptionGroup (anyio TaskGroup)
    if subs:
        return "; ".join(root_cause(s, depth + 1) for s in subs)
    inner = e.__cause__ or e.__context__
    if inner is None:                              # memoize may pass it as an arg
        inner = next((a for a in getattr(e, "args", ()) if isinstance(a, BaseException)), None)
    if inner is not None and inner is not e:
        return root_cause(inner, depth + 1)
    return f"{type(e).__name__}: {e}"


def threshold(args):
    """Exactly one of pct_range / max_pct / around_pct / threshold_pct -> (mode, lo, hi)."""
    if args.get("pct_range"):
        lo, hi = sorted(float(x) for x in args["pct_range"])
        return "range", lo, hi
    if args.get("max_pct") is not None:
        return "ceiling", None, float(args["max_pct"])
    if args.get("around_pct") is not None:
        v = float(args["around_pct"])
        return "absolute", v, v
    if args.get("threshold_pct") is not None:
        return "floor", float(args["threshold_pct"]), None
    return "floor", E.DIP_MIN_DROP, None


class DipRunner:
    def __init__(self, db_manager, request_id, data_source):
        self.db = db_manager
        self.request_id = request_id
        self.data_source = data_source
        self.last_sql = ""

    def source(self, name):
        views = DIP_VIEWS.get(self.data_source) or {}
        if name not in views:
            raise ValueError(f"no '{name}' dip view configured for data source "
                             f"'{self.data_source}' (see DIP_VIEWS in src/dip_new/config.py)")
        view, anchor = views[name]
        return E._mpls_source(view, anchor)


    async def run(self, sql):
        self.last_sql = sql
        try:
            return await self.db._execute_query(uuid=self.request_id, query=sql)
        except Exception as e:
            # py-memoize hides the real error behind "Refresh failed to complete",
            # and the MCP client can wrap it in an ExceptionGroup: show the root cause.
            raise RuntimeError(root_cause(e)) from e


    async def latest_time(self, src):
        res = await self.run(
            f"SELECT MAX(`{src['anchor_time_col']}`) AS latest FROM {src['anchor_table']}")
        data = res.get("data") or []
        v = next(iter(data[0].values()), None) if data else None
        if v is None:
            raise RuntimeError(f"{src['anchor_table']} has no rows")
        return to_dt(v)

    async def find(self, args, latest=None):
        source = args.get("source") or "mpls"
        src = self.source(source)

        direction = args.get("direction") or "dip"
        metric = args.get("metric") or "either"
        level = args.get("level") or "interface"
        unit = args.get("unit")
        if direction not in ("dip", "surge"):
            raise ValueError("direction must be 'dip' or 'surge'")
        if metric not in E.METRICS or level not in E.LEVELS:
            raise ValueError(f"bad metric {metric!r} or level {level!r}")
        if unit is not None and unit not in E.UNIT_LABEL:
            unit = None
        limit = max(1, min(int(args.get("limit") or DIP_DEFAULT_LIMIT), E.MAX_LIMIT))
        bp = DIP_BASELINE_POINTS

        mode, lo, hi = threshold(args)
        allowed = E.source_columns(src)
        filters = [f for f in (args.get("filters") or [])
                   if f.get("column") in allowed and f.get("op") in E.FILTER_OPS]
        p = {"direction": direction, "drop_mode": mode, "drop_lo": lo, "drop_hi": hi,
             "metric": metric, "level": level, "baseline_points": bp, "filters": filters,
             "want_high_util": args.get("min_util_pct") is not None,
             "high_util_pct": float(args.get("min_util_pct") or 0),
             "min_drop_abs": args.get("min_change_kbps"), "display_rate_unit": unit,
             "limit": limit, "notes": []}

        if args.get("start") and args.get("end"):
            s, e = to_dt(args["start"]), to_dt(args["end"])
            if e <= s:
                raise ValueError(f"end {e} is not after start {s}")
            win = E.window_between(s, e, src, bp)
        else:
            hours = int(round(float(args.get("window_hours") or DIP_DEFAULT_WINDOW_HOURS))) or 1
            newest = to_dt(latest) if latest else await self.latest_time(src)
            win = E.window_last_hours(newest, hours, src, bp)

        filter_sql, filter_params = E.build_filter_sql(filters, allowed)
        sql, params = E.build_dip_sql(src, p, filter_sql, filter_params, win)
        final = render(sql, params)

        t0 = time.time()
        res = await self.run(final)
        rows = res.get("data") or []
        cols = res.get("columns") or (list(rows[0]) if rows else [])
        out = {
            "ok": True, "source": source, "table": src["table"],
            "direction": direction, "level": p["level_effective"],
            "unit": E.UNIT_LABEL[p["display_unit_effective"]],
            "window": {"start": str(win[1]), "end": str(win[2])},
            "threshold": {"mode": mode, "lo": lo, "hi": hi},
            "filters": filters, "metric": metric, "limit": limit,
            "summary": E.describe(p),
            "method": (f"change % = (average of the previous {bp} readings - current) / that "
                       f"average x 100; a surge is the same with the sign flipped. Readings "
                       f"without {bp} earlier points, or with a baseline under "
                       f"{src['base_floor_kbps']} Kbps, are not judged."),
            "notes": p["notes"], "sql": final,
            "rows": rows, "columns": cols, "count": len(rows),
            "ms": round((time.time() - t0) * 1000),
        }
        if args.get("with_series") and rows:
            try:
                out["series"] = await self.series(src, p, rows)
            except Exception as ex:                     # a chart is never load-bearing
                out["notes"].append(f"Chart data failed: {ex}")
            self.last_sql = final
        return out

    async def series(self, src, p, rows):
        """Traffic points around each dip (interface level only), for the chart."""
        if p.get("level_effective") != "interface" or not rows:
            return None
        at_col = next((k for k in rows[0] if str(k).endswith(" At")), None)
        if at_col is None or "Node Name" not in rows[0]:
            return None
        pairs = []
        for r in rows:
            key = (r["Node Name"], r["Interface Name"])
            if key not in pairs:
                pairs.append(key)
        pairs = pairs[:DIP_SERIES_MAX_PAIRS]
        rows = [r for r in rows if (r["Node Name"], r["Interface Name"]) in pairs]

        bp = p["baseline_points"]
        lead, lag = max(E.SERIES_LEAD, bp + 1), E.SERIES_LAG
        poll = src["poll_interval_s"]
        times = [to_dt(r[at_col]) for r in rows]
        t_lo = min(times) - timedelta(seconds=(lead + 2) * poll)
        t_hi = max(times) + timedelta(seconds=(lag + 1) * poll)

        sql, params = E.build_series_sql(src, sorted(pairs), t_lo, t_hi)
        res = await self.run(render(sql, params))
        by_iface = {}
        for d in res.get("data") or []:
            by_iface.setdefault((d["node_name"], d["iface_name"]), []).append(
                (str(to_dt(d["ts"])), float(d["in_kbps"] or 0), float(d["out_kbps"] or 0)))

        out_u = p.get("display_unit_effective") or src["display_unit"]
        f = E.UNIT_BPS["kbps"] / E.UNIT_BPS[out_u]
        points = []
        for r in rows:
            key = (r["Node Name"], r["Interface Name"])
            seq = by_iface.get(key) or []
            dip_at = str(to_dt(r[at_col]))
            idx = next((n for n, s in enumerate(seq) if s[0] == dip_at), None)
            if idx is None:
                continue
            for n in range(max(0, idx - lead), min(len(seq), idx + lag + 1)):
                ts, i_k, o_k = seq[n]
                off = n - idx
                points.append({"dip_key": f"{key[0]}|{key[1]}|{dip_at}", "node": key[0],
                               "interface": key[1], "time": ts,
                               "in": round(i_k * f, 4), "out": round(o_k * f, 4),
                               "in_baseline": -bp <= off <= -1, "is_dip": off == 0})
        return ({"unit": E.UNIT_LABEL[out_u], "group_by": "dip_key", "points": points}
                if points else None)
