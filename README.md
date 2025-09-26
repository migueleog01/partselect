# PartSelect MCP System

A complete Model Context Protocol (MCP) system that integrates PartSelect.com scraping with DeepSeek AI for intelligent appliance repair assistance.

## 🏗️ Architecture

```
React Frontend (Port 3000)
    ↓
FastAPI Bridge (Port 3002)  
    ↓
MCP Client (DeepSeek AI)
    ↓
MCP Server (Port 8000)
    ↓
PartSelect Scraper + RAG System
```

## 🚀 Features

- **Smart Web Scraping**: Automated PartSelect.com data extraction with anti-detection
- **RAG System**: Retrieval-Augmented Generation using FAISS and SentenceTransformers
- **AI Integration**: DeepSeek AI with conversation memory and tool calling
- **Modern Frontend**: React-based chat interface
- **HTTP Transport**: FastMCP-powered HTTP communication
- **Appliance Focus**: Specialized for Refrigerator and Dishwasher repairs only

## 📁 Project Structure

```
partselectMCP/
├── mcp-server/           # MCP Server with scraping and RAG
│   ├── server.py         # Main MCP server
│   ├── utils/            # Scraping and RAG utilities
│   ├── data/             # JSON repair guide data
│   └── requirements.txt
├── mcp-client/           # MCP Client with DeepSeek AI
│   ├── main.py           # Client with conversation memory
│   └── requirements.txt
├── api-bridge/           # FastAPI bridge for React
│   ├── main.py           # HTTP API server
│   └── requirements.txt
├── case-study-frontend/  # React chat interface
│   ├── src/
│   ├── public/
│   └── package.json
└── README.md
```

## 🛠️ Setup & Installation

### Prerequisites

- Python 3.8+
- Node.js 16+
- Chrome browser (for web scraping)

### 1. MCP Server Setup

```bash
cd mcp-server
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. MCP Client Setup

```bash
cd mcp-client
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Add your DeepSeek API key
echo "DEEPSEEK_API_KEY=your_key_here" > .env
```

### 3. API Bridge Setup

```bash
cd api-bridge
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 4. React Frontend Setup

```bash
cd case-study-frontend
npm install
```

## 🚀 Running the System

Start all components in separate terminals:

### Terminal 1 - MCP Server
```bash
cd mcp-server
fastmcp run server.py:mcp --transport http --port 8000
```

### Terminal 2 - API Bridge
```bash
cd api-bridge
venv\Scripts\activate
python main.py
```

### Terminal 3 - React Frontend
```bash
cd case-study-frontend
npm start
```

## 🔧 Available Tools

### `get_part_detail`
Scrapes detailed part information from PartSelect.com including:
- Part name, price, and availability
- Installation videos and manuals
- Compatible models
- Customer reviews

### `get_repair_guides`
Uses RAG system to provide repair guidance including:
- Common symptoms and troubleshooting
- Step-by-step repair instructions
- Video tutorials
- Component-specific guidance

## 🤖 AI Capabilities

- **Conversation Memory**: Maintains context across chat sessions
- **Tool Calling**: Automatically invokes scraping tools when needed
- **Smart Responses**: DeepSeek AI provides intelligent, complete answers
- **Appliance Specialization**: Focused on refrigerator and dishwasher repairs

## 📊 RAG System

The system uses:
- **FAISS**: For efficient similarity search
- **SentenceTransformers**: For text embeddings
- **Local JSON Data**: Comprehensive repair guides
- **Intelligent Caching**: Persistent index storage
- **Multi-Query Search**: Enhanced recall for diverse queries

## 🔒 Security & Policies

- **Strict Appliance Policy**: Only handles refrigerator/dishwasher queries
- **Anti-Detection**: Rotating user agents and request delays
- **Chrome Driver Management**: Automatic driver updates
- **Error Handling**: Graceful fallbacks and logging

## 📝 Example Queries

- "What are common refrigerator problems?"
- "Get part details for PS11752778"
- "How do I fix a noisy dishwasher?"
- "Troubleshoot condenser fan motor issues"

## 🏷️ API Endpoints

### FastAPI Bridge (Port 3002)

- `GET /` - Health check
- `GET /health` - Detailed system status
- `POST /chat` - Main chat endpoint
- `GET /docs` - API documentation

## 🛡️ Error Handling

- **Unicode Safety**: Handles special characters in scraped data
- **Connection Resilience**: Automatic retries and fallbacks
- **Logging**: Comprehensive debug logs for troubleshooting
- **Graceful Degradation**: Continues operation if components fail

## 📈 Performance

- **Caching**: Tool response and RAG index caching
- **Parallel Processing**: Concurrent tool calls and searches
- **Optimized Scraping**: Efficient Chrome driver management
- **Memory Management**: Context length limits and cleanup

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request



## 🔗 Links

- [PartSelect.com](https://www.partselect.com) - Source of repair data
- [FastMCP Documentation](https://github.com/jlowin/fastmcp) - MCP framework
- [DeepSeek API](https://platform.deepseek.com) - AI model provider

---


