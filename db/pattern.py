from abc import ABC, abstractmethod

from db.traffic_data_last_3days.src import TrafficDataLastThreeDays


class AbstractDB(ABC):

    @property
    @abstractmethod
    def db_type(self):
        pass

    async def get_sql_generate_prompt(self, **kwargs):
        pass
    
    async def get_sql_repair_prompt(self, **kwargs):
        pass



class DBFactory:
    _databases = {
        "traffic_data_last_3days": TrafficDataLastThreeDays,
        # "mcp_demo": McpDemo
    }

    @staticmethod
    def get(db_name: str) -> AbstractDB:
        db_class = DBFactory._databases.get(db_name)
        if not db_class:
            raise ValueError(f"Unknown Database Source: {db_name}")
        return db_class()