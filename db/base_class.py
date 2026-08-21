from abc import ABC, abstractmethod


class AbstractDB(ABC):

    def get_db_type(self):
        pass

    async def get_sql_generate_prompt(self, **kwargs):
        pass
    
    async def get_sql_repair_prompt(self, **kwargs):
        pass