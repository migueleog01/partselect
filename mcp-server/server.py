import logging
import sys
import hashlib
from datetime import datetime, timedelta

from fastmcp import FastMCP
from utils import scrape_partselect_product
from utils.rag_system import search_repair_guides, initialize_rag_system
from utils.simple_search import simple_text_search

# Set up comprehensive logging - NO STDOUT to avoid MCP protocol corruption
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server_debug.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Simple response cache for tool results
_response_cache = {}
_cache_ttl = timedelta(minutes=30)  # Cache responses for 30 minutes

def _get_cache_key(tool_name: str, **kwargs) -> str:
    """Generate cache key for tool calls"""
    key_data = f"{tool_name}:{sorted(kwargs.items())}"
    return hashlib.md5(key_data.encode()).hexdigest()

def _get_cached_response(cache_key: str):
    """Get cached response if still valid"""
    if cache_key in _response_cache:
        cached_time, response = _response_cache[cache_key]
        if datetime.now() - cached_time < _cache_ttl:
            return response
        else:
            # Remove expired cache
            del _response_cache[cache_key]
    return None

def _cache_response(cache_key: str, response):
    """Cache a response with timestamp"""
    _response_cache[cache_key] = (datetime.now(), response)

def _clean_unicode_data(data):
    """Clean Unicode characters that might cause encoding issues"""
    if isinstance(data, dict):
        return {key: _clean_unicode_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_clean_unicode_data(item) for item in data]
    elif isinstance(data, str):
        # More aggressive Unicode cleaning
        cleaned = data
        
        # Replace smart quotes and apostrophes
        cleaned = cleaned.replace('"', '"').replace('"', '"')
        cleaned = cleaned.replace(''', "'").replace(''', "'")
        
        # Replace dashes
        cleaned = cleaned.replace('—', '-').replace('–', '-')
        
        # Replace other common problematic characters
        cleaned = cleaned.replace('…', '...')
        cleaned = cleaned.replace('®', '(R)')
        cleaned = cleaned.replace('™', '(TM)')
        cleaned = cleaned.replace('©', '(C)')
        
        # Handle the specific byte 0x96 (Windows-1252 en-dash)
        cleaned = cleaned.replace('\x96', '-')
        
        # More aggressive approach: encode to latin-1 first, then decode, then re-encode to UTF-8
        try:
            # First try normal UTF-8 cleaning
            cleaned = cleaned.encode('utf-8', errors='ignore').decode('utf-8')
        except:
            try:
                # If that fails, try latin-1 approach for Windows-1252 characters
                cleaned = cleaned.encode('latin-1', errors='ignore').decode('latin-1')
                cleaned = cleaned.encode('utf-8', errors='ignore').decode('utf-8')
            except:
                # Last resort: ASCII only
                cleaned = str(data).encode('ascii', errors='ignore').decode('ascii')
        
        return cleaned
    else:
        return data

mcp = FastMCP("PartSelect MCP Server")

@mcp.tool()
def get_part_detail(part_select_number: str) -> dict:
    """
    Get comprehensive part details from PartSelect.com
    
    Args:
        part_select_number: The PartSelect part number (e.g., 'PS11752778')
        
    Returns:
        Dictionary containing detailed part information including:
        - Basic info (name, price, part numbers)
        - Installation details (difficulty, time estimate)
        - Customer reviews (rating, review count)
        - Compatibility (compatible models)
        - Troubleshooting (symptoms, replaces parts)
        - Additional products and installation videos
    """
    try:
        logger.info(f"get_part_detail called with part_select_number='{part_select_number}'")
        
        # Use the scraping function to get comprehensive part data
        part_detail = scrape_partselect_product(part_select_number, headless=True)
        
        # Clean any problematic Unicode characters that might cause encoding issues
        part_detail = _clean_unicode_data(part_detail)
        
        logger.info(f"Successfully retrieved part details for {part_select_number}")



        """
        product_info = {
        'url': url,
        'name': '',
        'price': None,
        'part_number': '',
        'manufacturer_part': '',
        'replaces_parts': [],
        'difficulty': '',
        'time_estimate': '',
        'rating': None,
        'review_count': None,
        'product_type': '',
        'in_stock': False,
        'description': '',
        'you_may_need': [],
        'symptoms': [],
        'part_videos': [],
        'model_compatibility': []
    }
        
        """
        #if its not a refrigereator or dishwasher then return saying sorry i can only help with refrigerator or dishwasher

        if part_detail.get('product_type') != 'refrigerator' and part_detail.get('product_type') != 'dishwasher':
            return {
                "error": "Sorry, I can only help with refrigerator or dishwasher. Please ask about refrigerator or dishwasher issues.",
                "part_number": part_select_number,
                "product_type": part_detail.get('product_type')
            }


        return part_detail
    except UnicodeDecodeError as e:
        logger.error(f"Unicode encoding error for {part_select_number}: {e}")
        return {
            "error": f"Unicode encoding issue with part {part_select_number}. Please try again or contact support.",
            "part_number": part_select_number,
            "error_type": "encoding"
        }
    except Exception as e:
        logger.error(f"General error for {part_select_number}: {e}")
        return {
            "error": f"Failed to scrape part {part_select_number}: {str(e)}",
            "part_number": part_select_number
        }

