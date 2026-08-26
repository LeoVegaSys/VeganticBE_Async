import json
import asyncio
from uuid import uuid4

from langgraph.store.redis.aio import AsyncRedisStore

from config.store import (KEEP_FIRST_N, KEEP_LAST_N, KEEP_THRESHOLD,
                          REDIS_HOST, REDIS_PORT, REDIS_TTL, STORE_DB, HISTORY,
                          WARMUP, USERS)
from config.llm import OLLAMA_KEEP_ALIVE

REDIS_STORE_URI = f"{STORE_DB}://{REDIS_HOST}:{REDIS_PORT}"


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
    filters = {"user_id": user_id}
    try:
        async with AsyncRedisStore.from_conn_string(REDIS_STORE_URI) as store:
            namespaces = await store.alist_namespaces(suffix=(USERS,))
            for ns in namespaces:
                results = await store.asearch(ns, filter=filters, limit=KEEP_THRESHOLD)
                print(f"store manage :UID: {user_id} :NS: {ns} :F: {filters} :LEN: {len(results)}")
                if len(results) > KEEP_THRESHOLD:
                    r_sorted = sorted(results, key=lambda x: x.updated_at)
                    to_delete = [store.adelete(ns, key=s.key) for s in r_sorted[KEEP_FIRST_N: -KEEP_LAST_N]]
                    await asyncio.gather(*to_delete)
    except Exception as e:
        print(f"Error occurred during store manage : {str(e)}")
        return False


async def write_to_store(category: str, payload: dict):
    try:
        async with AsyncRedisStore.from_conn_string(REDIS_STORE_URI) as store:
            print(f"store write :C: {category} :P: {payload}")
            await store.aput(
                namespace=(category, USERS),
                key=str(uuid4()),
                value=payload
            )
    except Exception as e:
        print(f"Error occurred during store write : {str(e)}")


async def clear_store(user_id: str, category: str = ""):
    """
    If category is provided, deletes all category records ONLY for user.
    If category is not provided, deletes all store records for ALL categories for user.
    """
    filters = {"user_id": user_id}
    try:
        async with AsyncRedisStore.from_conn_string(REDIS_STORE_URI) as store:
            if category:
                namespaces = [(category, USERS)]
            else:
                namespaces = await store.alist_namespaces(suffix=(USERS,))
            for ns in namespaces:
                results = await store.asearch(ns, filter=filters, limit=KEEP_THRESHOLD)
                print(f"store clear :UID: {user_id} :F: {filters} :NS: {ns} :LEN: {len(results)}")
                to_delete = [store.adelete(ns, key=r.key) for r in results]
                await asyncio.gather(*to_delete)
    except Exception as e:
        print(f"Error occurred during store clear : {str(e)}")


async def read_from_store(user_id: str, category: str, params: list[str] = []) -> list[dict]:
    """
    If params is provided, Returns category records matching the list of text params.
    If params is not provided, Returns all records for the category.
    """
    result_set = []
    for param in params:
        filters = {"user_id": user_id, "type": param}
        try:
            async with AsyncRedisStore.from_conn_string(REDIS_STORE_URI) as store:
                namespace = (category, USERS)
                results = await store.asearch(namespace, filter=filters, limit=KEEP_THRESHOLD)
                print(f"store read :UID: {user_id} :F: {filters} :NS: {namespace} :LEN: {len(results)}")
                result_set += results
        except Exception as e:
            print(f"Error occurred during store read : {str(e)}")
    return result_set


async def get_conversation_history(user_id: str, params: list[str]) -> list[dict]:
    """
    Returns previous user conversations 
    """
    # if not warmup_done(user_id):
    memories = await read_from_store(user_id=user_id, category=HISTORY, params=params)
    return memories


def create_memory_payload(param_type: str, user_id: str, session_id: str, 
                          request_id: str, data: dict, fields: list = []):
    payload = {}
    payload["type"] = param_type
    payload["user_id"] = user_id
    payload["session_id"] = session_id
    payload["request_id"] = request_id
    r = {f:data[f] for f in fields if f in data} if fields else data
    try:    # Stringify data for storage
        result = r if isinstance(r, str) else json.dumps(r)
    except Exception as e:
        print(f"Store W :: JSON conversion failed for {r} with error {str(e)}")
        result = None
    payload["data"] = result
    return payload
