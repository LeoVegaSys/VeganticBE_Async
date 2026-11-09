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


    async def aupd_del(self, q_list: list):
        """Updates records for given DELETE/UPDATE queries"""
        try:
            async with aiomysql.create_pool(**self.db_conf) as pool:
                async with pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cursor:
                        for query in q_list:
                            await cursor.execute(query)
                            print(f"aupd_del :: {cursor.rowcount} rows :: Q {query}")
                        await conn.commit()
            return {'ok': True}
        except Exception as e:
            raise Exception(f"UPDATE/DEL Query execution failed: {str(e)}")


    async def ainsert(self, q_list: list):
        """Inserts records for given INSERT queries"""
        try:
            new_id = 0
            async with aiomysql.create_pool(**self.db_conf) as pool:
                async with pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cursor:
                        for query in q_list:
                            await cursor.execute(query)
                            new_id = cursor.lastrowid
                            print(f"ainsert :: {cursor.rowcount} rows :: Q {query}")
                            print(f"ainsert :: ID {new_id}")
                        await conn.commit()
            print(f"ainsert 2 :: ID {new_id}")
            return {'ok': True, 'new_id': new_id}
        except Exception as e:
            raise Exception(f"INSERT Query execution failed: {str(e)}")
