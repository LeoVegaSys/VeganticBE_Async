from utils.memoization import memoize, memoization_configuration as m_cfg

async def get_business():
    return """
TIME RULE: the data is not live. Anchor relative times on the newest poll, never NOW():
    traffic: (SELECT MAX(Time_1) FROM ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B)
    power:   (SELECT MAX(Time_1) FROM POWER_STATS_TBL)
    'last 2 hours' -> Time_1 >= (anchor) - INTERVAL 2 HOUR.
    'today' -> Time_1 >= DATE(anchor).

EXTRA RULES:
- Traffic as a rate (bps, Mbps, utilization), dips and surges: reply UNSUPPORTED.
- Optical power compared with thresholds (low/high power, alarms): reply UNSUPPORTED
  until the power unit is confirmed.
- "Which customers are affected by X": find X's interfaces or node first, then join
  CUSTOMER_VRF_TBL with RemoveTime IS NULL.
"""