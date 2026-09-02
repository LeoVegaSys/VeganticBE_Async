from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from utils.mcp import parse_mcp_query_response
from utils.context import MCPConfigParser
from utils.memoization import memoize, memoization_configuration as m_cfg


class DatabaseManager:

    def __init__(self, mcp_config: dict):
        self.mcp_config = mcp_config


    @memoize(configuration=m_cfg)
    async def _execute_query(self, uuid: str, query: str):
        """ Calls Database MCP server and returns query results"""
        try:
            tool_params = {}
            mcp_obj = MCPConfigParser(self.mcp_config).get_mcp_details()
            # mcp_server, _mcp_config, mcp_func, mcp_key, mcp_db = get_mcp_details(
            #     self.mcp_config)
            mcp_client = MultiServerMCPClient(mcp_obj.config)

            async with mcp_client.session(
                server_name=mcp_obj.name) as session:
                # Get tools
                # tools = await mcp_client.get_tools(server_name=mcp_server)
                # result = await mcp_client.call_tool("run_query", query)
                tools = await load_mcp_tools(session)
                run_tool = next(t for t in tools if t.name==mcp_obj.func)
                tool_params[mcp_obj.key] = query
                tool_params["database"] = mcp_obj.db_name
                tool_params["host"] = mcp_obj.host
                tool_params["port"] = mcp_obj.port
                print(f"DBM :: tool called :: {run_tool.name} :: params :: {tool_params}")
                result = await run_tool.ainvoke(tool_params)
                print(f"\nDBM :: _execute_query :: Result: {result}")
                return parse_mcp_query_response(result, run_tool.name)

        except Exception as e :
            err_msg = f"MCP :: Error encountered while executing {mcp_obj.name} :: query {query} : {str(e)}"
            print(err_msg)
            raise e


    async def _get_schema(self, uuid: str):
        """ 
        Calls Database MCP server and returns schema results.
        Make sure to make the database schema available in the MCP server
        """
        try:
            mcp_obj = MCPConfigParser(self.mcp_config).get_mcp_details()
            # mcp_server, _mcp_config, _, _, mcp_db = get_mcp_details(
            #                 self.mcp_config)
            mcp_client = MultiServerMCPClient(mcp_obj.config)

            async with mcp_client.session(server_name=mcp_obj.name) as session:
                schema = await session.read_resource(f"schema://{mcp_obj.db_name}")
                result = schema.contents[0].text
            print(f"\nDBM :: _get_schema :: Result: {result}")
            return result

        except Exception as e :
            err_msg = f"MCP :: Error encountered while getting {mcp_obj.name} :: {mcp_obj.db_name} schema : {str(e)}"
            print(err_msg)
            raise e
