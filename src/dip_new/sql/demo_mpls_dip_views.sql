-- ---------------------------------------------------------------------------
-- demo_mpls_dip_views.sql
-- Traffic views for DEMO_MPLS, read by src/dip_new (DIP_VIEWS["demo_mpls"] in
-- src/dip_new/config.py). Run once; the dip tool reads these views only.
--
-- DEMO_MPLS has two traffic tables with the same columns:
--   ROUTERTRAFFIC_VLANPRT_SCALE1_TBL    network ports: backbone, NNI, rings, trunks
--   ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B  B2B customer ports
--
-- So there are two views:
--   mpls_traffic_raw      network links (what the dip tool reads)
--   mpls_b2b_traffic_raw  B2B customer ports
-- Both are a pure join + rename (no aggregation, no window functions, no UNION),
-- so MySQL merges them and the Time filter uses the Time_1 index. A UNION of the
-- two tables in one view would stop that and scan both tables in full.
--
-- `In Traffic` / `Out Traffic` are RcvOctets / TxOctets passed through unchanged,
-- exactly as the Vegayan_MPLS view does. They already hold a rate in bps
-- (confirmed in dip.py 2026.09.04), so do NOT convert them here.
--
-- Run:  mysql -h 127.0.0.1 -P 3307 -u root -p DEMO_MPLS < demo_mpls_create_view.sql
-- Compare with the original first:
--   USE Vegayan_MPLS; SHOW CREATE VIEW mpls_traffic_raw\G
-- ---------------------------------------------------------------------------

USE DEMO_MPLS;

-- 1a. Network links --------------------------------------------------------
CREATE OR REPLACE ALGORITHM = MERGE SQL SECURITY INVOKER VIEW mpls_traffic_raw AS
SELECT
    t.PortID          AS `Port ID`,
    n.ANodeName       AS `Node Name`,
    n.AIfDescr        AS `Interface Name`,
    n.ACircle         AS `Circle`,
    n.ATier           AS `Tier`,
    n.ACity           AS `City`,
    n.VendorName      AS `Vendor`,
    n.LinkType        AS `LinkType`,
    n.LinkSubType     AS `LinkSubType`,
    n.Flag            AS `Flag`,
    n.Class           AS `Class`,
    n.IfOperStatus    AS `Oper Status`,
    n.IfAdminStatus   AS `Admin Status`,
    n.RingName        AS `Ring Name`,
    n.IfAlias         AS `Interface Alias`,
    n.IfSpeed         AS `BW(Kb)`,
    t.Time_1          AS `Time`,
    t.RcvOctets       AS `In Traffic`,
    t.TxOctets        AS `Out Traffic`,
    t.InDiscPkts      AS `In Discards`,
    t.InErrPkts       AS `In Errors`,
    t.OutDiscPkts     AS `Out Discards`,
    t.OutErrPkts      AS `Out Errors`
FROM ROUTERTRAFFIC_VLANPRT_SCALE1_TBL t
JOIN NODEANDIF_STATIC_TBL n ON n.APortID = t.PortID;

-- 1b. B2B customer ports (same columns) ------------------------------------
CREATE OR REPLACE ALGORITHM = MERGE SQL SECURITY INVOKER VIEW mpls_b2b_traffic_raw AS
SELECT
    t.PortID          AS `Port ID`,
    n.ANodeName       AS `Node Name`,
    n.AIfDescr        AS `Interface Name`,
    n.ACircle         AS `Circle`,
    n.ATier           AS `Tier`,
    n.ACity           AS `City`,
    n.VendorName      AS `Vendor`,
    n.LinkType        AS `LinkType`,
    n.LinkSubType     AS `LinkSubType`,
    n.Flag            AS `Flag`,
    n.Class           AS `Class`,
    n.IfOperStatus    AS `Oper Status`,
    n.IfAdminStatus   AS `Admin Status`,
    n.RingName        AS `Ring Name`,
    n.IfAlias         AS `Interface Alias`,
    n.IfSpeed         AS `BW(Kb)`,
    t.Time_1          AS `Time`,
    t.RcvOctets       AS `In Traffic`,
    t.TxOctets        AS `Out Traffic`,
    t.InDiscPkts      AS `In Discards`,
    t.InErrPkts       AS `In Errors`,
    t.OutDiscPkts     AS `Out Discards`,
    t.OutErrPkts      AS `Out Errors`
FROM ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B t
JOIN NODEANDIF_STATIC_TBL n ON n.APortID = t.PortID;


