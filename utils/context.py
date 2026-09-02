import random
from typing import Union
from dataclasses import dataclass

from config.traffic import DATA_SOURCE
from config.scratchpad import USERS, SESSIONS, REQUESTS

@dataclass
class Context:
    user_id: str


class QueryRequest:
    def __init__(self, body: Union[dict, None]):
        if not self.is_valid(body):
            return None
        self.question = body.get("question", "").strip()
        self.user_response = body.get("user_response", "").strip()
        _no_summary = body.get("no_summary", False)
        self.summarize = not body.get("summarize", _no_summary)
        self.request_id = body.get("request_id", f"req_{random.choice(range(REQUESTS))}")
        self.user_context = body.get("context", {})
        self.session_id = body.get("context", {}).get("session_id", f"sess_{random.choice(range(SESSIONS))}")
        self.user_id = body.get("context", {}).get("user_id", f"user_{random.choice(range(USERS))}")
        self.data_source = body.get("context", {}).get("data_source", DATA_SOURCE)

    def is_valid(self, body):
        return True if isinstance(body, dict) else False


class SummarizeRequest:
    def __init__(self, body: Union[dict, None]):
        if not self.is_valid(body):
            return None
        self.request_ids = body.get('request_ids', [])
        self.session_id = body.get('request_ids', "")
        self.user_id = body.get('request_ids', "")

    def is_valid(self, body):
        return True if isinstance(body, dict) else False


class MCPConfigParser:
    """
    Parses MCP config
    Input:
        mcp_config: dict -> MCP Configuration with additional details
    Returns:
        name: str -> Database type (e.g. mysql, duckdb)
        config: dict -> MCP Configuration details
        func: str -> Database query execution function name
        key: str -> Database query execution function parameter name
        db_name: str | None -> Database name to connect to
        host: str | None -> Database Host to connect to
        port: int -> Database Port to connect to
    """
    def __init__(self, mcp_input: dict):
        self.body = mcp_input
        if not self.is_valid():
            return None
        self.name = None
        self.config = {}
        self.func = None
        self.key = None
        self.db_name = None
        self.host = None
        self.port = 0

    def is_valid(self):
        return True if isinstance(self.body, dict) else False

    def get_mcp_details(self):
        for key, val in self.body.items():
            self.name = key
            """Get MCP server details"""
            self.config[key] = val["server"]
            """Get MCP executor function details"""
            self.func = val["query_function"]
            """Get MCP API key details"""
            self.key = val["query_key"]
            self.db_name = val["query_db"] if "query_db" in val else None
            self.host = val["query_host"] if "query_host" in val else None
            self.port = val["query_port"] if "query_port" in val else None