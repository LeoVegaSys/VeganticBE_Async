import random
from typing import Union
from dataclasses import dataclass

from config.traffic import DATA_SOURCE
from config.scratchpad import USERS, SESSIONS, REQUESTS

@dataclass
class Context:
    user_id: str


class NewQueryRequest:
    def __init__(self, body: Union[dict, None]):
        if not self.is_valid(body):
            return None
        self.user_id = body.get("user_id", f"user_{random.choice(range(USERS))}")
        self.question = body.get("text", "").strip()
        self.request_id = body.get("request_id", f"req_{random.choice(range(REQUESTS))}")
        self.filters = body.get("filters", {})
        self.selected_context = body.get("selected_context", [])
        self.selected_values = body.get("selected_values", [])
        self.session_id = body.get("sessionId", f"sess_{random.choice(range(SESSIONS))}")
        self.data_source = body.get("context", {}).get("data_source", DATA_SOURCE)
        # self.user_response = body.get("user_response", "").strip()
        # _no_summary = not body.get("no_summary", False)
        # self.summarize = body.get("summarize", _no_summary)

    def is_valid(self, body):
        return True if isinstance(body, dict) else False


class UserLoginRequest:
    def __init__(self, body: Union[dict, None]):
        if not self.is_valid(body):
            return None
        self.user_name = body.get('username', '')
        self.password = body.get('password', '')

    def is_valid(self, body):
        return True if isinstance(body, dict) else False


class UserDetailsRequest:
    def __init__(self, body: Union[dict, None]):
        if not self.is_valid(body):
            return None
        self.user_id = int(body.get('userId', 0))

    def is_valid(self, body):
        return True if isinstance(body, dict) else False


class UserSessionsRequest:
    def __init__(self, body: Union[dict, None]):
        if not self.is_valid(body):
            return None
        self.user_id = int(body.get('userId', 0))

    def is_valid(self, body):
        return True if isinstance(body, dict) else False


class NewSessionRequest:
    def __init__(self, body: Union[dict, None]):
        if not self.is_valid(body):
            return None
        self.user_id = int(body.get('userId', 0))
        self.label = body.get('label', '')
        self.networks = body.get('networks', [])
        self.levels = body.get('levels', [])
        self.circle = body.get('circle', [])
        self.services = body.get('services', [])
        self.date_from = body.get('dateFrom', '')
        self.date_to = body.get('dateTo', '')
        self.time_from = body.get('timeStart', '')
        self.time_to = body.get('timeEnd', '')

    def is_valid(self, body):
        return True if isinstance(body, dict) else False


class SessionDetailsRequest:
    def __init__(self, body: Union[dict, None]):
        if not self.is_valid(body):
            return None
        self.session_id = int(body.get('sessionId', 0))

    def is_valid(self, body):
        return True if isinstance(body, dict) else False


class UpdateSessionRequest:
    def __init__(self, body: Union[dict, None]):
        if not self.is_valid(body):
            return None
        # self.session_id = body.get('sessionId', '')
        self.networks = body.get('networks', [])
        self.levels = body.get('levels', [])
        self.circle = body.get('circle', [])
        self.services = body.get('services', [])
        self.date_from = body.get('dateFrom', '')
        self.date_to = body.get('dateTo', '')
        self.time_from = body.get('timeStart', '')
        self.time_to = body.get('timeEnd', '')

    def is_valid(self, body):
        return True if isinstance(body, dict) else False


class ClearSessionRequest:
    def __init__(self, body: Union[dict, None]):
        if not self.is_valid(body):
            return None
        self.clear_messages = body.get('clearMessages', True)

    def is_valid(self, body):
        return True if isinstance(body, dict) else False


class DeleteSessionRequest:
    def __init__(self, body: Union[dict, None]):
        if not self.is_valid(body):
            return None
        self.user_id = int(body.get('userId', 0))

    def is_valid(self, body):
        return True if isinstance(body, dict) else False


class QueryRequest:
    def __init__(self, body: Union[dict, None]):
        if not self.is_valid(body):
            return None
        self.question = body.get("question", "").strip()
        self.user_response = body.get("user_response", "").strip()
        _no_summary = not body.get("no_summary", False)
        self.summarize = body.get("summarize", _no_summary)
        self.request_id = body.get("request_id", f"req_{random.choice(range(REQUESTS))}")
        self.user_context = body.get("context", {})
        self.session_id = body.get("context", {}).get("session_id", f"sess_{random.choice(range(SESSIONS))}")
        self.user_id = body.get("context", {}).get("user_id", f"user_{random.choice(range(USERS))}")
        self.data_source = body.get("context", {}).get("data_source", DATA_SOURCE)
        # UI global filters (networks, levels, circle, services, dateFrom, dateTo,
        # timeStart, timeEnd), at the top level or inside context. Used by src/dip_new.
        self.filters = body.get("filters") or body.get("context", {}).get("filters") or {}

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
        self.proc_func = None
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
            self.config[key] = val.get("server", None)
            """Get MCP query executor function details"""
            self.func = val.get("query_function", None)
            """Get MCP procedure executor function details"""
            self.proc_func = val.get("procedure_function", None)
            """Get MCP API key details"""
            self.key = val.get("query_key", None)
            self.db_name = val.get("query_db", None)
            self.host = val.get("query_host", None)
            self.port = val.get("query_port", None)
        return self
