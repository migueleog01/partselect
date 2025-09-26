#!/usr/bin/env python3
"""
FastAPI Bridge Server for PartSelect Case Study
Bridges React frontend with MCP server via HTTP
"""

import asyncio
import sys
import os
import logging
from typing import Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Add mcp-client to path to import our client
sys.path.insert(0, os.path.abspath('../mcp-client'))
import importlib.util

# Import MCPClient from the mcp-client main.py file
spec = importlib.util.spec_from_file_location("mcp_client_main", "../mcp-client/main.py")
mcp_client_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcp_client_module)
MCPClient = mcp_client_module.MCPClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - API-BRIDGE - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api_bridge.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# MCP server configuration
MCP_SERVER_URL = "http://127.0.0.1:8000/mcp"

# Global MCP client instance
mcp_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    global mcp_client
    
    # Startup
    try:
        logger.info("Initializing MCP client...")
        mcp_client = MCPClient()
        await mcp_client.connect_to_http_server(MCP_SERVER_URL)
        logger.info("MCP client initialized successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize MCP client: {e}")
        raise
    
    yield
    
    # Shutdown
    if mcp_client:
        try:
            await mcp_client.cleanup()
            logger.info("MCP client cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# FastAPI app
app = FastAPI(
    title="PartSelect API Bridge",
    description="Bridge between React frontend and MCP server",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://127.0.0.1:3000",
        "http://localhost:3001",  # In case frontend runs on different port
        "http://127.0.0.1:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    role: str = "assistant"
    content: str

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "PartSelect API Bridge",
        "mcp_server": MCP_SERVER_URL,
        "description": "Bridging React frontend with MCP server"
    }

@app.get("/health")
async def health_check():
    """Detailed health check including MCP client connectivity"""
    global mcp_client
    try:
        if mcp_client and mcp_client.client:
            # Test MCP client connection
            async with mcp_client.client:
                tools = await mcp_client.client.list_tools()
                tool_names = [tool.name for tool in tools]
            
            return {
                "status": "healthy",
                "mcp_client": "connected",
                "available_tools": tool_names,
                "mcp_url": MCP_SERVER_URL,
                "conversation_length": len(mcp_client.conversation_history)
            }
        else:
            return {
                "status": "degraded",
                "mcp_client": "not_initialized",
                "mcp_url": MCP_SERVER_URL
            }
    except Exception as e:
        logger.error(f"MCP client health check failed: {e}")
        return {
            "status": "degraded",
            "mcp_client": "disconnected", 
            "error": str(e),
            "mcp_url": MCP_SERVER_URL
        }

@app.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint that uses your MCP client's process_query method
    
    This endpoint:
    1. Receives user message from React frontend
    2. Uses your MCP client with DeepSeek AI integration
    3. Calls process_query which handles tool calling and conversation context
    4. Returns AI-generated response back to frontend
    """
    global mcp_client
    
    try:
        logger.info(f"Received chat request: {request.message}")
        
        if not mcp_client:
            raise HTTPException(status_code=503, detail="MCP client not initialized")
        
        # Use your MCP client's process_query method - this gives you:
        # - DeepSeek AI integration
        # - Automatic tool calling (get_part_detail, get_repair_guides)
        # - Conversation context/memory
        # - All the smart logic from your main.py
        response_content = await mcp_client.process_query(request.message)
        
        logger.info(f"MCP client response length: {len(response_content)}")
        logger.info(f"Response preview: {response_content[:200]}...")
        
        return ChatResponse(
            role="assistant",
            content=response_content
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return ChatResponse(
            role="assistant",
            content=f"I apologize, but I'm having trouble processing your request. Please try again.\n\nError: {str(e)}"
        )

if __name__ == "__main__":
    print("🌉 Starting PartSelect API Bridge Server...")
    print(f"🔗 Bridging React frontend with MCP server at: {MCP_SERVER_URL}")
    print("🚀 API will be available at: http://127.0.0.1:3002")
    print("📚 API docs at: http://127.0.0.1:3002/docs")
    print("Press Ctrl+C to stop")
    
    uvicorn.run(
        app,
        host="127.0.0.1", 
        port=3002,
        reload=False,  # Disable reload to avoid import issues
        log_level="info"
    )
