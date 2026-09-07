from utils.memoization import memoize, memoization_configuration as m_cfg


@memoize(configuration=m_cfg)
async def get_business():
    return """"""