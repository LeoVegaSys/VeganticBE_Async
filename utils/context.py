from typing import Union
from dataclasses import dataclass

from config.mcp import MCP_DB_TYPE

@dataclass
class Context:
    user_id: str


class QueryRequest:
    def __init__(self, body: Union[dict, None]):
        if not self.is_valid(body):
            return None
        self.question = body.get("question", "").strip()
        self.user_response = body.get("user_response", "").strip()
        self.mcp_server = body.get("db_type", MCP_DB_TYPE)
        self.summarize = not body.get("no_summary", False)
        self.request_id = body.get("request_id", "")
        self.session_id = body.get("session_id", "")
        self.user_id = body.get("user_id", "")

    def is_valid(self, body):
        return True if isinstance(body, dict) else False


