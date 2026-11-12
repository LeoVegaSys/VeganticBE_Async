from db.demo_mpls.config import TRAFFIC_DB_NAME, MCP_DB_TYPE
from config.mcp import MCP_HOST, MCP_PORT

MCP_CONFIG={
    MCP_DB_TYPE:{
        "server":{
                "transport": "http",  # HTTP-based remote server
                # Ensure you start your weather server on port 8000
                "url": f"http://{MCP_HOST}:{MCP_PORT}/mcp",
            },
        "query_function": "arun_query",
        "procedure_function": "call_procedure",
        "query_key": "query",
        "query_db": TRAFFIC_DB_NAME,
    }
}
