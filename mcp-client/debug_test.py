import asyncio
import os
import json
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()

async def test_mcp_connection():
    """Simple test to debug MCP connection"""
    exit_stack = AsyncExitStack()
    
    try:
        print("Step 1: Setting up server parameters...")
        server_dir = os.path.abspath("../mcp-server")
        server_file = "server.py"
        
        print(f"Server directory: {server_dir}")
        print(f"Server file: {server_file}")
        
        # Test the command we're going to use
        command_to_run = f"cd /d {server_dir} && uv run mcp run {server_file}"
        print(f"Command: cmd /c \"{command_to_run}\"")
        
        server_params = StdioServerParameters(
            command="cmd",
            args=["/c", command_to_run],
            env=None
        )
        
        print("Step 2: Starting server...")
        stdio_transport = await exit_stack.enter_async_context(stdio_client(server_params))
        stdio, write = stdio_transport
        
        print("Step 3: Creating session...")
        session = await exit_stack.enter_async_context(ClientSession(stdio, write))
        
        print("Step 4: Initializing session...")
        await session.initialize()
        
        print("Step 5: Listing tools...")
        response = await session.list_tools()
        tools = response.tools
        print(f"Available tools: {[tool.name for tool in tools]}")
        
        print("Step 6: Testing direct tool call...")
        result = await session.call_tool("get_part_detail", {"part_select_number": "PS11752778"})
        print(f"Tool result type: {type(result)}")
        print(f"Tool result content: {result.content}")
        
    except Exception as e:
        print(f"Error at step: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await exit_stack.aclose()

if __name__ == "__main__":
    asyncio.run(test_mcp_connection())
