import asyncio

from utils.memoization import memoization_configuration as m_cfg, memoize
from utils.store import get_conversation_history
from utils.prompts import (memories_to_chat_msgs, sql_repair_prompt)

from db.base_class import AbstractDB
from db.vegayan_mpls.config import TRAFFIC_DB_NAME
from db.vegayan_mpls.mcp import MCP_CONFIG
from db.vegayan_mpls.skills import get_business
from db.vegayan_mpls.prompts import sql_generate_prompt
from db.manager import DatabaseManager


class VegayanMPLS(AbstractDB):
    def __init__(self):
        self.db_manager = DatabaseManager(MCP_CONFIG)

    def get_db_manager(self):
        return self.db_manager

    async def get_sql_generate_prompt(
                self, request_id: str, user_id: str, session_id: str,
                question: str):
        pass

    async def get_sql_repair_prompt(
                self, request_id: str, question: str, query: str, faults: str):
        pass
