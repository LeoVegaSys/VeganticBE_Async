import json
import asyncio

from langgraph.store.redis.aio import AsyncRedisStore

from config.redis import *
from config.llm import OLLAMA_KEEP_ALIVE

REDIS_STORE_URI = f"redis://{REDIS_HOST}:{REDIS_PORT}"


def get_ttl_config():
    return {
    "default_ttl": int(REDIS_TTL),      # Expire data after REDIS_TTL minutes
    "refresh_on_read": True             #TRUE to Reset expiration timer on each read
}


async def manage_store(user_id: str):
    """
    Clear older records. Store size max KEEP_THRESHOLD
    Check counts of each namespace, Sort by updated_at asc
    Keep first KEEP_FIRST_N and latest KEEP_LAST_N
    """
    try:
        async with AsyncRedisStore.from_conn_string(REDIS_STORE_URI) as store:
            namespaces = await store.alist_namespaces(suffix=(user_id,))
            for ns in namespaces:
                results = await store.asearch(ns, limit=50)
                print(f"store :: manage :: UID {user_id} :: NS {ns} :: LEN {len(results)}")
                if len(results) > KEEP_THRESHOLD:
                    r_sorted = sorted(results, key=lambda x: x.updated_at)
                    for s in r_sorted[KEEP_FIRST_N: -KEEP_LAST_N]:
                        await store.adelete(ns, key=s.key)
    except Exception as e:
        print(f"Error occurred during store manage : {str(e)}")
        return False


async def write_to_store(user_id: str, category: str, param: str, data: str):
    from uuid import uuid4
    try:
        async with AsyncRedisStore.from_conn_string(REDIS_STORE_URI) as store:
            await store.aput(
                namespace=(category, user_id),
                key=str(uuid4()),
                value={param : data}
            )
    except Exception as e:
        print(f"Error occurred during store write : {str(e)}")


async def add_to_memories(user_id: str, param_key: str, data: dict,
                          fields_to_copy: list = []):
    '''
    Writes user memories to store
    Args:
        user_id : User identifier
        fields_to_copy : List of keys to be stored as part of data
        param_key : Key identifier for memory
        data : input dataset to be stored fully or partially
    If fields_to_copy is provided, only a subset of result is stored
    '''
    # Pull specific key-value pairs from input if required
    r = {f:data[f] for f in fields_to_copy if f in data} if fields_to_copy \
        else data
    # Stringify data for storage
    try:
        res = r if isinstance(r, str) else json.dumps(r)
    except Exception as e:
        print(f"Store W :: JSON conversion failed for {r} with error {str(e)}")
        return
    await write_to_store(user_id=user_id, category=HISTORY, param=param_key, 
                         data=res)


async def clear_store(user_id: str, category: str = ""):
    """
    If category is provided, deletes all category records ONLY for user.
    If category is not provided, deletes all store records for ALL categories for user.
    """
    try:
        async with AsyncRedisStore.from_conn_string(REDIS_STORE_URI) as store:
            if category:
                namespaces = [(category, user_id)]
            else:
                namespaces = await store.alist_namespaces(suffix=(user_id,))
            for ns in namespaces:
                results = await store.asearch(ns, limit=50)
                print(f"store :: clear :: UID {user_id} :: NS {ns} :: LEN {len(results)}")
                for r in results:
                    await store.adelete(ns, key=r.key)
    except Exception as e:
        print(f"Error occurred during store clear : {str(e)}")


async def read_from_store(user_id: str, category: str, params: list[str] = []) -> list[dict]:
    """
    If params is provided, Returns category records matching the list of text params.
    If params is not provided, Returns all records for the category.
    """
    result_set = []
    try:
        async with AsyncRedisStore.from_conn_string(REDIS_STORE_URI) as store:
            namespace = (category, user_id)
            results = await store.asearch(namespace, limit=50)
            print(f"store :: read :: UID {user_id} :: NS {namespace} :: LEN {len(results)}")
            if results:
                if params:
                    result_set = [r for r in results for p in params if p in r.value]
                else:
                    result_set = [r for r in results]
            return result_set
    except Exception as e:
        print(f"Error occurred during store read : {str(e)}")
        return []


async def get_conversation_history(user_id: str, params: list[str]) -> str:
    """
    Returns key-value pairs in flattened string, stored as part of previous conversations 
    """
    history = ""
    # if not warmup_done(user_id):
    memories = await read_from_store(user_id=user_id, category=HISTORY, params=params)
    if memories:
        history = "\n".join([f"{k.upper()}:{v}" for m in memories for k,v in m.value.items()])
    print(f"GCM :: store :: {HISTORY}, {user_id} :: MemLen :: {len(memories)}")
    return history


async def warmup_done(user_id: str):
    """Returns True if warmup has been performed in last 30 mins"""
    from datetime import datetime, timezone
    warmed_up = False
    # Check if warmup prompt already loaded
    warmup_done = await read_from_store(user_id=user_id, category=WARMUP)
    
    if warmup_done:
        # Calculate minutes since last warmup
        # If time over KEEP_ALIVE, warmup to be performed
        keep_alive_mins = get_keep_alive_in_mins()
        last_run = warmup_done[0].updated_at.replace(tzinfo=timezone.utc)
        mins_since_last_run = ((datetime.now(timezone.utc) - last_run).total_seconds())//60
        if mins_since_last_run > keep_alive_mins:
            print(f"Warmup completed for user {user_id} more than {keep_alive_mins} mins ago.")
        else:
            print(f"Warmup already completed for user {user_id}.")
            warmed_up = True

    if not warmed_up:   # CLEAR OLD WARMUP ENTRIES IF ANY
        print(f"Warmup not completed for user {user_id}.")
        await clear_store(user_id=user_id, category=WARMUP)
        await write_to_store(user_id=user_id, category=WARMUP, param="warmup", data="true")

    return warmed_up


def get_keep_alive_in_mins():
    import re
    units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400, 'w': 604800}
    is_alphanum = any(c.isalpha() for c in OLLAMA_KEEP_ALIVE)
    if is_alphanum:
        total_seconds = sum(
            int(value) * units[unit.lower()] 
            for value, unit in re.findall(r'(\d+)([dhmshw])', OLLAMA_KEEP_ALIVE)
        )
        return (total_seconds//60)
    else:
        return int(OLLAMA_KEEP_ALIVE)