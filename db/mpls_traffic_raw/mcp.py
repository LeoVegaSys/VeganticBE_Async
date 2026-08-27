from db.mpls_traffic_raw.config import TRAFFIC_DB_NAME, MCP_DB_TYPE

MCP_CONFIG={
    MCP_DB_TYPE:{
        "server":{
                "transport": "http",  # HTTP-based remote server
                # Ensure you start your weather server on port 8000
                "url": "http://127.0.0.1:8080/mcp",
            },
        "query_function": "run_query",
        "query_key": "query",
        "query_db": TRAFFIC_DB_NAME,
    }
}