@mcp.tool()
def get_repair_guides(appliance_type: str = "Dishwasher") -> dict:
    """
    Get repair guides and troubleshooting information using RAG (Retrieval-Augmented Generation)
    
    Args:
        appliance_type: Type of appliance to get repair guides for (e.g., 'Dishwasher', 'Refrigerator', 'Washer', 'Dryer')
        
    Returns:
        Dictionary containing repair guides including:
        - Common symptoms and issues for the appliance type
        - Detailed troubleshooting instructions
        - Related parts information
        - Retrieved from local JSON data using semantic search
    """
    logger.info(f"get_repair_guides called with appliance_type='{appliance_type}'")
    
    # Check cache first
    cache_key = _get_cache_key("get_repair_guides", appliance_type=appliance_type)
    cached_result = _get_cached_response(cache_key)
    if cached_result:
        logger.info(f"Using cached response for {appliance_type}")
        logger.info(f"CACHE HIT: get_repair_guides for {appliance_type}")
        return cached_result
    
    logger.info(f"=== TOOL CALL START ===")
    logger.info(f"Tool: get_repair_guides")
    logger.info(f"Input: appliance_type='{appliance_type}'")
    logger.info(f"Timestamp: {datetime.now()}")
    logger.info(f"========================")
    
    try:
        # Create a comprehensive query for the appliance type
        # Use multiple targeted queries to ensure we get all symptom types
        queries = [
            f"common {appliance_type} symptoms problems",
            f"{appliance_type} repair issues troubleshooting",
            f"{appliance_type} not working broken symptoms"
        ]
        logger.info(f"Generated queries: {queries}")
        
        # Try RAG first with multiple queries to capture all symptoms
        logger.info(f"Trying RAG search with multiple queries...")
        all_results = []
        seen_symptoms = set()
        
        for query in queries:
            logger.info(f"Searching with query: '{query}'")
            rag_results = search_repair_guides(query, appliance_type=appliance_type, top_k=15)
            
            if "error" not in rag_results and "results" in rag_results:
                for result in rag_results["results"]:
                    symptom_key = f"{result['symptom']}-{result['issue_title']}"
                    if symptom_key not in seen_symptoms:
                        all_results.append(result)
                        seen_symptoms.add(symptom_key)
        
        logger.info(f"Combined RAG search found {len(all_results)} unique results")
        
        # Create combined results object
        rag_results = {
            "results": all_results,
            "query": " | ".join(queries),
            "method": "RAG (Multi-query search)"
        }
        
        logger.info(f"RAG search returned: {type(rag_results)}")
        
        if "error" in rag_results:
            logger.warning(f"RAG failed: {rag_results['error']}")
            logger.info(f"Falling back to simple text search...")
            rag_results = simple_text_search(query=queries[0], appliance_type=appliance_type, max_results=12)
            logger.info(f"Simple search returned: {type(rag_results)}")
            
            if "error" in rag_results:
                logger.error(f"Simple search also failed: {rag_results['error']}")
                return rag_results
        
        logger.info(f"Found {rag_results.get('total_found', 0)} results")
        
        # Process and structure the results
        repair_sections = []
        seen_issues = set()
        
        for i, result in enumerate(rag_results["results"]):
            logger.debug(f"Processing result {i+1}: {result.get('symptom', 'N/A')} - {result.get('issue_title', 'N/A')}")
            
            # Avoid duplicate issues
            issue_key = f"{result['symptom']}_{result['issue_title']}".lower()
            if issue_key in seen_issues:
                logger.debug(f"Skipping duplicate issue: {issue_key}")
                continue
            seen_issues.add(issue_key)
            
            repair_sections.append({
                "symptom": result["symptom"],
                "issue_title": result["issue_title"],
                "description": result["text"].split("Description: ")[1].split("\n")[0] if "Description: " in result["text"] else "",
                "instructions": result["instructions"],
                "related_parts": result["related_parts"],
                "confidence_score": round(result["score"], 3),
                "source": result["source_file"]
            })
        
        # Group by symptoms for better organization, but also detect component-specific queries
        symptoms = {}
        component_sections = {}
        
        for section in repair_sections:
            symptom = section["symptom"] or "General"
            if symptom not in symptoms:
                symptoms[symptom] = []
            symptoms[symptom].append(section)
            
            # Also group by component/issue title for component-specific queries
            component = section["issue_title"]
            if component not in component_sections:
                component_sections[component] = []
            component_sections[component].append(section)
        
        # If this looks like a component-specific query, prioritize component grouping
        query_lower = " ".join(queries).lower()
        component_keywords = ["motor", "fan", "valve", "pump", "control", "switch", "sensor", "heater", "thermostat"]
        is_component_query = any(keyword in query_lower for keyword in component_keywords)
        
        if is_component_query and len(component_sections) < len(symptoms):
            logger.info(f"Detected component-specific query, using component grouping")
            # Use component grouping for better organization
            symptoms = {f"Component: {comp}": sections for comp, sections in component_sections.items()}
        
        logger.info(f"Successfully processed {len(repair_sections)} sections into {len(symptoms)} symptom groups")
        
        result = {
            "appliance_type": appliance_type,
            "method": "RAG (Retrieval-Augmented Generation)" if "method" not in rag_results else rag_results["method"],
            "total_issues_found": len(repair_sections),
            "symptoms": symptoms,
            "note": "Data retrieved from local repair database using semantic search"
        }
        
        logger.info(f"=== TOOL RESPONSE ===")
        logger.info(f"Tool: get_repair_guides")
        logger.info(f"Success: True")
        logger.info(f"Method: {result['method']}")
        logger.info(f"Issues found: {len(repair_sections)}")
        logger.info(f"Symptom groups: {len(symptoms)}")
        logger.info(f"Response size: {len(str(result))} characters")
        logger.info(f"=====================")
        
        # Cache the successful result
        _cache_response(cache_key, result)
        logger.info(f"Cached response for {appliance_type}")
        
        return result
        
    except Exception as e:
        error_msg = f"Failed to get repair guides for {appliance_type}: {str(e)}"
        logger.error(f"Exception occurred: {error_msg}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        error_result = {
            "error": error_msg,
            "appliance_type": appliance_type
        }
        
        logger.error(f"=== TOOL ERROR ===")
        logger.error(f"Tool: get_repair_guides")
        logger.error(f"Error: {error_msg}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        logger.error(f"==================")
        
        return error_result

# CLI mode - FastMCP CLI handles the server startup
# Use: fastmcp run server.py:mcp --transport http --port 8000

# if __name__ == "__main__":
#     # Initialize RAG system on startup with detailed logging
#     logger.info("=" * 50)
#     logger.info("INITIALIZING RAG SYSTEM ON SERVER STARTUP")
#     logger.info("=" * 50)
#     
#     rag_initialized = False
#     
#     # Temporarily disable RAG initialization to avoid asyncio conflicts
#     # The RAG system will initialize on first use instead
#     logger.info("Skipping RAG initialization at startup to avoid asyncio conflicts")
#     logger.info("RAG system will initialize on first tool call")
#     rag_initialized = False
#     
#     logger.info("=" * 50)
#     if rag_initialized:
#         logger.info("Starting MCP server with RAG system enabled...")
#     else:
#         logger.info("Starting MCP server with simple search fallback...")
#     logger.info("=" * 50)
#     
#     # Always start the MCP server regardless of RAG status
#     print("🚀 MCP Server running on HTTP port 8000")
#     print("📡 Available endpoints:")
#     print("   - get_part_detail")
#     print("   - get_repair_guides")
#     print("🌐 Access at: http://localhost:8000/mcp")
#     print("Press Ctrl+C to stop")
#     mcp.run(transport="http", port=8000)