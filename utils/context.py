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
