from utils import scrape_symptom_detail, setup_logging
import json
import os

def scrape_refrigerator_noisy():
    """Specifically scrape the refrigerator noisy symptom that failed"""
    logger = setup_logging()
    
    # Target URL and info
    symptom_url = "https://www.partselect.com/Repair/Refrigerator/Noisy/"
    symptom_title = "Noisy"
    
    print(f"🧊 Scraping Refrigerator Noisy Symptom")
    print("=" * 50)
    print(f"🎯 Symptom: {symptom_title}")
    print(f"🌐 URL: {symptom_url}")
    
    try:
        # Create directory structure
        os.makedirs('data/refrigerator/refrigerator_symptoms', exist_ok=True)
        
        # Scrape detailed symptom data
        print(f"🔄 Scraping detailed data...")
        symptom_data = scrape_symptom_detail(symptom_url, symptom_title, headless=True)
        
        # Check what we got
        print(f"\n📊 RESULTS:")
        print(f"   Symptom Title: {symptom_data.get('symptom_title', 'None')}")
        print(f"   URL: {symptom_data.get('url', 'None')}")
        print(f"   Repair Sections: {len(symptom_data.get('repair_sections', []))}")
        print(f"   Repair Stats: {symptom_data.get('repair_stats', {})}")
        
        repair_sections = symptom_data.get('repair_sections', [])
        if repair_sections:
            print(f"\n🔧 REPAIR SECTIONS FOUND:")
            for i, section in enumerate(repair_sections, 1):
                title = section.get('title', 'No title')
                description = section.get('description', 'No description')
                instructions_count = len(section.get('instructions', []))
                parts_count = len(section.get('related_parts', []))
                
                print(f"   {i}. {title}")
                print(f"      📝 Description: {description[:80]}..." if len(description) > 80 else f"      📝 Description: {description}")
                print(f"      📋 Instructions: {instructions_count} steps")
                print(f"      🔧 Related Parts: {parts_count} parts")
                
                # Show first instruction
                instructions = section.get('instructions', [])
                if instructions:
                    print(f"      📖 First step: {instructions[0][:60]}..." if len(instructions[0]) > 60 else f"      📖 First step: {instructions[0]}")
        else:
            print(f"\n❌ NO REPAIR SECTIONS FOUND")
            print(f"   This might indicate:")
            print(f"   - Different page structure than expected")
            print(f"   - Page didn't load properly")
            print(f"   - Different HTML format for refrigerator vs dishwasher")
        
        # Save to file regardless
        filename = "refrigerator_noisy_detail.json"
        output_file = f'data/refrigerator/refrigerator_symptoms/{filename}'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(symptom_data, f, indent=2, ensure_ascii=False)
        
        file_size = os.path.getsize(output_file)
        print(f"\n💾 SAVED:")
        print(f"   File: {output_file}")
        print(f"   Size: {file_size:,} bytes")
        
        # If no sections found, let's also save the raw HTML template for analysis
        if not repair_sections:
            print(f"\n🔍 SAVING HTML TEMPLATE FOR ANALYSIS...")
            from utils.scraper import setup_chrome_driver
            from utils.helpers import random_delay, simulate_human_behavior, validate_page_load
            
            driver = None
            try:
                driver = setup_chrome_driver(headless=True)
                driver.get(symptom_url)
                random_delay(3, 6)
                simulate_human_behavior(driver)
                
                if validate_page_load(driver):
                    page_html = driver.page_source
                    template_path = 'template/refrigerator_noisy_template.html'
                    os.makedirs('template', exist_ok=True)
                    
                    with open(template_path, 'w', encoding='utf-8') as f:
                        f.write(page_html)
                    
                    print(f"   📄 HTML template saved: {template_path}")
                    print(f"   📊 Template size: {len(page_html):,} characters")
                else:
                    print(f"   ❌ Page validation failed - couldn't save template")
                    
            except Exception as e:
                print(f"   ❌ Error saving template: {e}")
            finally:
                if driver:
                    driver.quit()
        
        return symptom_data
        
    except Exception as e:
        logger.error(f"Error scraping refrigerator noisy: {e}")
        print(f"❌ ERROR: {e}")
        return None

if __name__ == "__main__":
    scrape_refrigerator_noisy()
