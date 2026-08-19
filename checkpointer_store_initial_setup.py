from langgraph.store.redis import RedisStore
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
import asyncio

from config.store import REDIS_HOST, REDIS_PORT, STORE_DB
from config.checkpointer import *


async def main():
    """
    To be performed ONLY ONCE, to set up database schema migrations in REDIS
    RUN before first usage of checkpoint or store in langgraph
    """
    redis_uri = f"{STORE_DB}://{REDIS_HOST}:{REDIS_PORT}"
    pg_uri = f"{CHECKPOINTER_DB}://{PG_USER}:{PG_PWD}@{PG_HOST}:{PG_PORT}/{PG_DB_NAME}"
    conn_kwargs = {
        "autocommit": True,
        "prepare_threshold": 0,
    }
    # with RedisStore.from_conn_string(redis_uri) as store:
        # store.setup()
        # Remember to check TTL config before uncommenting above setup function
        # pass

    async with AsyncConnectionPool(conninfo=pg_uri, max_size=4,
                                   kwargs=conn_kwargs) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        print(f"Starting setup :: {pg_uri}")
        checkpointer.setup()
        print(f"Setup done!!!")
        pass


if __name__ == "__main__":
    asyncio.run(main())