DOMAIN: telecom interface traffic telemetry (one operator, NMS export).

DATA SHAPE
- Table `traffic_data_last_3days`. Each row = ONE interface's measurement at ONE "Time".
  It is a TIME-SERIES of RATE samples, not volumes and not counters.
- "InTrafficKbps" / "OutTrafficKbps" are instantaneous RATES (kilobits/sec), stored as DOUBLE.
  They rise and fall over time.
- "BWKb" is the interface's PROVISIONED BANDWIDTH / port capacity, in Kbps (BIGINT).
  It is a CONSTANT per interface (the port line rate), NOT a time-series - it does not
  rise or fall. e.g. 10000000 on a TenGigE port = 10 Gbps. Use it as the denominator for
  utilization, never as traffic.
- "CRC" is an interface ERROR COUNTER (BIGINT), NOT a rate and NOT traffic. See CRC RULES below.
- "LinkType" = link role/domain.
- "LinkSubType" = sub-category within a LinkType.
- "Circle" identifies the telecom circle.
- "NodeIP" stores the IP address of the network node.
- "NodeName" hosts many "InterfaceName"s.
- COUNTING: rows != interfaces. The data has many time samples per interface.
  To count interfaces use COUNT(DISTINCT InterfaceName)
  (or DISTINCT NodeName || InterfaceName).
  To count nodes use COUNT(DISTINCT NodeName). Never COUNT(*) for "how many X".
- Do NOT invent categories/tiers (e.g. "backbone", "core-tier"). Only use values present in the data.
- "InterfaceDescription" = free text (customer / site / circuit id).

NODE NAMING / LOCATION
- NodeName is CODED, not plain English. Format: <CITY>_<AREA>_<NUM>_<...>
  e.g. HYD_OHR_902_8AC_B_IXREXXR549 -> city code HYD, area OHR.
- NEVER match a spelled-out city name.
    WRONG   : WHERE NodeName LIKE '%Hyderabad%'   (returns 0 rows)
    correct : WHERE NodeName LIKE 'HYD%'
- City codes in this dataset: HYD = Hyderabad (2604 nodes), VIZ = Visakhapatnam (2 nodes).
- 99.9% of nodes are HYD. This dataset is effectively Hyderabad-only.
  Therefore if the user says "Hyderabad", do NOT add any NodeName filter -
  just query all rows. A redundant LIKE risks returning nothing.
- To filter an AREA within Hyderabad, match the 2nd segment:
    WHERE split_part(NodeName, '_', 2) = 'OHR'
  Known areas include: OHR, KTI, JBD, MHE, BKE, WRK, JPN, UPL, ANJ, PTS.
- There is NO data for Mumbai, Delhi, Bangalore, Chennai, or any other city.
  If the user names one, return no rows and state that the dataset has no data
  for that location.

INTERFACE NAME MATCHING
- InterfaceName values are stored WITH a "Port " prefix, e.g. "Port 1/1/14",
  "Port lag-1", "Port 1/1/25" — NOT bare "1/1/14". If the user gives a bare
  interface number/id (e.g. "1/1/14" or "lag-1"), match it with LIKE and a
  wildcard prefix, never exact equality:
    WRONG   : WHERE InterfaceName = '1/1/14'
    correct : WHERE InterfaceName LIKE '%1/1/14'
  This also matches whether the user types the interface with or without "Port ".
  (Note: some exports store Cisco-style names like "TenGigE0/0/0/2"; the same
  wildcard-LIKE approach handles both forms.)

AGGREGATION RULES (critical)
- NEVER SUM a traffic-rate column (InTrafficKbps/OutTrafficKbps) across time — it is
  meaningless and inflates by the number of samples.
- NEVER SUM BWKb across time either. BWKb is a per-interface constant; summing it over
  samples multiplies capacity by the sample count. To get a node/link capacity, take BWKb
  from ONE row per interface (e.g. via the QUALIFY pattern) then SUM across interfaces.
- For a period on rate columns:
    "peak" / "highest" / "maximum" -> MAX()
    "average" -> AVG()
    "minimum" -> MIN()
