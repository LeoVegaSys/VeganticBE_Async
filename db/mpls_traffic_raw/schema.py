from utils.memoization import memoize, memoization_configuration as m_cfg


@memoize(configuration=m_cfg)
async def get_schema():
    return """ 
VIEW: mpls_traffic_raw
  Pre-joined view: NODEANDIF_STATIC_TBL (aliased s, A-end inventory) INNER
  JOIN ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B (aliased t, traffic) ON
  t.PortID = s.APortID. Query this for interfaces or traffic; never write
  the join yourself.

  Column             Source        Meaning
  -----------------  ------------  --------------------------------------------
  `Port ID`          s.APortID     VLAN port id (one interface)
  `Node Name`        s.ANodeName   Router hostname, e.g. MUM-MPL-RR-RTR-37-10
  `Interface Name`   s.AIfDescr    e.g. HundredGigE0/0/0/0, Bundle-Ether30.210
  `Circle`           s.ACircle     Short code: MH, AP, TN, UPE, BHJH...
  `Tier`             s.ATier       T1..T5
  `City`             s.ACity       Full name: MUMBAI, PUNE...
  `Vendor`           s.VendorName  CISCO, NOKIA, JUNIPER...
  `LinkType`         s.LinkType    Mobility-Core, Domestic Backbone, T5-Ring...
  `LinkSubType`      s.LinkSubType More specific link classification
  `Flag`             s.Flag        Physical, Bundle, Logical, Bundle with dot
  `Class`            s.Class       Single letter: B, C, E, F
  `Oper Status`      s.IfOperStatus   up, down, testing...
  `Admin Status`     s.IfAdminStatus  up, down, testing...
  `Ring Name`        s.RingName    Ring topology name
  `Interface Alias`  s.IfAlias     Configured interface description
  `BW(Kb)`           s.IfSpeed     Interface speed in Kb (100G = 100000000)
  `Time`             t.Time_1      5-minute poll timestamp
  `In Traffic`       t.RcvOctets   INBOUND bytes in that interval (see below)
  `Out Traffic`      t.TxOctets    OUTBOUND bytes in that interval
  `In Discards`      t.InDiscPkts  Inbound discarded packets (count)
  `In Errors`        t.InErrPkts   Inbound error packets (count)
  `Out Discards`     t.OutDiscPkts Outbound discarded packets (count)
  `Out Errors`       t.OutErrPkts  Outbound error packets (count)
"""