import json
from typing import Union


def get_mcp_details(mcp_config: dict):
    _server_config = {}
    _func = ""
    _key = ""
    _name = ""
    for key, val in mcp_config.items():
        """Get MCP server details"""
        _name = key
        _server_config[key] = val["server"]
        """Get MCP executor function details"""
        _func = val["query_function"]
        """Get MCP API key details"""
        _key = val["query_key"]
    return (_name, _server_config, _func, _key)

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
        data = [{c: (str(v) if hasattr(v, "isoformat") else v) for c, v in zip(result["columns"], r)} for r in result["rows"]]
        result["data"] = data
        result['tool_id'] = tool_id
        result['tool_name'] = tool_name
        return result
    except Exception as e:
        raise e