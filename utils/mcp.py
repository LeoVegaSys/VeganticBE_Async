import json
from typing import Union


def parse_mcp_proc_response(mcp_result: Union[list, dict, str, None], tool_name: str = "") -> dict:
    """
    Parse MCP Tool Procedure Execution response
    Input args:
        Expected mcp_result structure:
        [
            {'type': 'text',
            'text': '[
                {"id":1,"username":"WWWW","password_hash":"XXXXX","display_name":"EEEEE","created_at":"2026-10-07T06:54:00"}]',
            'id': 'lc_8aa970c6-5273-4a8e-8284-d6969c674d7c'}
        ]
    """

    try:
        result = json.loads(mcp_result[0]['text'])
        tool_id = mcp_result[0]['id']

        result["data"] = result
        result['tool_id'] = tool_id
        result['tool_name'] = tool_name
        return result
    except Exception as e:
        raise e


def parse_mcp_query_response(mcp_result: Union[list, dict, str, None], tool_name: str = "") -> dict:
    """
    Parse MCP Tool Query Execution response
    Input args:
        Expected mcp_result structure:
        [
            {'type': 'text',
            'text': '{
                \n  "success": true,
                \n  "columns": [\n    "LinkType",\n    "Node Name",\n    ...],
                \n  "columnTypes": [\n    "VARCHAR",\n    "VARCHAR",\n    ...],
                \n  "rows": [\n    [\n      "Core",\n      "HYD_OHR_901_...]\n  ],
                \n  "rowCount": 5\n}',
            'id': 'lc_42c9b207-fc49-4e31-a50a-c0fa18ecf9ad'}
            ]
    Intermediate response:
        {
            "success": true,
            "columns": ["NodeNumber", "NodeID", ...],
            "columnTypes": ["SHORT", "VAR_STRING", ...],
            "rows": [["Core", "HYD_OHR_901_...]],
            "data": [{"NodeNumber": 117, "NodeID": "202.123.37.241", ...}],
            "rowCount": 5
        }
    """

    try:
        result = json.loads(mcp_result[0]['text'])
        tool_id = mcp_result[0]['id']

        if any(isinstance(r, list) for r in result["rows"]):
            #If result rows are in list form [value1, value2, value3], add columns as keys
            data = [{c: (str(v) if hasattr(v, "isoformat") else v) for c, v in zip(result["columns"], r)} for r in result["rows"]]
        else:
            #If result rows are in dict form {column: value}
            data = result["rows"]

        result["data"] = data
        result['tool_id'] = tool_id
        result['tool_name'] = tool_name
        return result
    except Exception as e:
        raise e