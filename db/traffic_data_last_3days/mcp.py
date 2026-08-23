from pathlib import Path

fp = str(Path(__file__).parent.resolve())

MCP_CONFIG={
    "duckdb":{
            "server": {
                    "command": "uvx",
                    "args": ["mcp-server-motherduck", "--db-path", f"{fp}/data/traffic_data_last_3days.db"],
                             #"--max-rows", "10000", "--max-chars", "1000000"],
                             #"--max-rows", "100000", "--max-chars", "10000000"],
                    "transport": "stdio"
                },
            "query_function": "execute_query",
            "query_key": "sql",
        }
}