import json
import os
from datetime import datetime
from utils import scrape_partselect_product

def test_scraper():
    """Test the scraper with hardcoded part number PS3406971"""
    
    # Hardcoded part number for testing (using example from documentation)
    part_number = "PS11752778"
    
    print(f"Testing scraper with part number: {part_number}")
    print("Starting scrape...")
    
    try:
        # Run the scraper in headless mode for stability
        result = scrape_partselect_product(part_number, headless=True)
        
        # Add timestamp to result
        result['scraped_at'] = datetime.now().isoformat()
        result['test_run'] = True
        
        # Ensure data directory exists
        data_dir = "data"
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        
        # Save to JSON file (same file every time)
        json_file = os.path.join(data_dir, "scraped_parts.json")
        
        # Load existing data if file exists
        existing_data = {}
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                existing_data = {}
        
        # Add new result to existing data
        existing_data[part_number] = result
        
        # Write back to file
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Successfully scraped and saved to {json_file}")
        print(f"📋 Part name: {result.get('name', 'N/A')}")
        print(f"💰 Price: ${result.get('price', 'N/A')}")
        print(f"🔧 Difficulty: {result.get('difficulty', 'N/A')}")
        print(f"⏱️ Time estimate: {result.get('time_estimate', 'N/A')}")
        print(f"⭐ Rating: {result.get('rating', 'N/A')}/5.0")
        print(f"📦 In stock: {result.get('in_stock', 'N/A')}")
        
        if result.get('part_videos'):
            print(f"🎥 Found {len(result['part_videos'])} installation videos")
        
        if result.get('model_compatibility'):
            print(f"🔧 Compatible with {len(result['model_compatibility'])} models")
        
        return result
        
    except Exception as e:
        error_result = {
            "part_number": part_number,
            "error": str(e),
            "scraped_at": datetime.now().isoformat(),
            "test_run": True,
            "success": False
        }
        
        # Save error to JSON as well
        data_dir = "data"
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        
        json_file = os.path.join(data_dir, "scraped_parts.json")
        existing_data = {}
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except:
                existing_data = {}
        
        existing_data[f"{part_number}_error"] = error_result
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)
        
        print(f"❌ Error scraping {part_number}: {e}")
        return error_result

if __name__ == "__main__":
    test_scraper()
