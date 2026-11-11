from utils.memoization import memoize, memoization_configuration as m_cfg


@memoize(configuration=m_cfg)
async def get_schema():
    return """
DATABASE: DEMO_MPLS (MySQL 8). Airtel MPLS network: routers, interfaces, customer
circuits, traffic counters and optical power.

TABLES (use ONLY these, and ONLY the column names listed, spelled exactly):

- NODE_TBL: one row per router/switch. Small, needs no time filter.
    columns: NodeNumber, NodeID, NodeName, LocalAsNumber, NodeDesc, VendorName,
             NodeType, RouterType, Status, isUpdated
    * NodeNumber is the internal node key used by every other table.
    * NodeID is the management/loopback IP as text (e.g. '202.123.37.50').
    * NodeName is the hostname (e.g. 'JDH-MPL-LTE-PE-RTR-37-50'); a removed node has
      'decom' in it. Match node names with =; partial names with LIKE '%X%'.
    * NodeDesc is the full software description, e.g. 'Cisco IOS XR Software (ASR9K),
      Version 24.4.30 ...'. Software version =
      SUBSTRING_INDEX(SUBSTRING_INDEX(NodeDesc, 'Version ', -1), ' ', 1).
      Platform = text inside the first brackets, e.g. ASR9K.
    * LocalAsNumber is the BGP AS number of the node.
    * VendorName is in capitals (CISCO, JUNIPER, ...). NodeType is router / switch.
      RouterType is P / PE / CPE.
    * Peyto (optical) node: NodeID LIKE '116.119%' OR NodeName LIKE '%-T4-%'.

- NODEANDIF_STATIC_TBL: the current interface inventory: one row per interface with
  its A-end, Z-end (far end), circle, tier, city, link type. No traffic. No time filter.
  THIS is the table for circle / tier / city / link-type questions.
    columns: ACircle, ZCircle, ATier, ZTier, ACity, ZCity, AM6code, ZM6code,
             VendorName, ANodeNumber, ANodeID, ANodeName, AIfID, AIfDescr, APortID,
             ZNodeNumber, ZNodeID, ZNodeName, ZIfID, ZIfDescr, ZPortID,
             IfAdminStatus, IfOperStatus, Class, IfSpeed, LinkType, LinkSubType,
             RingName, ParentIfID, ParentIfDescr, Flag, IfAlias, AIfIndex
    * Use the A-end columns (ANodeName, AIfDescr, ACircle, ACity ...). Z-end columns
      are often NULL.
    * ACircle is a short circle code (MH, AP, RAJ, KK, NCR ...). ACity is the city
      name (e.g. 'Jodhpur'). ATier is T1..T5 (a few rows are NULL). AM6code is the
      site code CITY/AREA/NNN (e.g. 'JOD/BIA/007').
    * Circle / tier / city of a NODE: SELECT DISTINCT ANodeName, ACircle, ATier, ACity
      FROM NODEANDIF_STATIC_TBL.
    * IfSpeed is in Kb (100G = 100000000; 8192 = 8 Mbps). Mbps = IfSpeed / 1000.
    * LinkType values: BRAS, CMN-VOLTE, Domestic Backbone, Domestic BackToBack,
      Domestic Trunk, International Backbone, Mobility-Core, Mobility-RAN,
      MPLS Telemedia, MPLS-CEN-NNI, MPLS-EPT-NPT-NNI, MPLS-ISP-NNI, Optics, OTHERS,
      T4 DROPNODE, T4 INTRACITY, T4-EPT-NPT-NNI, T4-Ring, T5-Ring, Unidentified NNI.
    * LinkSubType is 'NA' except: MPLS-EPT-NPT-NNI -> 2G3G / 4G / B2B;
      MPLS-CEN-NNI -> B2B / Mobility; MPLS-ISP-NNI -> MPLS-ISP; 'Optics' on optical
      rows. '4G NNI links' -> LinkType = 'MPLS-EPT-NPT-NNI' AND LinkSubType = '4G'.
    * Flag is Physical / Bundle / Bundle with Dot (bundle sub-interface) / Logical /
      Optics / NA. A bundle's member ports have ParentIfID / ParentIfDescr set to the
      bundle.
    * Optics rows (Flag = 'Optics' or LinkType = 'Optics') are optical readings, not
      links: leave them out when counting links or interfaces unless the question is
      about optics.
    * Counting links: count Flag IN ('Physical','Bundle','Logical') rows, and skip
      Physical rows whose ParentIfID is set (bundle members), so a bundle counts once.
    * RingName is the ring a T4/T5 ring link belongs to ('NA' otherwise).
    * IfAlias formats: core links '#MPLS#BACK-TO-BACK##CONNECTED-TO-$NODE$PORT###'
      (the far end is between the $ signs); trunks '#CIRCUIT#ORDERNO#DDMMYYYY#SERVICE#';
      customer circuits 'CIRCUIT-CITY-SPEEDk-CUSTOMER-ORDERNO-DATE'. Search with LIKE.
    * Class is a letter (B, C, E ...); filter on it only when the user names a class.

- NODEIF_TBL: every interface ever discovered (large). Always filter by node or
  interface name and LIMIT. For "the interfaces of a node" prefer NODEANDIF_STATIC_TBL.
    columns: IfID, NodeNumber, IfIndex, IfIndexPhy, IfDescr, IfType, IfAdminStatus,
             IfOperStatus, IfMtu, IfSpeed, IfIPAddress, IfDuplexStatus, IfPhyAddress,
             IfLastChange, IfAlias, CreateTime, UpdateTime, IfActive
    * Use this table for IP address (IfIPAddress, 'NA' when none), MAC (IfPhyAddress),
      MTU (IfMtu), duplex (IfDuplexStatus), and first-seen time (CreateTime).
    * IfSpeed is in Kb, as in NODEANDIF_STATIC_TBL. A sub-interface shows its parent's
      speed.
    * Sub-interfaces are named PARENT.VLAN (Bundle-Ether35.200 = VLAN 200 on
      Bundle-Ether35): sub-interfaces of X -> IfDescr LIKE 'X.%'.
    * Old rows are kept: IfActive = 'Y' is not enough. For current interfaces also
      require UpdateTime >= (SELECT MAX(UpdateTime) FROM NODEIF_TBL) - INTERVAL 1 DAY.
      'Stale interfaces' = IfActive = 'Y' AND UpdateTime older than that.
    * IfLastChange is TEXT like '51 Days, 20 Hours, 10 Min, 34 Sec' (time since the last
      status change): show it, never sort or compare it.
    * IfOperStatus / IfAdminStatus are up / down / testing.

- VLANPRT_TBL: one row per polled port. It links the traffic table to interfaces.
    columns: PrtID, NodeID, PrtStatus, VlanId, IfIndex, Status, Class, counterType,
             IfDescr, IfID
    * PrtID is the port key; the traffic table's PortID = PrtID.
    * NodeID in THIS table is the node NUMBER: join it to NODE_TBL.NodeNumber, never to
      NODE_TBL.NodeID.
    * counterType is 32 or 64 (counter width).

- CUSTOMER_VRF_TBL: customer circuits (L3VPN / VRF) on PE routers: one row per circuit.
  Small, needs no time filter. Use it for any question about customers, circuits,
  VPNs or VRFs.
    columns: T_id, CircuitID, VpnName, VrfName, Location, NodeName, IfDescr, NodeNumber,
             IfIndex, IfSpeed, PortID, VpnID, ifAlias, ProvisionTime, RemoveTime, IfID,
             LSI, CustomerFullName
    * A circuit is LIVE when RemoveTime IS NULL. Add RemoveTime IS NULL to every query
      unless the question asks about removed, old, past or all circuits.
    * CustomerFullName is in capitals (e.g. '3I INFOTECH'); users type partial names:
      CustomerFullName LIKE '%NAME%', never =.
    * CircuitID e.g. '3IIN-ML3-1-7' (match with =). VpnName is its first part ('3IIN').
      VrfName is the VRF on the PE ('3I-INFOTECH-1-M').
    * Count customers with COUNT(DISTINCT CustomerFullName); circuits with
      COUNT(DISTINCT CircuitID).
    * IfSpeed in THIS table is the BOOKED speed in kbps (4096 = 4 Mbps).
      'booked bandwidth' = SUM(IfSpeed); Mbps = IfSpeed / 1000.
    * IfDescr is the customer sub-interface ('TenGigE0/1/1/1.3171'):
      VLAN = SUBSTRING_INDEX(IfDescr, '.', -1); port = SUBSTRING_INDEX(IfDescr, '.', 1).
    * Location is the city name. Circle / tier / oper status are not here: join
      NODEANDIF_STATIC_TBL on PortID = APortID.
    * ProvisionTime = service start, RemoveTime = service end. Time in service =
      DATEDIFF(COALESCE(RemoveTime, NOW()), ProvisionTime).
    * LSI is a numeric service ID (match with =). VpnID is mostly NULL: do not use it.

- ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B: traffic and error counters per port per poll
  (very large). ALWAYS filter on Time_1, and on PortID or a join, and LIMIT.
    columns: PortID, TxOctets, RcvOctets, InDiscPkts, InErrPkts, OutDiscPkts,
             OutErrPkts, Time_1, CrcAlignErr
    * PortID = VLANPRT_TBL.PrtID = NODEANDIF_STATIC_TBL.APortID.
    * Time_1 is the poll time. RcvOctets = inbound, TxOctets = outbound, for that poll.
    * InErrPkts / OutErrPkts = errors, InDiscPkts / OutDiscPkts = discards,
      CrcAlignErr = CRC errors; all per poll, so SUM them over the time range.
    * Rank ports or nodes by SUM(RcvOctets + TxOctets) over the time range. Do NOT
      convert octets to bps / Mbps / utilization: reply UNSUPPORTED for those.

- POWER_DATA_TBL: optical transceivers: one row per port lane with its power alarm
  and warning thresholds. Small, no time filter.
    columns: PowerID, NodeNumber, PowerRxIndex, PowerTxIndex, LaneName, IfDescr,
             IndexDescr, LowAlm, LowWarn, HiAlm, HiWarn, TransBW, Wavelength,
             TransDistance, OTypes, FTypes, Createtime, Updatetime, IfID,
             PowerSecIndex, NodeId
    * PowerID is the key; POWER_STATS_TBL.PowerID joins to it.
    * NodeId in THIS table is the node IP (like NODE_TBL.NodeID); NodeNumber is the
      node number.
    * IfDescr is the optical port (e.g. 'Port 1/1/5'); LaneName is the lane ('Lane 0').
    * LowAlm, LowWarn, HiWarn, HiAlm are thresholds in dBm (e.g. -30.00, -29.21, 6.00,
      8.16).
    * Wavelength, TransDistance, TransBW are 0 when unknown: ignore 0 values.

- POWER_STATS_TBL: optical power readings per transceiver lane per poll (large).
  ALWAYS filter on Time_1.
    columns: PowerID, NodeNo, RxPower, TxPower, Time_1, Source
    * PowerID = POWER_DATA_TBL.PowerID; NodeNo = NODE_TBL.NodeNumber.
    * RxPower / TxPower are raw integers in a unit not yet confirmed: show them as
      stored and never compare them with the dBm thresholds.
    * Latest reading of a lane: the row with MAX(Time_1) for that PowerID.
    * Source is the collector name (e.g. 'Simplus').

SAME COLUMN NAME IN SEVERAL TABLES -- in a multi-table query ALWAYS write alias.column:
    NodeNumber: NODE_TBL, NODEIF_TBL, CUSTOMER_VRF_TBL, POWER_DATA_TBL
    IfID: NODEIF_TBL, VLANPRT_TBL, CUSTOMER_VRF_TBL, POWER_DATA_TBL
    IfDescr: NODEIF_TBL, VLANPRT_TBL, CUSTOMER_VRF_TBL, POWER_DATA_TBL
    IfIndex: NODEIF_TBL, VLANPRT_TBL, CUSTOMER_VRF_TBL
    IfSpeed: NODEIF_TBL, NODEANDIF_STATIC_TBL, CUSTOMER_VRF_TBL
    NodeID / NodeId: NODE_TBL (IP), VLANPRT_TBL (node NUMBER!), POWER_DATA_TBL (IP)
    NodeName: NODE_TBL, CUSTOMER_VRF_TBL
    VendorName: NODE_TBL, NODEANDIF_STATIC_TBL
    IfAdminStatus, IfOperStatus: NODEIF_TBL, NODEANDIF_STATIC_TBL
    Class: VLANPRT_TBL, NODEANDIF_STATIC_TBL
    Status: NODE_TBL, VLANPRT_TBL
    PortID: CUSTOMER_VRF_TBL, ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B
    PowerID, Time_1: POWER_DATA_TBL / POWER_STATS_TBL, ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B

SAME THING, DIFFERENT COLUMN NAMES (values match):
    node number:  NODE_TBL.NodeNumber = NODEIF_TBL.NodeNumber = VLANPRT_TBL.NodeID
                  = NODEANDIF_STATIC_TBL.ANodeNumber = CUSTOMER_VRF_TBL.NodeNumber
                  = POWER_DATA_TBL.NodeNumber = POWER_STATS_TBL.NodeNo
    node IP:      NODE_TBL.NodeID = NODEANDIF_STATIC_TBL.ANodeID = POWER_DATA_TBL.NodeId
    node name:    NODE_TBL.NodeName = NODEANDIF_STATIC_TBL.ANodeName = CUSTOMER_VRF_TBL.NodeName
    interface id: NODEIF_TBL.IfID = VLANPRT_TBL.IfID = NODEANDIF_STATIC_TBL.AIfID
                  = CUSTOMER_VRF_TBL.IfID = POWER_DATA_TBL.IfID
    interface:    NODEIF_TBL.IfDescr = VLANPRT_TBL.IfDescr = NODEANDIF_STATIC_TBL.AIfDescr
                  = CUSTOMER_VRF_TBL.IfDescr
    description:  NODEIF_TBL.IfAlias = NODEANDIF_STATIC_TBL.IfAlias = CUSTOMER_VRF_TBL.ifAlias
    port id:      VLANPRT_TBL.PrtID = NODEANDIF_STATIC_TBL.APortID
                  = CUSTOMER_VRF_TBL.PortID = ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B.PortID
    vendor:       NODE_TBL.VendorName = NODEANDIF_STATIC_TBL.VendorName
    city:         NODEANDIF_STATIC_TBL.ACity = CUSTOMER_VRF_TBL.Location

JOINS (join tables only on these):
    NODEIF_TBL.NodeNumber                      = NODE_TBL.NodeNumber
    VLANPRT_TBL.NodeID                         = NODE_TBL.NodeNumber   (NodeID here is the node number)
    VLANPRT_TBL.IfID                           = NODEIF_TBL.IfID
    NODEANDIF_STATIC_TBL.ANodeNumber           = NODE_TBL.NodeNumber
    NODEANDIF_STATIC_TBL.AIfID                 = NODEIF_TBL.IfID
    NODEANDIF_STATIC_TBL.APortID               = VLANPRT_TBL.PrtID
    ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B.PortID  = VLANPRT_TBL.PrtID
    ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B.PortID  = NODEANDIF_STATIC_TBL.APortID   (traffic with circle / link type)
    CUSTOMER_VRF_TBL.NodeNumber                = NODE_TBL.NodeNumber
    CUSTOMER_VRF_TBL.IfID                      = NODEIF_TBL.IfID
    CUSTOMER_VRF_TBL.PortID                    = NODEANDIF_STATIC_TBL.APortID   (circle, tier, oper status of a circuit)
    CUSTOMER_VRF_TBL.PortID                    = ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B.PortID   (traffic of a circuit)
    POWER_DATA_TBL.NodeNumber                  = NODE_TBL.NodeNumber
    POWER_DATA_TBL.IfID                        = NODEIF_TBL.IfID
    POWER_STATS_TBL.PowerID                    = POWER_DATA_TBL.PowerID
    POWER_STATS_TBL.NodeNo                     = NODE_TBL.NodeNumber
"""