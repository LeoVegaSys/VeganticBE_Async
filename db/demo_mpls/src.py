import asyncio

from utils.memoization import memoization_configuration as m_cfg, memoize
from utils.store import get_conversation_history
from utils.prompts import (memories_to_chat_msgs, sql_repair_prompt)
from db.demo_mpls.prompts import sql_generate_prompt
from db.demo_mpls.skills import get_business
from db.demo_mpls.schema import get_schema

from db.base_class import AbstractDB
from db.demo_mpls.mcp import MCP_CONFIG
from db.manager import DatabaseManager


class DemoMPLS(AbstractDB):
    def __init__(self):
        self.db_manager = DatabaseManager(MCP_CONFIG)

    def get_db_manager(self):
        return self.db_manager

    async def get_sql_generate_prompt(
            self, request_id: str, user_id: str, session_id: str,
            question: str):
        self.request_id = request_id
        db_type = next(iter(MCP_CONFIG))
        get_schema_coro = asyncio.create_task(get_schema())
        get_business_coro = asyncio.create_task(get_business())
        # get_memories_coro = asyncio.create_task(get_conversation_history(
        #     user_id=user_id, session_id=session_id, params=["answer"]))

        schema = await get_schema_coro
        business_facts = await get_business_coro
        # memories = await get_memories_coro

        # last_conversation = memories_to_chat_msgs(memories)[-1:] if memories else []
        return sql_generate_prompt().invoke({
            "db_type": db_type, "business_facts": business_facts,
            "schema": schema, "question": question,
            # "last_conversation": last_conversation
        }).to_string()


    async def get_sql_repair_prompt(
            self, request_id: str, question: str, query: str, faults: str):
        self.request_id = request_id
        db_type = next(iter(MCP_CONFIG))
        get_schema_coro = asyncio.create_task(get_schema())
        get_business_coro = asyncio.create_task(get_business())
        schema = await get_schema_coro
        business_facts = await get_business_coro

        return sql_repair_prompt().invoke({
            "db_type": db_type, "business_facts": business_facts,
            "schema": schema, "question": question,
            "bad_sql": query, "err": faults}).to_string()


    async def run_query(self, query: str):
        result = await self.db_manager._execute_query(
            uuid=self.request_id, query=query)
        return result


    async def call_procedure(self, proc_name: str, proc_params: list = None):
        result = await self.db_manager._call_proc(
            uuid=self.request_id, proc_name=proc_name, params=proc_params)
        return result
