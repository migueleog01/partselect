
import asyncio
import sys
import os
import json
import logging
from typing import Optional
from contextlib import AsyncExitStack
from datetime import datetime

from fastmcp import Client
from openai import OpenAI
from dotenv import load_dotenv

# Set up client logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - CLIENT - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('client_debug.log', encoding='utf-8')
    ]
)
client_logger = logging.getLogger('mcp_client')

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize FastMCP client
        self.client = None
        self.deepseek = OpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )
        
        # Conversation context
        self.conversation_history = []
        self.system_message = {
            "role": "system",
            "content": """You are a professional appliance repair assistant specialized EXCLUSIVELY for Refrigerator and Dishwasher repairs with access to comprehensive PartSelect.com data through specialized tools.

STRICT SPECIALIZATION POLICY:
- You can ONLY help with REFRIGERATOR and DISHWASHER repairs and parts
- If users ask about any other appliances (washer, dryer, oven, microwave, etc.), politely decline
- Say: "Sorry, I can only help you with Refrigerator or Dishwasher repairs. Please ask about refrigerator or dishwasher issues."
- Do NOT call tools for unsupported appliances - the tools will reject them

CRITICAL: TOOL ERROR HANDLING:
- If a tool returns an error message saying "Sorry, I can only help with refrigerator or dishwasher", STOP IMMEDIATELY
- Do NOT provide any additional information about the part from your training data
- Do NOT explain what the part is for or what models it's compatible with
- Simply relay the tool's error message and ask for refrigerator/dishwasher questions instead
- NEVER supplement tool error responses with your own knowledge

CRITICAL INSTRUCTIONS FOR TOOL DATA USAGE:
- When you receive data from tools, present it COMPLETELY and DIRECTLY to the user
- DO NOT summarize, condense, or paraphrase the tool data - SHOW EVERYTHING
- If user asks for "all symptoms" or "all issues", show EVERY SINGLE ITEM from the tool response
- NEVER omit any items from lists - if the tool returns 12 items, show all 12
- Count the items in tool responses and verify you show the same number
- Preserve the exact structure, details, and completeness of the tool data
- Your role is to organize and format the data clearly, NOT to reduce or filter it
- When in doubt, show MORE data rather than less

RESPONSE GUIDELINES - MATCH USER INTENT:
- FOCUS on what the user specifically asked for - don't dump all data
- If user asks about INSTALLATION: show only installation videos, difficulty, time estimate, and installation steps
- If user asks about COMPATIBILITY: show only compatible models and part numbers
- If user asks about PRICE: show only pricing, availability, and stock status
- If user asks about SYMPTOMS: show only what problems this part fixes
- If user asks for GENERAL INFO or "details": then provide comprehensive information
- Use bullet points, numbered lists, or tables to organize information
- Always include the part name and number for context
- Add helpful context ONLY if directly related to the user's specific question

EXAMPLES:
- "How to install PS123?" → Show: part name, difficulty, time, installation videos, basic steps
- "What models work with PS123?" → Show: part name, compatible model list
- "How much is PS123?" → Show: part name, price, availability, stock status
- "What does PS123 fix?" → Show: part name, symptoms it addresses, problems it solves

WHEN TOOLS RETURN ERRORS:
- If tool returns an error about unsupported appliances, respond ONLY with the error message
- Do NOT add any information from your training data about the part or appliance
- Do NOT explain what the part does or what it's for
- End your response by asking for refrigerator or dishwasher questions
- Example: "Sorry, I can only help you with Refrigerator or Dishwasher repairs. Please ask about refrigerator or dishwasher issues."

TOOL USAGE:
- Use get_repair_guides ONLY for Refrigerator or Dishwasher troubleshooting
- Use get_part_detail ONLY for Refrigerator or Dishwasher parts from PartSelect.com
- Call tools when users ask about symptoms, repairs, parts, or troubleshooting for supported appliances
- Remember conversation context to provide consistent help across interactions

Your goal: Be the specialized bridge between users and the Refrigerator/Dishwasher repair database, ensuring they get complete, accurate information for ONLY these supported appliances."""
        }
        
        # Initialize conversation with system message
        self.conversation_history.append(self.system_message)

    async def connect_to_http_server(self, server_url: str = "http://127.0.0.1:8000/mcp"):
        """Connect to an MCP server via HTTP using FastMCP client
        
        Args:
            server_url: URL of the HTTP MCP server (default: http://127.0.0.1:8000/mcp)
        """
        client_logger.info(f"Connecting to HTTP MCP server at: {server_url}")
        
        try:
            # Create FastMCP client
            self.client = Client(server_url)
            
            # Test connection by listing tools
            async with self.client:
                tools = await self.client.list_tools()
                client_logger.info(f"Connected! Available tools: {[tool.name for tool in tools]}")
                print(f"✅ Connected to HTTP MCP server!")
                print(f"🔗 Server URL: {server_url}")
                print(f"🛠️  Available tools: {[tool.name for tool in tools]}")
            
        except Exception as e:
            client_logger.error(f"Failed to connect to HTTP server: {e}")
            print(f"❌ Connection failed: {e}")
            raise

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        # For FastMCP servers, use uv run mcp dev
        if is_python and "server.py" in server_script_path:
            # Get absolute path to server directory and file
            server_dir = os.path.abspath(os.path.dirname(server_script_path))
            server_file = os.path.basename(server_script_path)
            
            # Use cmd /c to change directory and run uv command on Windows
            # Match the Inspector's command format: run --with mcp mcp run server.py
            if os.name == 'nt':  # Windows
                server_params = StdioServerParameters(
                    command="cmd",
                    args=["/c", f"cd /d {server_dir} && uv run --with mcp mcp run {server_file}"],
                    env=None
                )
            else:  # Unix/Linux/Mac
                server_params = StdioServerParameters(
                    command="bash",
                    args=["-c", f"cd {server_dir} && uv run --with mcp mcp run {server_file}"],
                    env=None
                )
        else:
            command = "python" if is_python else "node"
            server_params = StdioServerParameters(
                command=command,
                args=[server_script_path],
                env=None
            )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    def _manage_context_length(self):
        """Keep conversation history within reasonable limits"""
        # Keep system message + last 20 exchanges (40 messages)
        if len(self.conversation_history) > 41:  # system + 40 messages
            # Keep system message and last 20 exchanges
            system_msg = self.conversation_history[0]
            recent_messages = self.conversation_history[-40:]
            self.conversation_history = [system_msg] + recent_messages

    async def process_query(self, query: str) -> str:
        """Process a query using DeepSeek and available tools with conversation context"""
        
        client_logger.info(f"=== USER QUERY ===")
        client_logger.info(f"Query: {query}")
        client_logger.info(f"Timestamp: {datetime.now()}")
        client_logger.info(f"===================")
        
        # Add user query to conversation history
        user_message = {"role": "user", "content": query}
        self.conversation_history.append(user_message)
        
        # Manage context length
        self._manage_context_length()
        
        # Get available tools using FastMCP client
        async with self.client:
            tools = await self.client.list_tools()
            available_tools = [{
                "type": "function", 
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            } for tool in tools]

        # Use conversation history for context
        messages = self.conversation_history.copy()

        # Initial DeepSeek API call with full context
        response = self.deepseek.chat.completions.create(
    model="deepseek-chat",
            max_tokens=1000,
            messages=messages,
            tools=available_tools,
            tool_choice="auto"
        )

        # Process response and handle tool calls
        final_text = []
        assistant_response = ""
        
        message = response.choices[0].message
        
        if message.content:
            final_text.append(message.content)
            assistant_response = message.content
        
        if message.tool_calls:
            # Add assistant message to conversation history
            assistant_msg = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": message.tool_calls
            }
            messages.append(assistant_msg)
            
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)  # Parse JSON string
                
                # Remove the debug line that shows tool calls in the response
                # final_text.append(f"\n[Calling tool {tool_name} with args {tool_args}]")
                
                # Execute tool call
                try:
                    client_logger.info(f"=== TOOL CALL ===")
                    client_logger.info(f"Tool: {tool_name}")
                    client_logger.info(f"Args: {tool_args}")
                    client_logger.info(f"=================")
                    
                    # Call tool using FastMCP client
                    async with self.client:
                        result = await self.client.call_tool(tool_name, tool_args)
                    
                    client_logger.info(f"=== TOOL RESULT ===")
                    client_logger.info(f"Tool: {tool_name}")
                    client_logger.info(f"Success: True")
                    client_logger.info(f"Result length: {len(str(result.content))}")
                    client_logger.info(f"Result preview: {str(result.content)[:200]}...")
                    client_logger.info(f"===================")
                    
                except Exception as e:
                    client_logger.error(f"=== TOOL ERROR ===")
                    client_logger.error(f"Tool: {tool_name}")
                    client_logger.error(f"Error: {str(e)}")
                    client_logger.error(f"==================")
                    
                    result = type('obj', (object,), {'content': f"Error: {str(e)}"})()  # Mock result object
                
                # Add tool result to conversation
                tool_result_msg = {
                    "role": "tool",
                    "content": str(result.content),
                    "tool_call_id": tool_call.id
                }
                messages.append(tool_result_msg)
            
            # Get next response from DeepSeek
            response = self.deepseek.chat.completions.create(
    model="deepseek-chat",
                max_tokens=1000,
                messages=messages,
                tools=available_tools
            )
            
            final_response = response.choices[0].message.content
            final_text.append("\n" + final_response)
            assistant_response += "\n" + final_response
            
            client_logger.info(f"=== FINAL RESPONSE ===")
            client_logger.info(f"Response length: {len(final_response)}")
            client_logger.info(f"Response: {final_response[:300]}...")
            client_logger.info(f"======================")
            
            # Update conversation history with complete assistant response
            self.conversation_history.append(assistant_msg)
            for tool_msg in messages[len(self.conversation_history):]:
                if tool_msg["role"] == "tool":
                    self.conversation_history.append(tool_msg)
            self.conversation_history.append({"role": "assistant", "content": final_response})
        else:
            # No tool calls, just add the assistant response to history
            self.conversation_history.append({"role": "assistant", "content": assistant_response})

        return "\n".join(final_text)

    def save_conversation(self, filename: str = None):
        """Save conversation history to a file"""
        if filename is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"conversation_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, indent=2, ensure_ascii=False)
            print(f"✅ Conversation saved to {filename}")
        except Exception as e:
            print(f"❌ Failed to save conversation: {e}")

    def load_conversation(self, filename: str):
        """Load conversation history from a file"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                self.conversation_history = json.load(f)
            print(f"✅ Conversation loaded from {filename}")
            print(f"📚 Loaded {len(self.conversation_history)} messages")
        except Exception as e:
            print(f"❌ Failed to load conversation: {e}")

    def show_context_summary(self):
        """Show a summary of the current conversation context"""
        total_messages = len(self.conversation_history)
        user_messages = sum(1 for msg in self.conversation_history if msg["role"] == "user")
        assistant_messages = sum(1 for msg in self.conversation_history if msg["role"] == "assistant")
        tool_calls = sum(1 for msg in self.conversation_history if msg["role"] == "tool")
        
        print(f"\n📊 Context Summary:")
        print(f"   Total messages: {total_messages}")
        print(f"   User queries: {user_messages}")
        print(f"   Assistant responses: {assistant_messages}")
        print(f"   Tool calls: {tool_calls}")

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        print("\nExample queries:")
        print("  - Get details for part PS11752778")
        print("  - Show me repair guides for refrigerators")
        print("  - What are common dishwasher problems?")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break
                elif not query:
                    continue

                response = await self.process_query(query)
                print("\n" + response)

            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"\nError: {str(e)}")
                client_logger.error(f"Chat loop error: {e}")
                import traceback
                client_logger.error(f"Traceback: {traceback.format_exc()}")

    async def cleanup(self):
        """Clean up resources"""
        # FastMCP client handles cleanup automatically with async context manager
        pass

async def main():
    # Connect to HTTP MCP server instead of stdio
    server_url = "http://127.0.0.1:8000/mcp"
    
    print("🚀 Starting MCP Client...")
    print(f"🔗 Connecting to: {server_url}")
    print("💡 Make sure your MCP server is running with:")
    print("   cd mcp-server && fastmcp run server.py:mcp --transport http --port 8000")
    print()

    client = MCPClient()
    try:
        await client.connect_to_http_server(server_url)
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())