#!/usr/bin/env python3

### MCP CONFIG
MCP_DB_PATH=""
MCP_DB_URL="http://127.0.0.1:8080/mcp"
# MCP_CONFIG= {
#             # "time": {
#             #     "transport": "stdio",
#             #     "command": "npx",
#             #     "args": ["-y", "@theo.foobar/mcp-time"],
#             # },
#             "duckdb": {
#                 "command": "uvx",
#                 "args": ["mcp-server-motherduck", "--db-path", "./data/duckdb/traffic.db", "--readonly"],
#                 "transport": "stdio"
#             },
#             "mysql": {
#                 "transport": "http",  # HTTP-based remote server
#                 # Ensure you start your weather server on port 8000
#                 "url": "http://127.0.0.1:8080/mcp",
#             }
#         }

MCP_CONFIG={
    "mysql":{
        "server":{
                "transport": "http",  # HTTP-based remote server
                # Ensure you start your weather server on port 8000
                "url": "http://127.0.0.1:8080/mcp",
            },
        "query_function": "run_query",
        "query_key": "query",
    },
    "duckdb":{
        "server": {
                "command": "uvx",
                "args": ["mcp-server-motherduck", "--db-path", "./dump/duckdb/traffic_data_last_3days.db"],
                         #"--max-rows", "10000", "--max-chars", "1000000"],
                         #"--max-rows", "100000", "--max-chars", "10000000"],
                "transport": "stdio"
            },
        "query_function": "execute_query",
        "query_key": "sql",
    },
}

#Valid values : mysql, duckdb, oracle, redis, postgresql
MCP_DB_TYPE="duckdb" 
