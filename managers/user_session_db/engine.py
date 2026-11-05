import aiomysql

from config.user_sessions import (
    DB_HOST, DB_PORT, DB_NAME, DB_PASSWORD, DB_USER, ROWS_LIMIT
)


class UserSessionsManager:
    def __init__(self, db_conf: dict = None):
        self.db_conf = db_conf or self._user_db_config()

    @staticmethod
    def _user_db_config():
        """Returns User Sessions database configuration"""
        return {
            "host": DB_HOST, "port": int(DB_PORT), "user": DB_USER,
            "password": DB_PASSWORD, "db": DB_NAME,
        }

    async def aget(self, query: str):
        """Retrieves records for given SELECT queries"""
        try:
            async with aiomysql.create_pool(**self.db_conf) as pool:
                async with pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cursor:

                        if "limit" not in query.lower():
                            query += f" LIMIT {ROWS_LIMIT}"

                        await cursor.execute(query)
                        cols = [d[0] for d in cursor.description]
                        cols_dt = [d[1] for d in cursor.description]
                        rows = await cursor.fetchall()
                        rowCount = cursor.rowcount

                        result={
                            "success":True,
                            "columns":cols,
                            "columnTypes":cols_dt,
                            "rows":rows,
                            "rowCount":rowCount
                        }
                        print(f"aget :: {rowCount} rows :: Q {query}")

            # return json.dumps(rows, default=str)
            return result

        except Exception as e:
            raise Exception(f"SELECT Query |{query}| execution failed: {str(e)}")


    async def adelete(self, query: str):
        """Deletes records for given queries"""
        try:
            async with aiomysql.create_pool(**self.db_conf) as pool:
                async with pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cursor:
                        await cursor.execute(query)
                        await conn.commit()
                        print(f"adelete :: {cursor.rowcount} rows :: Q {query}")
            return {'ok': True}
        except Exception as e:
            raise Exception(f"DELETE Query |{query}| execution failed: {str(e)}")


    async def aupdate(self, query: str):
        """Updates records for given INSERT/UPDATE queries"""
        try:
            async with aiomysql.create_pool(**self.db_conf) as pool:
                async with pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cursor:
                        await cursor.execute(query)
                        await conn.commit()
                        print(f"aupdate :: {cursor.rowcount} rows :: Q {query}")
            return {'ok': True}
        except Exception as e:
            raise Exception(f"INSERT/UPDATE Query |{query}| execution failed: {str(e)}")
