from db.base_class import AbstractDB
from db.traffic_data_last_3days.src import TrafficDataLastThreeDays
from db.mpls_traffic_raw.src import MplsTrafficRaw
from db.vegayan_mpls.src import VegayanMPLS


class DBFactory:
    _databases = {
        "traffic_data_last_3days": TrafficDataLastThreeDays,
        "vegayan_mpls": VegayanMPLS,
        "mpls_traffic_raw": MplsTrafficRaw
    }

    @staticmethod
    def get(db_name: str) -> AbstractDB:
        db_class = DBFactory._databases.get(db_name)
        if not db_class:
            raise ValueError(f"Unknown Database Source: {db_name}")
        return db_class()