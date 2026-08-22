import asyncio
import functools
from config.scratchpad import SAFE_DELAY

def async_delay(seconds=SAFE_DELAY):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            await asyncio.sleep(seconds)  # Non-blocking pause
            return await func(*args, **kwargs)
        return wrapper
    return decorator