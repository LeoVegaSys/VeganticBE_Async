import aiomysql

from config.user_sessions import (
    DB_HOST, DB_PORT, DB_NAME, DB_PASSWORD, DB_USER, ROWS_LIMIT
)


class UserSessionsManager:
    def __init__(self, query: str):
        self.query = query
        self.db_conf = self._user_db_config()

    @staticmethod
    def _user_db_config():
        """Returns User Sessions database configuration"""
        return {
            "host": DB_HOST, "port": int(DB_PORT), "user": DB_USER,
            "password": DB_PASSWORD, "db": DB_NAME,
        }

    async def aget(self):
        """Retrieves records for given SELECT queries"""
        try:
            async with aiomysql.create_pool(**self.db_conf) as pool:
                async with pool.acquire() as conn:
                    async with conn.cursor(aiomysql.DictCursor) as cursor:

                        if "limit" not in self.query.lower():
                            self.query += f" LIMIT {ROWS_LIMIT}"

                        await cursor.execute(self.query)
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
                        print(f"aget :: {rowCount} rows :: Q {self.query}")

            # return json.dumps(rows, default=str)
            return result

        except Exception as e:
            raise Exception(f"Query execution failed: {str(e)}")


    async def adelete(self):
        pass


    async def aupdate(self):
        pass