-- 2. Indexes ---------------------------------------------------------------
-- Check first; create only the missing ones. On a crore-row table an index
-- build takes a long time and locks writes: run it off-peak.
--
--   SHOW INDEX FROM ROUTERTRAFFIC_VLANPRT_SCALE1_TBL;
--   SHOW INDEX FROM ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B;
--   SHOW INDEX FROM NODEANDIF_STATIC_TBL;
--
-- CREATE INDEX ix_time_port ON ROUTERTRAFFIC_VLANPRT_SCALE1_TBL   (Time_1, PortID);
-- CREATE INDEX ix_port_time ON ROUTERTRAFFIC_VLANPRT_SCALE1_TBL   (PortID, Time_1);
-- CREATE INDEX ix_time_port ON ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B (Time_1, PortID);
-- CREATE INDEX ix_port_time ON ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B (PortID, Time_1);
-- CREATE INDEX ix_aportid   ON NODEANDIF_STATIC_TBL (APortID);


-- 3. Checks: run after creating the views ----------------------------------

-- (a) Both views return rows, and the time filter is fast (< 1 s each).
SELECT 'network' AS src, COUNT(*) AS rows_last_hour
FROM mpls_traffic_raw
WHERE `Time` >= (SELECT MAX(Time_1) FROM ROUTERTRAFFIC_VLANPRT_SCALE1_TBL) - INTERVAL 1 HOUR
UNION ALL
SELECT 'b2b', COUNT(*)
FROM mpls_b2b_traffic_raw
WHERE `Time` >= (SELECT MAX(Time_1) FROM ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B) - INTERVAL 1 HOUR;

-- (b) The plan must use an index on Time_1 / PortID, not a full scan.
EXPLAIN
SELECT `Node Name`, `In Traffic`
FROM mpls_traffic_raw
WHERE `Time` >= (SELECT MAX(Time_1) FROM ROUTERTRAFFIC_VLANPRT_SCALE1_TBL) - INTERVAL 1 HOUR;

-- (c) No port is in both tables (expect 0).
SELECT COUNT(DISTINCT b.PortID) AS ports_in_both
FROM ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B b
JOIN ROUTERTRAFFIC_VLANPRT_SCALE1_TBL n ON n.PortID = b.PortID AND n.Time_1 = b.Time_1
WHERE b.Time_1 >= (SELECT MAX(Time_1) FROM ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B) - INTERVAL 1 HOUR;

-- (d) Which link types land in each table: network link types should be in
--     the network table, customer ports in _B.
SELECT 'network' AS src, `LinkType`, COUNT(DISTINCT `Port ID`) AS ports
FROM mpls_traffic_raw
WHERE `Time` >= (SELECT MAX(Time_1) FROM ROUTERTRAFFIC_VLANPRT_SCALE1_TBL) - INTERVAL 1 HOUR
GROUP BY `LinkType`
UNION ALL
SELECT 'b2b', `LinkType`, COUNT(DISTINCT `Port ID`)
FROM mpls_b2b_traffic_raw
WHERE `Time` >= (SELECT MAX(Time_1) FROM ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B) - INTERVAL 1 HOUR
GROUP BY `LinkType`
ORDER BY src, ports DESC;

-- (e) One inventory row per port. If an APortID appears twice, every traffic
--     reading for it is counted twice through the views.
SELECT APortID, COUNT(*) AS rows_for_port
FROM NODEANDIF_STATIC_TBL
WHERE APortID IS NOT NULL
GROUP BY APortID
HAVING COUNT(*) > 1
ORDER BY rows_for_port DESC
LIMIT 20;

-- (f) Poll gap and unit sanity for one network port: the gap should be ~300 s,
--     and In Traffic / 1e6 (already bps) should give a believable Mbps for the port speed.
SELECT `Time`, `In Traffic`,
       TIMESTAMPDIFF(SECOND, LAG(`Time`) OVER (ORDER BY `Time`), `Time`) AS gap_s,
       ROUND(`In Traffic` / 1e6, 2) AS in_mbps,
       `BW(Kb)` / 1000 AS port_mbps
FROM mpls_traffic_raw
WHERE `Node Name` = 'JDH-MPL-LTE-PE-RTR-37-50' AND `Interface Name` = 'Bundle-Ether35'
  AND `Time` >= (SELECT MAX(Time_1) FROM ROUTERTRAFFIC_VLANPRT_SCALE1_TBL) - INTERVAL 1 HOUR
ORDER BY `Time`;