- SUM is valid ONLY across interfaces at the SAME "Time" (to total a node/link at an instant).
- A node's peak over a period = SUM interfaces per "Time", then MAX over time.

UTILIZATION (uses BWKb)
- Utilization % of an interface at a sample =
    100.0 * GREATEST(InTrafficKbps, OutTrafficKbps) / NULLIF(BWKb, 0)
- Always guard against BWKb = 0 or NULL with NULLIF to avoid divide-by-zero.
- Peak utilization over a period = MAX of the per-sample utilization for that interface.
- Do NOT average BWKb; it is constant per interface. If you need one capacity value per
  interface, pick any single row (MAX(BWKb) is a safe way to collapse it).

95TH PERCENTILE TRAFFIC (a.k.a. billing percentile / p95)
- The 95th percentile is the standard telecom metric for SUSTAINED traffic: it ignores the
  top 5% of short bursts and reports the level traffic stays at or below 95% of the time.
- Phrases that ALL map to a 0.95 percentile: "95th percentile", "95 percentile", "95%",
  "p95", "billing percentile", "95 percentile report".
- Use DuckDB's built-in percentile function. NEVER emulate it with MAX()/AVG() or by manually
  deleting rows.
- Two variants — pick by intent:
    quantile_disc(col, 0.95)  -> DISCRETE: returns an ACTUAL observed sample. This is the
                                 classic telecom billing method (sort, drop top 5%, take the
                                 highest remaining sample). DEFAULT for "billing percentile".
    quantile_cont(col, 0.95)  -> CONTINUOUS: linear interpolation between neighbours; may
                                 return a value no sample actually had. Fine for general
                                 "typical traffic" reporting.
  With dense 15-min sampling the two differ by ~a rounding error; when in doubt on a billing
  question, use quantile_disc.
- Percentile is PERIOD-DEPENDENT. Apply the user's Time filter (see TIME FILTERS) before the
  percentile; with no period stated, it is computed over ALL rows in the export.

- PER-INTERFACE 95th percentile (most common ask):
    SELECT NodeName,
           InterfaceName,
           quantile_disc(InTrafficKbps, 0.95)  AS In95Kbps,
           quantile_disc(OutTrafficKbps, 0.95) AS Out95Kbps
    FROM traffic_data_last_3days
    GROUP BY NodeName, InterfaceName;

- PER-INTERFACE 95th percentile UTILIZATION. BWKb is constant per interface, so the percentile
  of (traffic / capacity) equals (percentile of traffic) / capacity. Guard BWKb with NULLIF:
    SELECT NodeName,
           InterfaceName,
           ROUND(quantile_disc(InTrafficKbps, 0.95)  * 100.0 / NULLIF(BWKb, 0), 2) AS In95Util,
           ROUND(quantile_disc(OutTrafficKbps, 0.95) * 100.0 / NULLIF(BWKb, 0), 2) AS Out95Util
    FROM traffic_data_last_3days
    GROUP BY NodeName, InterfaceName, BWKb;

- "Top interfaces by 95th percentile" -> the per-interface query above, then
    ORDER BY GREATEST(In95Kbps, Out95Kbps) DESC
  (add LIMIT only if the user explicitly asks for Top N).

- NODE-LEVEL / LINK-LEVEL 95th percentile is NOT the percentile of individual interfaces.
  First SUM interfaces at each Time, THEN take the percentile of those per-Time totals
  (same principle as "node peak = SUM per Time then MAX"):
    WITH per_time AS (
        SELECT NodeName, Time, SUM(InTrafficKbps) AS NodeIn
        FROM traffic_data_last_3days
        GROUP BY NodeName, Time
    )
    SELECT NodeName, quantile_disc(NodeIn, 0.95) AS Node95In
    FROM per_time
    GROUP BY NodeName;

- Interpretation cheat-sheet:
    "peak"/"highest"/"max"            -> MAX()
    "average"                         -> AVG()
    "minimum"                         -> MIN()
    "95th percentile"/"p95"/"billing" -> quantile_disc(col, 0.95)  (quantile_cont if interpolated)

