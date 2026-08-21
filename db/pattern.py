from base_class import AbstractDB
from db.traffic_data_last_3days.src import TrafficDataLastThreeDays





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