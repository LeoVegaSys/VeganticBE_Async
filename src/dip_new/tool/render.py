"""
render.py -- put parameter values into the SQL as safe literals.

The MCP tool (arun_query) takes one SQL string and no parameter list, so the
engine's %s placeholders are replaced here. Column names never come from here:
the engine checks them against a fixed list. Only values are rendered:
    None -> NULL, bool -> 1/0, int/float -> number, datetime -> 'YYYY-MM-DD HH:MM:SS',
    str -> '...' with ' doubled. Strings with a backslash or control characters are
    refused (their meaning depends on the server's sql_mode).
"""
import math
from datetime import date, datetime
from decimal import Decimal


def literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, (float, Decimal)):
        f = float(v)
        if not math.isfinite(f):
            raise ValueError(f"not a finite number: {v!r}")
        return repr(f)
    if isinstance(v, datetime):
        return "'" + v.strftime("%Y-%m-%d %H:%M:%S") + "'"
    if isinstance(v, date):
        return "'" + v.strftime("%Y-%m-%d") + "'"
    s = str(v)
    if "\\" in s or any(ord(ch) < 32 for ch in s):
        raise ValueError(f"value has a backslash or control character: {s!r}")
    return "'" + s.replace("'", "''") + "'"


def render(sql, params):
    """Replace each %s in `sql`, in order, with literal(param)."""
    parts = sql.split("%s")
    params = list(params or [])
    if len(parts) - 1 != len(params):
        raise ValueError(f"SQL has {len(parts) - 1} placeholders but {len(params)} values")
    out = [parts[0]]
    for value, rest in zip(params, parts[1:]):
        out.append(literal(value))
        out.append(rest)
    return "".join(out)
