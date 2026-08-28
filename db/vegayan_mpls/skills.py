from utils.memoization import memoize, memoization_configuration as m_cfg


@memoize(configuration=m_cfg)
async def get_business():
    return """
The interface naming convention differs by network vendor. The Flag or interface classification should be determined based on the vendor-specific interface naming patterns below. Interface Name startswith or contains below keywords for Bundle and Physical Type

Flag Identification Conditions-
Vendor  Bundle Interface Naming Convention      Physical Interface Naming Convention
Cisco   Bundle-Ether                            Hun, FourHun, TwentyFive, Ten, Gig
Juniper ae                                      et, xe, ge
Nokia   Port lag, Port x/x/cx (x is number)     Port x/x/x, Port x/x/cx/x
Huawei  100G                                    Gig

Logical Type
For Cisco, Huawei, and Juniper, logical interfaces are physical interfaces with a '.' in the name
For Nokia and Alcatel, logical interfaces are physical interfaces with a ':' in the name

Bundle with Dot Type
Includes bundle interfaces with either '.' or ':' in their names
"""