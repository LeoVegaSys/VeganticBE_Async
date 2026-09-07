import os
import aiofiles

from utils.memoization import memoize, memoization_configuration as m_cfg

async def get_business():
    return """
CRITICAL DATA FACTS:
  - `In Traffic`/`Out Traffic` are PER-INTERVAL BYTE TOTALS, not rates and not
    running counters. SUM() over a range = total bytes (valid). AVG()/MAX() is
    NOT a Mbps/Gbps rate -- do not present it as one.
  - `In/Out Discards` and `In/Out Errors` are packet COUNTS, not bytes and not
    rates. SUM() them for totals.
  - One row = one interface at one poll. Count interfaces/nodes with
    COUNT(DISTINCT `Interface Name`) / COUNT(DISTINCT `Node Name`), never COUNT(*).
  - `Circle` = short code (MH); `City` = full name (MUMBAI). Match values to
    the right column.
  - Any query scanning traffic MUST filter `Time`, or it reads ~60M rows.
    Pure metadata (list circles, count nodes) does not, since DISTINCT/COUNT
    collapse the rows.
  - INNER join means interfaces with NO traffic rows in the window are absent.
    For pure inventory ("what interfaces exist on node X") query
    NODEANDIF_STATIC_TBL directly: columns ANodeName, AIfDescr, APortID.
"""