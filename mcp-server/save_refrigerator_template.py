from utils.scraper import setup_chrome_driver
from utils.helpers import setup_logging, random_delay, simulate_human_behavior, validate_page_load
import os

def save_refrigerator_template():
    """Save the refrigerator repair page HTML for analysis if needed"""
    logger = setup_logging()
    url = "https://www.partselect.com/Repair/Refrigerator/"
    
    driver = None
    try:
        # Setup driver
        driver = setup_chrome_driver(headless=True)
        
        # Navigate to refrigerator repair page
        logger.info(f"Navigating to refrigerator repair page: {url}")
        driver.get(url)
        random_delay(3, 6)
        
        # Simulate human behavior
        simulate_human_behavior(driver)
        
        # Validate page load
        if not validate_page_load(driver):
            logger.error("Page validation failed")
            return
        
        # Get page HTML
        page_html = driver.page_source
        
        # Create template directory if it doesn't exist
        os.makedirs('template', exist_ok=True)
        
        # Save template
        template_path = 'template/refrigerator_repair_template.html'
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(page_html)
        
        logger.info(f"Saved refrigerator template to {template_path}")
        print(f"✅ Refrigerator template saved: {len(page_html):,} characters")
        
    except Exception as e:
        logger.error(f"Error saving refrigerator template: {e}")
        print(f"❌ Error: {e}")
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    save_refrigerator_template()