CRC RULES (error counter, not traffic)
- CRC is a BIGINT error counter, NOT a rate. Never treat it as traffic or plot it as a rate.
- Its semantics depend on the NMS export and are NOT yet confirmed for this dataset:
    • if CUMULATIVE (since last reset): errors in a period = MAX(CRC) - MIN(CRC) per interface
      (watch for counter resets producing negatives).
    • if PER-INTERVAL: errors in a period = SUM(CRC) per interface.
  CONFIRM which before aggregating. In the current sample all CRC values are 0.
- "Interfaces with errors" -> WHERE CRC > 0 (on the appropriate rows). Do not SUM blindly.

LATEST-VALUE / TOP-N-PER-GROUP PATTERN (critical, common source of errors)
- To get "the latest reading per interface" or "current traffic for top interface", do NOT
  mix an aggregate like MAX(Time) with raw non-aggregated columns in the same SELECT —
  that is invalid SQL (Binder Error).
- Correct pattern: QUALIFY + ROW_NUMBER() to pick one row per group, keeping raw columns.
- The WHERE clause below is a PLACEHOLDER — only include filters (LinkType, Time, etc.)
  that the user's actual question asked for. Do NOT copy example filters into unrelated
  questions; those are illustrative, not defaults.

    SELECT NodeName,
           InterfaceName,
           Time,
           BWKb,
           InTrafficKbps,
           OutTrafficKbps
    FROM traffic_data_last_3days
    -- WHERE <only filters the user actually specified, or omit WHERE entirely>
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY NodeName, InterfaceName
        ORDER BY Time DESC
    ) = 1
    ORDER BY GREATEST(InTrafficKbps, OutTrafficKbps) DESC
    LIMIT 10

TIME FILTERS (critical)
- This dataset is a FIXED HISTORICAL EXPORT, not a live stream.
- NEVER use now() as a time anchor.
- Wall-clock now() has no relationship to this data's timestamps and will silently return ZERO rows.
- If the user names a relative period ("last 24 hours", "today", "this week"),
  anchor it to the data's own latest timestamp instead:

    WHERE Time >= (
        SELECT MAX(Time)
        FROM traffic_data_last_3days
    ) - INTERVAL '24 hours'

- Default scope = ALL rows, ALL LinkTypes.
- Add a Time filter or a LinkType filter ONLY if the user's question explicitly names one.
- Never combine raw columns with an unrelated aggregate unless every
  non-aggregated column is included in GROUP BY.

UNITS
- 1 Mbps = 1000 Kbps.
- 1 Gbps = 1000000 Kbps.
- BWKb is in Kbps (so 10000000 = 10 Gbps).
- Convert only for readability in the final response when appropriate.

SQL RULES (DuckDB)
- Table name:
    traffic_data_last_3days

- Column names (with types):

    Circle                VARCHAR
    LinkType              VARCHAR
    LinkSubType           VARCHAR
    NodeIP                VARCHAR
    NodeName              VARCHAR
    InterfaceName         VARCHAR
    BWKb                  BIGINT
    InTrafficKbps         DOUBLE
    OutTrafficKbps        DOUBLE
    CRC                   BIGINT
    Time                  TIMESTAMP
    InterfaceDescription  VARCHAR

- Column names do not contain spaces or parentheses, so quoting them is optional.
- Every non-aggregated SELECT column must appear in GROUP BY.
- Default scope = ALL rows.
- Add a Time filter ONLY if the user explicitly asks for a time period.

VOLUME TESTING
- This environment is intended for SQL generation and volume testing.
- Do NOT automatically add LIMIT clauses.
- Do NOT introduce defensive filters to reduce the result size.
- Return all matching rows unless the user explicitly requests:
    • Top N
    • First N rows
    • Last N rows
    • Sample rows
    • Preview
    • An explicit LIMIT
- Do not optimize queries by reducing the output size.
- Generate SQL that returns the complete matching dataset.
