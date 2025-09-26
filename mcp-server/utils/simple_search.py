"""
Simple fallback search system for repair data without RAG dependencies.
Uses basic text matching when FAISS/SentenceTransformers aren't available.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import re
import logging

logger = logging.getLogger(__name__)

def simple_text_search(data_dir: str = "data", query: str = "", appliance_type: str = None, max_results: int = 8) -> Dict[str, Any]:
    """
    Simple text-based search through JSON repair data
    """
    logger.info(f"Starting search for '{query}' in appliance_type='{appliance_type}'")
    
    data_path = Path(data_dir)
    if not data_path.exists():
        error_msg = f"Data directory not found: {data_path.absolute()}"
        logger.error(error_msg)
        return {"error": error_msg}
    
    results = []
    query_words = query.lower().split()
    
    logger.info(f"Searching in {data_path.absolute()}")
    
    # Find all JSON files
    json_files = list(data_path.rglob("*.json"))
    repair_files = [f for f in json_files if f.name != "scraped_parts.json"]
    
    logger.info(f"Found {len(repair_files)} repair files to search")
    
    for json_file in repair_files:
        # Skip if appliance type filter doesn't match
        if appliance_type:
            file_path_str = str(json_file).lower()
            if appliance_type.lower() not in file_path_str:
                continue
        
        logger.debug(f"Processing {json_file.name}")
        
        try:
            data = json.loads(json_file.read_text(encoding='utf-8'))
            
            # Extract appliance type from path
            file_appliance_type = "General"
            if "refrigerator" in str(json_file).lower():
                file_appliance_type = "Refrigerator"
            elif "dishwasher" in str(json_file).lower():
                file_appliance_type = "Dishwasher"
            elif "washer" in str(json_file).lower():
                file_appliance_type = "Washer"
            elif "dryer" in str(json_file).lower():
                file_appliance_type = "Dryer"
            
            symptom_title = data.get("symptom_title", "")
            
            # Process repair sections
            for section in data.get("repair_sections", []):
                title = section.get("title", "")
                description = section.get("description", "")
                instructions = section.get("instructions", [])
                
                # Create searchable text
                searchable_text = f"{symptom_title} {title} {description} {' '.join(instructions)}".lower()
                
                # Simple text matching - count query word matches
                matches = sum(1 for word in query_words if word in searchable_text)
                
                if matches > 0:  # At least one query word matches
                    score = matches / len(query_words)  # Simple relevance score
                    
                    results.append({
                        "score": score,
                        "appliance_type": file_appliance_type,
                        "symptom": symptom_title,
                        "issue_title": title,
                        "text": f"Symptom: {symptom_title}\nIssue: {title}\nDescription: {description}",
                        "instructions": instructions,
                        "related_parts": section.get("related_parts", []),
                        "source_file": json_file.name,
                        "url": data.get("url", "")
                    })
        
        except Exception as e:
            logger.error(f"Error processing {json_file.name}: {e}")
            continue
    
    # Sort by score (descending) and limit results
    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:max_results]
    
    logger.info(f"Found {len(results)} results")
    if results:
        logger.info(f"Top result: {results[0]['symptom']} - {results[0]['issue_title']} (score: {results[0]['score']:.2f})")
    
    return {
        "query": query,
        "appliance_type": appliance_type,
        "results": results,
        "total_found": len(results),
        "method": "Simple text search (fallback)"
    }
