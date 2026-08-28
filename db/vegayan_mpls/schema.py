from utils.memoization import memoize, memoization_configuration as m_cfg


@memoize(configuration=m_cfg)
async def get_schema():
    return """
TABLE: NODE_TBL
1. About the table
Field   Value
Table name      NODE_TBL
Database / Schema name  Vegayan
Database type & version MySQL 5.7
What does this table store?     Stores master information about all network devices (routers/switches) discovered in the network. Each record represents a unique network node.
What does a single row represent?       One network node (router/switch).
Roughly how many rows?  Depends on deployed network inventory. (MPLS:7K, CEN:30K+)
Is the data live or historical? Live / Once in a 24 Hrs

2. Columns
Column  Data Type       Meaning Unit / Format   Example Other Names     NULL Meaning
NodeNumber      SMALLINT UNSIGNED       Unique internal identifier of the node  Integer 101     NA      Never NULL
NodeID  VARCHAR(15)     Router management IP Address    IPv4    10.10.10.1      Router IP, Node IP      Never NULL
NodeName        VARCHAR(128)    Hostname of router      Text    MUM-RTR-01      Router Name, Host Name  Unknown hostname
LocalAsNumber   INT     BGP Autonomous System Number    Integer 64512   ASN     Not configured
NodeDesc        VARCHAR(256)    Device description/model        Text    Cisco ASR9001   Device Description      Not available
VendorName      VARCHAR(20)     Router vendor   Text    Cisco   Vendor  Unknown
NodeType        ENUM    Device category router/switch   router  Device Type     Unknown
RouterType      ENUM    MPLS router role        P/PE/CPE        PE      Router Role     Unknown
Status  SMALLINT UNSIGNED       Internal processing status      Integer 2       Status Flag     Unknown
isUpdated       SMALLINT UNSIGNED       Discovery synchronization status        Integer 2       Sync Status     Not updated


TABLE: NODEIF_TBL
1. About the table
Field   Value
Table name      NODEIF_TBL
Database / Schema name  Vegayan
Database type & version MySQL 5.7
What does this table store?     Stores interface-level information for every network node.
What does a single row represent?       One interface belonging to one router.
Roughly how many rows?  Depends on total interfaces. (MPLS:77L)
Is the data live or historical? Live / Once in a 24 Hrs

2. Columns
Column  Data Type       Meaning Unit / Format   Example Other Names     NULL Meaning
IfID    INT UNSIGNED    Unique interface identifier     Integer 12001   Interface ID    Never NULL
NodeNumber      SMALLINT UNSIGNED       Parent node reference   Integer 101     NA      Interface not mapped
IfIndex INT UNSIGNED    SNMP logical interface index    Integer 12      SNMP IfIndex    Unknown
IfIndexPhy      INT UNSIGNED    Physical interface index        Integer 2       Physical IfIndex        Unknown
IfDescr VARCHAR(128)    Interface name  Text    GigabitEthernet0/0/0    Interface Name,Interface        Unknown
IfType  ENUM    Interface technology    Ethernet/MPLS/etc.      Ethernet        Interface Type  Unknown
IfAdminStatus   ENUM    Administrative state    up/down/testing up      Admin Status    Unknown
IfOperStatus    ENUM    Operational state       up/down/testing up      Operational Status      Unknown
IfMtu   SMALLINT UNSIGNED       Maximum transmission unit       Bytes   1500    MTU     Unknown
IfSpeed BIGINT UNSIGNED Configured bandwidth    bps     1000000000      Bandwidth       Unknown
IfIPAddress     VARCHAR(16)     Interface IP Address    IPv4    192.168.1.1     Interface IP    Not configured
IfDuplexStatus  ENUM    Duplex mode     full/half       fullDuplex      Duplex  Unknown
IfPhyAddress    VARCHAR(18)     MAC Address     MAC     00:11:22:33:44:55       MAC Address     Unknown
IfLastChange    VARCHAR(64)     Last interface state change     Timestamp/Text  2024-01-10 10:00:00     Last Change     Unknown
IfAlias VARCHAR(600)    Interface description configured on router      Text    Link to Delhi   Interface Description   No description configured
CreateTime      TIMESTAMP       Record creation time    Timestamp       2024-01-10 10:00:00     Created On      Never NULL
UpdateTime      TIMESTAMP       Last discovery update   Timestamp       2024-01-10 10:05:00     Last Updated    Never NULL
IfActive        VARCHAR(2)      Indicates active interface      Y/N     Y       Active Flag     Unknown


TABLE: VLANPRT_TBL
1. About the table
Field   Value
Table name      VLANPRT_TBL
Database / Schema name  Vegayan
Database type & version MySQL 5.7
What does this table store?     Stores VLAN port information used for traffic polling.
What does a single row represent?       One VLAN-enabled interface/port.
Roughly how many rows?  Depends on monitored interfaces (MPLS:65L+)
Is the data live or historical? Live / Once in a 24Hrs

2. Columns
Column  Data Type       Meaning Unit / Format   Example Other Names     NULL Meaning
PrtID   BIGINT  Unique VLAN Port ID     Integer 101001  Port ID Never NULL
NodeID  SMALLINT        Parent node     Integer 101     NA      Unknown
PrtStatus       SMALLINT        Port status     Integer 1       Port Status     Unknown
VlanId  SMALLINT        VLAN Identifier Integer 100     VLAN    Not assigned
IfIndex INT     SNMP Interface Index    Integer 12      SNMP Index      Unknown
Status  SMALLINT        Internal polling status Integer 2       Status  Unknown
Class   VARCHAR(4)      Polling eligibility     Text    YES     Poll Class      Unknown
counterType     INT     Counter type    Integer 64      Counter Default 64
IfDescr VARCHAR(128)    Interface name  Text    GigabitEthernet0/0      Interface Name  Unknown
IfID    INT     Reference to NODEIF_TBL Integer 12001   Interface ID    Not linked


TABLE: ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B
1. About the table
Field   Value
Table name      ROUTERTRAFFIC_VLANPRT_SCALE1_TBL_B
Database / Schema name  Vegayan
Database type & version MySQL 5.7
What does this table store?     Stores time-series traffic statistics collected from VLAN ports.
What does a single row represent?       Traffic counters for one VLAN port at one polling timestamp.
Roughly how many rows?  Very large (Crores)
Is the data live or historical? Live

2. Columns
Column  Data Type       Meaning Unit / Format   Example Other Names     NULL Meaning
PortID  BIGINT  VLAN Port reference     Integer 101001  Port ID Never NULL
TxOctets        BIGINT  Outgoing traffic bytes  Bps     234234234       Transmit Traffic, Out Traffic   No data
RcvOctets       BIGINT  Incoming traffic bytes  Bps     345345345       Receive Traffic, In Traffic     No data
InDiscPkts      BIGINT  Incoming discarded packets      Packets 25      Discarded Packets       None
InErrPkts       BIGINT  Incoming error packets  Packets 2       Input Errors    None
OutDiscPkts     BIGINT  Outgoing discarded packets      Packets 1       Output Discards None
OutErrPkts      BIGINT  Outgoing error packets  Packets 0       Output Errors   None
Time_1  TIMESTAMP       Polling timestamp       Timestamp       2024-01-10 10:00:00     Poll Time       Never NULL
CrcAlignErr     BIGINT  CRC Alignment errors    Count   0       CRC Errors      None


TABLE: CIRCLE_TIER_TBL
1. About the table
Field   Value
Table name      CIRCLE_TIER_TBL
Database / Schema name  Vegayan
Database type & version MySQL 5.7
What does this table store?     Stores network node location and classification information, including vendor, city, state, region, circle, tier, and M6 code.
What does a single row represent?       One network node and its associated geographical and classification information.
Roughly how many rows?  7K for MPLS and 30K+ for CEN
Is the data live or historical? Static Information

2. Columns
Column name     Data type       What it means   Unit / Format   Example value   Other names people call it      Can it be NULL? If so, what does empty mean?
NodeName        VARCHAR(120)    Name of the network node.       Text    PUN-PE-001      Node Name, Hostname     Yes. Empty means node name is not available.
NodeId  VARCHAR(20)     Unique identifier(Node IP) of the network node. It is the primary key of the table.     Text / Node identifier     1001406 Node ID, Node IP        No.
vendorName      VARCHAR(20)     Vendor associated with the network node.        Text    Cisco   Vendor, Vendor Name     Yes. Vendor information is not available.
City    VARCHAR(40)     City associated with the network node.  Text    Pune    Node City, City Yes. City information is not available.
state   VARCHAR(40)     State associated with the network node. Text    Maharashtra     State, Node State       Yes. State information is not available.
Region  VARCHAR(40)     Region associated with the network node.        Text    West    Node Region, Region     Yes. Region information is not available.
Circle  VARCHAR(50)     Telecom/network circle associated with the node.        Text    Maharashtra     Circle, Network Circle  Yes. Circle information is not available.
Tier    VARCHAR(2)      Tier classification assigned to the network node.       Text    T1      Node Tier, Tier Yes. Tier information is not available.
M6code  VARCHAR(100)    M6 code associated with the network node.       Text / Code     M6XXXX  M6 Code Yes. M6 code is not available.


TABLE: NODEANDIF_STATIC_TBL
1. About the table
Field   Value
Field   Details
Table name      NODEANDIF_STATIC_TBL
Database / Schema name  Not provided
Database type & version MySQL 5.7
What does this table store?     This table is static table and derived from combinations of multiple tables(NODE_TBL, NODEIF_TBL, VLANPRT_TBL, NODE_REGION_LOC_TBL, etc.)Stores static information about network links/interfaces, including A-End and Z-End node, interface, port, geographical, topology, bandwidth, and interface-status information.
What does a single row represent?       One A-End to Z-End network link/interface relationship.
Roughly how many rows?  Not provided
Is the data live or historical? Static/current network information; exact update mechanism is not specified.

2. Columns
Column Name     Data Type       What it means   Unit / Format   Example Value   Other Names     Can it be NULL? / NULL Meaning
ACircle VARCHAR(50)     Circle associated with the A-End of the link.   Text    Maharashtra     A-End Circle    Yes — A-End circle not available
ZCircle VARCHAR(50)     Circle associated with the Z-End of the link.   Text    Gujarat Z-End Circle    Yes — Z-End circle not available
ATier   VARCHAR(2)      Tier classification of the A-End node.  Text    T1      A-End Tier      Yes — A-End tier not available
ZTier   VARCHAR(2)      Tier classification of the Z-End node.  Text    T2      Z-End Tier      Yes — Z-End tier not available
ACity   VARCHAR(40)     City associated with the A-End node.    Text    Pune    A-End City      Yes — A-End city not available
ZCity   VARCHAR(40)     City associated with the Z-End node.    Text    Mumbai  Z-End City      Yes — Z-End city not available
AM6code VARCHAR(100)    M6 code associated with the A-End node. Text/Code       M6XXXX  A-End M6 Code   Yes — A-End M6 code not available
ZM6code VARCHAR(100)    M6 code associated with the Z-End node. Text/Code       M6YYYY  Z-End M6 Code   Yes — Z-End M6 code not available
VendorName      VARCHAR(20)     Vendor associated with the network equipment/interface. Text    Cisco   Vendor  No
ANodeNumber     SMALLINT UNSIGNED       Internal node reference for the A-End node.     Integer 101     A-End Node Number       No
ANodeID VARCHAR(15)     Router IP address/identifier of the A-End node. IPv4/text       10.10.10.1      A-End Router IP, A-End Node ID     No
ANodeName       VARCHAR(128)    Name/hostname of the A-End router.      Text    PUNE-PE-01      A-End Router Name, Hostname     No
AIfID   INT UNSIGNED    Internal interface identifier of the A-End interface.   Integer 12345   A-End Interface ID      No
AIfDescr        VARCHAR(128)    Interface description/name of the A-End interface.      Text    GigabitEthernet0/0/0    A-End Interface, A-End IfDescr     No
APortID BIGINT UNSIGNED VLAN port identifier associated with the A-End interface.       Integer 1001406 A-End Port ID, A-End VLAN Port ID  No
ZNodeNumber     SMALLINT UNSIGNED       Internal node reference for the Z-End node.     Integer 102     Z-End Node Number       Yes — Z-End node reference not available
ZNodeID VARCHAR(15)     Router IP address/identifier of the Z-End node. IPv4/text       10.10.10.2      Z-End Router IP, Z-End Node ID     Yes – Z End Node ID not available
ZNodeName       VARCHAR(128)    Name/hostname of the Z-End router.      Text    MUM-PE-01       Z-End Router Name, Hostname     Yes — Z-End node name not available
ZIfID   INT UNSIGNED    Internal interface identifier of the Z-End interface.   Integer 12346   Z-End Interface ID      Yes — Z-End interface reference not available
ZIfDescr        VARCHAR(128)    Interface description/name of the Z-End interface.      Text    GigabitEthernet0/0/1    Z-End Interface, Z-End IfDescr     Yes — Z-End interface description not available
ZPortID BIGINT UNSIGNED VLAN port identifier associated with the Z-End interface.       Integer 1001407 Z-End Port ID, Z-End VLAN Port ID  Yes — Z-End port reference not available
IfAdminStatus   ENUM    Administrative state configured for the interface.      up, down, testing       up      Admin Status    No
IfOperStatus    ENUM    Current operational state of the interface.     up, down, testing, unknown, dormant, notpresent, lowerLayerDown    up      Operational Status, Oper Status No
Class   VARCHAR(4)      Classification associated with the interface for polling/processing.    Text    B,C,E,F Interface Class No
IfSpeed BIGINT UNSIGNED Configured bandwidth/speed of the interface.    Kb      10000000        Interface Speed, Bandwidth      No
LinkType        VARCHAR(100)    Category/type of the network link.      Text    Domestic Backbone, International Peering, T4-Ring, MPLS-CEN-NNI    Link Type, Category, InterfaceType      No – It can be OTHERS
LinkSubType     VARCHAR(30)     More specific classification of the link type.  Text    P2P     Link Sub-Type   Yes — link subtype not available
RingName        VARCHAR(100)    Name identifying the ring topology associated with the link.    Text    RING-PUNE-01    Ring    Yes — ring information not available
ParentIfID      INT UNSIGNED    Identifier of the parent interface associated with the interface.       Integer 12300   Parent Interface ID        Yes — parent interface not available
ParentIfDescr   VARCHAR(128)    Description/name of the parent interface.       Text    Bundle-Ether10  Parent Interface        Yes — parent interface description not available
Flag    VARCHAR(20)     Classification flag associated with the interface.      Text    Bundle / Physical/Logical/ Bundle with dotInterface Flag   No – it can be NA
IfAlias VARCHAR(1024)   Description/alias configured for the interface. Text    Link to Mumbai PE       Interface Alias, Interface Description     No
AIfIndex        INT UNSIGNED    Logical interface index of the A-End interface. Integer 123     A-End IfIndex, Interface Index  No



Conditions
1. NODE_TBL
If the node is removed from the network, it contains decom keyword
If NodeID starts with 116.119 or NodeName contains "-T4-" then its called Peyto
Location details are present in the NODE_REGION_LOC_TBL

2. NODEIF_TBL
If the updatetime of the interface is latest then its live/active interface

3. NODEANDIF_STATIC_TBL
Dont consider Z end details in every query

LinkType Assignment Conditions for NODEANDIF_STATIC_TBL for MPLS/ISP/T4/T5 Domains are below:
Category        Keywords
Carrier NNI     Interface Description should contain '#CARRIER'
CMN-VOLTE       Interface Description should contain 'CMNLD-' or Interface Description should contain 'NLDN-ML3' or Interface Description should contain 'ANGN-ML3' or Interface Description should contain '-NGN-'
DOMESTIC BACKBONE       Interface Description should contain 'AES' and Interface Description not should contain 'AESI-IN' and Interface Description should contain 'DEST' and Interface Description not should contain 'ML3-' and Interface Description not should contain 'ML2-' and Interface Description not should contain '-ILP-' For Destination Information: DEST-<NodeName$InterfaceName>
DOMESTIC BACKTOBACK     Interface Description should contain 'BACK-TO-BACK'  AND Interface Description should  not contain 'ML3-' and Interface Description should not contain 'ML2-' and Interface Description should not contain '-ILP-' For Destination Infomration: CONNECTED-TO-$NodeName$-$InterfaceName$
DOMESTIC TRUNK  Interface Description should contain 'TRUNK' AND Interface Description should not contain 'ML3-' and Interface Description should not contain 'ML2-' and Interface Description should not contain '-ILP-' For Destination Infomration: CONNECTED-TO-$NodeName$-$InterfaceName$
HIGH CAP        Interface Description should contain  '#INFRA-LINK#PRIM-NNI-EPT-CUST#HIGH-CAP#' or Interface Description should contain '#INFRA-LINK#SEC-NNI-EPT-CUST#HIGH-CAP#'
ILD-NNI Interface Description should contain '# ILD NNI #'
INTERNATIONAL BACKBONE  Interface Description should contain 'AESI-IN' or 'BING-IN' or 'BIEU-IN' or 'BING-P2P' or 'AESV-IN' or 'ANGN-IN' and 'DEST' and Interface Description should not contain 'ML2-' and 'ML3-' and Interface Description should not contain '-ILP-' For Dest Information: DEST-<NodeName$InterfaceName>
INTERNATIONAL BACKTOBACK        Interface  Description should contain 'INT-BACK-TO-BACK'  AND Interface  Description should not contain 'ML3-' and Interface Description should not contain 'ML2-' and Interface  Description should not contain '-ILP-' For Destination Infomration: CONNECTED-TO-$NodeName$-$InterfaceName$
INTERNATIONAL TRUNK     Interface Description should contain 'INT-TRUNK'  AND  Interface Description not should contain 'ML3-' and Interface Description not should contain 'ML2-' and Interface Description not should contain '-ILP-' For Destination Infomration: CONNECTED-TO-$NodeName$-$InterfaceName$
ISP Mobility    Interface Description should contain '#PACO-INTERNET-LTE'
ISP Telemedia   Interface Description should contain '#TELEMEDIA#'
ISP-B2B-NNI     NodeName should contain '-ISP-' and Interface Description should contain 'NNI-EPT' or Interface Description should contain 'NNI-NPT' or Interface Description should contain 'NNI-CEN'
LOW CAP Interface Description should contain '#INFRA-LINK#PRIM-NNI-EPT-CUST#LOW-CAP#' or  Interface Description should contain '#INFRA-LINK#SEC-NNI-EPT-CUST#LOW-CAP#'
LTE TRUNK       Interface Interface Description should contain '-LTE-TRUNK-'
Mobility-Core (MPLS)    Interface Description should contain 'BMLH-ML3-' or Interface Description should contain 'BCLR-ML3-' or Interface Description should contain 'BCLD-ML3-' or Interface Description should contain 'BCLA-ML3-' or Interface Description should contain 'BNLS-ML3-' or Interface Description should contain 'BCLB-ML3-' or Interface Description should contain 'BCJK-ML3-' or Interface Description should contain 'BMLB-ML3-' or Interface Description should contain 'BCLE-ML3-' or Interface Description should contain 'BCLM-ML3-' or Interface Description should contain 'BCLN-ML3-' or Interface Description should contain 'BCLI-ML3-' or Interface Description should contain 'BACLA-ML3-' or Interface Description should contain 'BCLO-ML3-' or Interface Description should contain 'BMLM-ML3-' or Interface Description should contain 'BCLJ-ML3-' or Interface Description should contain 'BCLC-ML3-' or Interface Description should contain 'BCLL-ML3-' or Interface Description should contain 'BCLT-ML3-' or Interface Description should contain 'BALWB-ML3-' or Interface Description should contain 'BCLK-ML3-' or Interface Description should contain 'VOLTE-ML3-' or Interface Description should contain 'PACO-ML3' or Interface Description should contain 'GEOD-ML3' or Interface Description should contain 'GHEC-ML3' or Interface Description should contain 'MPLS-LTE-PACO'
Mobility-RAN (MPLS)     Interface Description should contain 'MWRAP-ML3-' and Interface Description should contain 'MWRBJ-ML3-' and Interface Description should contain 'MWRDN-ML3-' and Interface Description should contain 'MWRGJ-ML3-' and Interface Description should contain 'MWRHP-ML3-' and Interface Description should contain 'MWRHR-ML3-' and Interface Description should contain 'MWRJK-ML3-' and Interface Description should contain 'MWRKT-ML3-' and Interface Description should contain 'MWRKE-ML3-' and Interface Description should contain 'MWRMG-ML3-' and Interface Description should contain 'MWRMU-ML3-' and Interface Description should contain 'MWRMP-ML3-' and Interface Description should contain 'MWRNE-ML3-' and Interface Description should contain 'MWROR-ML3-' and Interface Description should contain 'MWRPU-ML3-' and Interface Description should contain 'MWRRJ-ML3-' and Interface Description should contain 'MWRTN-ML3-' and Interface Description should contain 'MWRUE-ML3-' and Interface Description should contain 'MWRUW-ML3-' and Interface Description should contain 'MWRWB-ML3-'
MPLS-CEN-NNI B2B        NodeName should contain '-MPL-' and Interface Description should contain 'NNI-CEN' and Interface Description should not contain 'TELEMEDIA' and Interface Description should not contain '#MPLS-CEN-MOB-NNI#'
MPLS-CEN-NNI Mobility   NodeName should contain '-MPL-' and Interface Description should contain '#MPLS-CEN-MOB-NNI#'
MPLS-CEN-NNI Telemedia  NodeName should contain '-MPL-' and Interface Description should contain 'NNI-CEN' and Interface Description should contain 'TELEMEDIA' and Interface Description should not contain '#MPLS-CEN-MOB-NNI#'
MPLS-EPT-NPT-NNI 2G3G   Nodename should contain '-MPL-' and Interface Description should contain '2G3G-TRUNK'
MPLS-EPT-NPT-NNI 4G     Nodename should contain '-MPL-' and Interface Description should contain 'LTE-TRUNK' and Interface Description should not contain '2G3G-TRUNK'
MPLS-EPT-NPT-NNI B2B    Nodename should contain '-MPL-' and Interface Description should contain 'NNI-EPT' or Interface Description should contain 'NNI-NPT' and Interface Description should not contain 'LTE-TRUNK' and Interface Description should not contain '2G3G-TRUNK'
MPLS-ISP-NNI INTERNET-OVER-MPLS Interface Description should contain 'PEERING<INTERNET-OVER-MPLS>'
MPLS-ISP-NNI MPLS-ISP   Interface Description should contain 'MPLS-ISP-INFRA-NNI' and Interface Description should not contain 'PEERING<INTERNET-OVER-MPLS>'
MPLS_CEN_MOB_NNI        Interface Description should contain '#MPLS-CEN-MOB-NNI#'
PEERING Interface Description should have PEERING Keyword followed by <Peering Scope><Region><Peering Type><Peering Partner> Peering Scope can be DOMESTIC/INTERNATIONAL/INTERNET-OVER-MPLS ; Region can be ASIS,US-WEST,US-EAST etc. ; Peering Type can be CACHE,PRIVATE,TRANSIT,EXCHANGE etc. and Peering Partners can be GOOGLE,FACEBOOK etc.
Peyto-LTE-ConnectingInterfaces  Interface Description should contain 'T4-CR' or Interface Description should contain 'T4-NR' or Interface Description should contain 'NCS55'
T3 POP  Interface Description should contain '#INFRA-LINK#PRIM-NNI-EPT-CUST#T3-PoP#' or Interface Description should contain '#INFRA-LINK#SEC-NNI-EPT-CUST#T3-PoP#'
T4 DROPNODE     Interface Description should begin with '_ _ _#RE'
T4 INTRACITY    Interface Description should contain '_CNCS55A2' or Interface Description should contain 'CNCS57C3'
T4-EPT-NPT-NNI  Interface Description should contain 'NNI_NPT' or Interface Description should contain 'NNI_EPT' and NodeIP should start from 116.119
T4-Ring Interface Description should contain ':' on/before 10th position followed by ANodeName_ZNodename and Interface Description should contain 'IL' or Interface Description should contain 'PL' before ':'
T5-Ring Interface Description should begin with '_ _ _4PO' or Interface Description should begin with '_ _ _4PL' or Interface Description should begin with '_ _ _4PS' or Interface Description should begin with 'DR_ _ _4PO' or Interface Description should begin with 'DR_ _ _4PL' or Interface Description should begin with 'DR_ _ _4PS' or Interface Description should begin with '_ _ _8ES' or Interface Description should begin with '_ _ _8PL' or Interface Description should begin with '_ _ _8CL' or Interface Description should begin with '_ _ _8CO' or Interface Description should begin with '_ _ _8EO' or Interface Description should begin with 'DR_ _ _8PL' or Interface Description should begin with 'DR_ _ _8CL' or Interface Description should begin with 'DR_ _ _8EL'
Telemedia (MPLS)        Interface Description should contain 'ABTS-ML3-' or Interface Description should contain 'ABTS-ML2-'
Unidentified NNI        Interface Description should contain 'NNI' or Interface Description should  not contain 'planning' or Interface Description should not contain 'reserved'
"""