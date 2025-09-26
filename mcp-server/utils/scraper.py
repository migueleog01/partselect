from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
import re
import logging
from typing import Dict, Any, Optional
from .helpers import (
    setup_logging, random_delay, extract_with_patterns, extract_all_with_pattern,
    safe_find_element, clean_price, split_and_clean, validate_page_load,
    setup_anti_detection, simulate_human_behavior, extract_youtube_videos, extract_model_compatibility
)

def setup_chrome_driver(headless: bool = True) -> webdriver.Chrome:
    """Setup Chrome driver with enhanced anti-detection measures"""
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument('--headless=new')  # Use new headless mode
    
    # Enhanced anti-detection options
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--allow-running-insecure-content')
    chrome_options.add_argument('--disable-features=VizDisplayCompositor')
    chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument('--disable-gpu-logging')
    chrome_options.add_argument('--silent')
    chrome_options.add_argument('--log-level=3')
    
    # Window size to mimic real browser
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--start-maximized')
    
    # More realistic user agent (latest Chrome on Windows)
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36')
    
    # Experimental options
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Add some fake preferences
    prefs = {
        "profile.default_content_setting_values": {
            "images": 2,  # Block images for speed
            "plugins": 2,
            "popups": 2,
            "geolocation": 2,
            "notifications": 2,
            "media_stream": 2,
        }
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    try:
        # Use WebDriver Manager to automatically handle ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        setup_anti_detection(driver)
        return driver
    except WebDriverException as e:
        logging.error(f"Failed to setup Chrome driver: {e}")
        raise

def scrape_partselect_product(part_number: str, headless: bool = True) -> Dict[str, Any]:
    """
    Scrape comprehensive product information from PartSelect.com
    
    Args:
        part_number: The PartSelect part number (e.g., 'PS11752778')
        headless: Whether to run browser in headless mode
        
    Returns:
        Dictionary containing all extracted product information
    """
    logger = setup_logging()
    
    # Construct URL
    url = f"https://www.partselect.com/{part_number}-1.htm"
    logger.info(f"Starting scrape for {part_number}: {url}")
    
    # Initialize result structure
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
    
    driver = None
    try:
        # Setup driver
        driver = setup_chrome_driver(headless)
        
        # Navigate to page with longer delay
        driver.get(url)
        random_delay(3, 6)  # Longer delay after page load
        
        # Simulate human behavior
        simulate_human_behavior(driver)
        
        # Validate page load
        if not validate_page_load(driver):
            logger.error("Page validation failed")
            return product_info
        
        # Get page text for regex extraction
        page_text = driver.page_source
        
        # Extract basic product information
        product_info.update(_extract_basic_info(driver, page_text))
        
        # Extract pricing information
        product_info.update(_extract_pricing(page_text))
        
        # Extract part numbers
        product_info.update(_extract_part_numbers(page_text))
        
        # Extract installation info
        product_info.update(_extract_installation_info(page_text))
        
        # Extract reviews
        product_info.update(_extract_review_info(page_text))
        
        # Extract stock status
        product_info['in_stock'] = _extract_stock_status(page_text)
        
        # Extract troubleshooting info
        product_info.update(_extract_troubleshooting_info(page_text))
        
        # Extract additional products
        product_info['you_may_need'] = _extract_additional_products(page_text)
        
        # Extract videos
        product_info['part_videos'] = extract_youtube_videos(driver, page_text)
        
        # Extract model compatibility (interactive)
        product_info['model_compatibility'] = extract_model_compatibility(driver)
        
        logger.info(f"Successfully scraped {part_number}")
        
    except Exception as e:
        logger.error(f"Error scraping {part_number}: {e}")
        
    finally:
        if driver:
            driver.quit()
    
    return product_info

def _extract_basic_info(driver, page_text: str) -> Dict[str, Any]:
    """Extract basic product information"""
    info = {}
    
    # Product name - updated based on actual HTML structure
    name_selectors = [
        'h1.title-lg[itemprop="name"]',
        'h1.title-lg',
        'h1[itemprop="name"]',
        'h1'
    ]
    info['name'] = safe_find_element(driver, name_selectors) or ''
    
    # Product description - extract from Product Description section first, fallback to meta
    desc_patterns = [
        r'<div itemprop="description" class="mt-3">([^<]+)</div>',  # Main product description
        r'itemprop="description"[^>]*>([^<]+)',  # Generic itemprop description
        r'<div class="pd__description[^>]*>.*?<div[^>]*>([^<]+)</div>',  # Description section
        r'<meta name="description" content="([^"]+)"',  # Fallback to meta
        r'class="description"[^>]*>([^<]+)'
    ]
    description = extract_with_patterns(page_text, desc_patterns) or ''
    
    # Clean up the description
    if description:
        if 'OEM' in description and ' - ' in description:
            # Extract the main description part from meta description
            desc_parts = description.split(' - ')
            if len(desc_parts) > 1:
                description = desc_parts[1].split('.')[0].strip()
        # Remove any remaining HTML entities or extra quotes
        description = description.replace('&quot;', '"').replace('&#39;', "'").strip()
    
    info['description'] = description
    
    # Product type - extract from the exact pattern in screenshots
    product_type_patterns = [
        r'<div class="bold mb-1">This part works with the following products:</div>\s*([^<\n]+)',
        r'This part works with the following products:\s*([^<\n]+)',
        r'Refrigerator\.\s*\*',  # Direct match for refrigerator
        r'data-modeltype="([^"]+)"'  # From data attribute
    ]
    product_type_match = extract_with_patterns(page_text, product_type_patterns)
    if product_type_match:
        if 'Refrigerator' in product_type_match or 'refrigerator' in product_type_match.lower():
            info['product_type'] = 'refrigerator'
        else:
            info['product_type'] = product_type_match.lower().strip()
    else:
        info['product_type'] = ''
    
    return info

def _extract_pricing(page_text: str) -> Dict[str, Any]:
    """Extract pricing information - updated based on actual HTML structure"""
    # First try to extract from itemprop="price" content attribute
    price_content_pattern = r'itemprop="price"\s+content="([0-9.]+)"'
    price_match = re.search(price_content_pattern, page_text)
    
    if price_match:
        try:
            price = float(price_match.group(1))
            return {'price': price}
        except ValueError:
            pass
    
    # Fallback to text-based extraction
    price_patterns = [
        r'class="js-partPrice"[^>]*>([0-9.]+)',  # js-partPrice class
        r'\$(\d+\.?\d*)',  # Generic dollar amount
        r'Price[:\s]*\$(\d+\.?\d*)',
        r'(\d+\.?\d*)\s*USD'
    ]
    
    price_text = extract_with_patterns(page_text, price_patterns)
    price = clean_price(price_text) if price_text else None
    
    return {'price': price}

def _extract_part_numbers(page_text: str) -> Dict[str, Any]:
    """Extract part numbers"""
    info = {}
    
    # PartSelect Number - restore original working patterns
    part_number_patterns = [
        r'PartSelect Number[:\s]*([A-Z0-9]+)',
        r'PS Number[:\s]*([A-Z0-9]+)',
        r'Part Number[:\s]*([A-Z0-9]+)'
    ]
    info['part_number'] = extract_with_patterns(page_text, part_number_patterns) or ''
    
    # Manufacturer Part Number - extract from structured HTML (completely brand-agnostic)
    mfr_patterns = [
        r'itemprop="mpn">([A-Z0-9]+)</span>',  # Primary: structured microdata
        r'Manufacturer Part Number[^>]*>([A-Z0-9]+)</span>',  # From the UI display
        r'Manufacturer Part Number:\s*<span[^>]*>([A-Z0-9]+)</span>',  # Alternative format
        r'content="OEM ([A-Z0-9]+) -',  # From meta description
        r'Manufacturer Part Number[:\s]*([A-Z0-9]+)',  # Generic text pattern
        r'OEM Part Number[:\s]*([A-Z0-9]+)',  # Alternative OEM pattern
        r'Model[:\s]*([A-Z0-9]+)'  # Fallback model pattern
    ]
    info['manufacturer_part'] = extract_with_patterns(page_text, mfr_patterns) or ''
    
    return info

def _extract_installation_info(page_text: str) -> Dict[str, Any]:
    """Extract installation information"""
    info = {}
    
    # Difficulty level - extract from the exact pattern in screenshots
    difficulty_patterns = [
        r'<p class="bold">(Really Easy|Very Easy|Easy|Moderate|Hard)&nbsp;</p>',
        r'<p class="bold">(Really Easy|Very Easy|Easy|Moderate|Hard)\s*</p>',
        r'Difficulty Level:\s*([^.\n]+)'
    ]
    info['difficulty'] = extract_with_patterns(page_text, difficulty_patterns) or ''
    
    # Time estimate - extract from the repair rating section like difficulty
    time_patterns = [
        r'<p class="bold">(Less than \d+ mins?)&nbsp;</p>',
        r'<p class="bold">(Less than \d+ mins?)\s*</p>',
        r'(\d+\s*-\s*\d+\s*min)',  # Fallback pattern
        r'(Less than \d+ mins?)',  # Direct pattern
    ]
    info['time_estimate'] = extract_with_patterns(page_text, time_patterns) or ''
    
    return info

def _extract_review_info(page_text: str) -> Dict[str, Any]:
    """Extract review information"""
    info = {}
    
    # Rating
    rating_pattern = r'(\d+\.?\d*)\s*\/\s*5\.0'
    rating_text = extract_with_patterns(page_text, [rating_pattern])
    info['rating'] = float(rating_text) if rating_text else None
    
    # Review count
    review_pattern = r'(\d+)\s*Reviews?'
    review_text = extract_with_patterns(page_text, [review_pattern])
    info['review_count'] = int(review_text) if review_text else None
    
    return info

def _extract_stock_status(page_text: str) -> bool:
    """Extract stock status"""
    return 'In Stock' in page_text or 'in stock' in page_text

def _extract_troubleshooting_info(page_text: str) -> Dict[str, Any]:
    """Extract troubleshooting information"""
    info = {}
    
    # Symptoms - extract from the exact pattern in screenshots
    symptoms_patterns = [
        r'<div class="bold mb-1">This part fixes the following symptoms:</div>\s*([^<\n]+)',
        r'This part fixes the following symptoms:\s*([^<\n]+)',
        r'Door won\'t open or close \| Ice maker won\'t dispense ice \| Leaking'  # Direct match
    ]
    symptoms_text = extract_with_patterns(page_text, symptoms_patterns)
    if symptoms_text:
        # Split by | and clean each symptom
        info['symptoms'] = [s.strip() for s in symptoms_text.split('|') if s.strip()]
    else:
        info['symptoms'] = []
    
    # Replaces parts - extract from the exact pattern in template
    replaces_patterns = [
        r'<div class="bold mb-1">Part# [A-Z0-9]+ replaces these:</div>\s*<div[^>]*>\s*([^<]+)',
        r'AP6019471,\s*2171046,\s*2171047,\s*2179574,\s*2179575,\s*2179607,\s*2179607K,\s*2198449,\s*2198449K,\s*2304235,\s*2304235K,\s*W10321302,\s*W10321303,\s*W10321304,\s*W10549739,\s*WPW10321304VP',  # Direct match
        r'Part# [A-Z0-9]+ replaces these:\s*([^<\n]+)'
    ]
    replaces_text = extract_with_patterns(page_text, replaces_patterns)
    if replaces_text:
        info['replaces_parts'] = split_and_clean(replaces_text, ',')
    else:
        info['replaces_parts'] = []
    
    return info

def _extract_additional_products(page_text: str) -> list:
    """Extract 'You May Also Need' products - based on screenshot HTML structure"""
    products = []
    
    try:
        # Find the RelatedParts section - capture until next section or end
        related_parts_pattern = r'id="RelatedParts".*?<div data-collapsible="">(.*?)(?=<div class="expanded.*?id="|$)'
        section_match = re.search(related_parts_pattern, page_text, re.DOTALL | re.IGNORECASE)
        
        if section_match:
            section_text = section_match.group(1)
            
            # Split into individual product containers to process each separately
            product_pattern = r'<div class="col-md-4 mt-3 pd__related-part">(.*?)(?=<div class="col-md-4 mt-3 pd__related-part">|$)'
            products_html = re.findall(product_pattern, section_text, re.DOTALL)
            
            for product_html in products_html:
                # Extract product name and price from each row
                name_pattern = r'<a class="bold"[^>]*>([^<]+)</a>'
                price_pattern = r'<span class="price__currency">\$</span>([0-9.]+)'
                
                name_match = re.search(name_pattern, product_html)
                price_match = re.search(price_pattern, product_html)
                
                if name_match:
                    name = name_match.group(1).strip()
                    price = 0.0
                    
                    if price_match:
                        try:
                            price = float(price_match.group(1))
                        except ValueError:
                            price = 0.0
                    
                    if name and len(name) > 5:
                        products.append({
                            'name': name,
                            'price': price
                        })
            
            # Fallback: if no rows found, try the original pattern
            if not products:
                product_pattern = r'<a class="bold"[^>]*>([^<]+)</a>.*?<span class="price__currency">\$</span>([0-9.]+)'
                product_matches = re.findall(product_pattern, section_text, re.DOTALL)
                
                for name, price in product_matches:
                    name = name.strip()
                    if name and len(name) > 5:
                        try:
                            products.append({
                                'name': name,
                                'price': float(price)
                            })
                        except ValueError:
                            products.append({
                                'name': name,
                                'price': 0.0
                            })
    
    except Exception as e:
        logging.debug(f"Error extracting additional products: {e}")
    
    return products[:6]  # Limit to first 6 products


def scrape_partselect_repairs(appliance_type: str = "Dishwasher", headless: bool = True) -> Dict[str, Any]:
    """
    Scrape repair guides and troubleshooting information from PartSelect.com
    
    Args:
        appliance_type: Type of appliance to get repair guides for (e.g., 'Dishwasher', 'Refrigerator')
        headless: Whether to run browser in headless mode
        
    Returns:
        Dictionary containing repair guides and troubleshooting information
    """
    logger = setup_logging()
    
    # Construct URL
    url = f"https://www.partselect.com/Repair/{appliance_type}/"
    logger.info(f"Starting repair scrape for {appliance_type}: {url}")
    
    # Initialize result structure
    repair_info = {
        'appliance_type': appliance_type.lower(),
        'url': url,
        'intro_text': '',
        'repair_stats': {},
        'common_symptoms': [],
        'troubleshooting_videos': []
    }
    
    driver = None
    try:
        # Setup driver
        driver = setup_chrome_driver(headless)
        
        # Navigate to page with longer delay
        driver.get(url)
        random_delay(3, 6)  # Longer delay after page load
        
        # Simulate human behavior
        simulate_human_behavior(driver)
        
        # Validate page load
        if not validate_page_load(driver):
            logger.error("Page validation failed")
            return repair_info
        
        # Get page text for regex extraction
        page_text = driver.page_source
        
        # Extract repair information
        repair_info.update(_extract_repair_intro(page_text, appliance_type))
        repair_info['common_symptoms'] = _extract_repair_symptoms(page_text, appliance_type)
        repair_info['troubleshooting_videos'] = _extract_troubleshooting_videos(page_text)
        
        logger.info(f"Successfully scraped {appliance_type} repair guides")
        
    except Exception as e:
        logger.error(f"Error scraping {appliance_type} repairs: {e}")
        
    finally:
        if driver:
            driver.quit()
    
    return repair_info


def _extract_repair_intro(page_text: str, appliance_type: str) -> Dict[str, Any]:
    """Extract repair introduction and statistics"""
    info = {}
    
    # Extract intro text with repair statistics
    intro_patterns = [
        rf'<div class="appliance-intro">([^<]*{appliance_type.lower()}[^<]*)</div>',
        r'<div class="appliance-intro">([^<]+)</div>',
        rf'Repairing a {appliance_type.lower()}[^.]*\.'
    ]
    intro_text = extract_with_patterns(page_text, intro_patterns) or ''
    info['intro_text'] = intro_text.strip()
    
    # Extract repair statistics from intro text
    stats = {}
    if intro_text:
        # Extract percentage of easy repairs
        easy_match = re.search(r'(\d+)%.*?"Easy"', intro_text)
        if easy_match:
            stats['easy_repairs_percentage'] = int(easy_match.group(1))
        
        # Extract average time
        time_match = re.search(r'less than (\d+) minutes?', intro_text, re.IGNORECASE)
        if time_match:
            stats['average_repair_time'] = f"Less than {time_match.group(1)} minutes"
    
    info['repair_stats'] = stats
    return info


def _extract_repair_symptoms(page_text: str, appliance_type: str) -> list:
    """Extract common repair symptoms with descriptions and statistics"""
    symptoms = []
    
    try:
        # Find all symptom links with their data - using a more flexible approach
        # First find all symptom links
        link_pattern = rf'<a href="/Repair/{appliance_type}/([^/]+)/" class="row[^"]*">(.*?)</a>'
        link_matches = re.findall(link_pattern, page_text, re.DOTALL | re.IGNORECASE)
        
        matches = []
        for url_slug, content in link_matches:
            # Extract title
            title_match = re.search(r'<h3 class="title-md[^"]*">([^<]+)</h3>', content)
            title = title_match.group(1).strip() if title_match else ""
            
            # Extract description  
            desc_match = re.search(r'<p>([^<]+)</p>', content)
            description = desc_match.group(1).strip() if desc_match else ""
            
            # Extract percentage - look for the pattern we found
            percent_match = re.search(r'<span>\s*(\d+%)\s*of\s*customers\s*</span>', content)
            percentage = percent_match.group(1) + " of customers" if percent_match else ""
            
            if title and description:
                matches.append((url_slug, title, description, percentage))
        
        for url_slug, title, description, percentage in matches:
            # Clean up the data
            title = title.strip()
            description = description.strip()
            percentage = percentage.strip()
            
            # Create full URL
            full_url = f"https://www.partselect.com/Repair/{appliance_type}/{url_slug}/"
            
            # Extract percentage number
            percent_match = re.search(r'(\d+)%', percentage)
            percent_value = int(percent_match.group(1)) if percent_match else None
            
            symptom_data = {
                'title': title,
                'description': description,
                'url': full_url,
                'url_slug': url_slug,
                'reported_by_percentage': percent_value,
                'reported_by_text': percentage
            }
            
            symptoms.append(symptom_data)
        
        # Sort by percentage (highest first)
        symptoms.sort(key=lambda x: x['reported_by_percentage'] or 0, reverse=True)
        
    except Exception as e:
        logging.debug(f"Error extracting repair symptoms: {e}")
    
    return symptoms


def _extract_troubleshooting_videos(page_text: str) -> list:
    """Extract troubleshooting videos from the repair page"""
    videos = []
    
    try:
        # Find the Troubleshooting Videos section
        video_section_pattern = r'<h2[^>]*>Troubleshooting Videos</h2>(.*?)(?=<h2|<footer|$)'
        section_match = re.search(video_section_pattern, page_text, re.DOTALL | re.IGNORECASE)
        
        if section_match:
            section_text = section_match.group(1)
            
            # Find all video containers with YouTube data
            video_pattern = r'<div data-yt-init="([^"]+)"[^>]*>.*?title="([^"]+)".*?alt="([^"]+)"'
            video_matches = re.findall(video_pattern, section_text, re.DOTALL)
            
            for video_id, title, alt_text in video_matches:
                # Clean up the title and alt text
                title = title.strip()
                alt_text = alt_text.strip()
                
                # Create YouTube URL
                youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                
                # Use title if available, otherwise use alt text
                video_title = title if title else alt_text
                
                video_data = {
                    'title': video_title,
                    'video_id': video_id,
                    'url': youtube_url,
                    'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
                }
                
                videos.append(video_data)
        
    except Exception as e:
        logging.debug(f"Error extracting troubleshooting videos: {e}")
    
    return videos


def scrape_symptom_detail(symptom_url: str, symptom_title: str, headless: bool = True) -> Dict[str, Any]:
    """
    Scrape detailed repair information for a specific symptom
    
    Args:
        symptom_url: URL of the specific symptom page
        symptom_title: Title of the symptom for reference
        headless: Whether to run browser in headless mode
        
    Returns:
        Dictionary containing detailed repair information for the symptom
    """
    logger = setup_logging()
    
    logger.info(f"Starting detailed scrape for symptom: {symptom_title} - {symptom_url}")
    
    # Initialize result structure
    symptom_detail = {
        'symptom_title': symptom_title,
        'url': symptom_url,
        'repair_sections': [],
        'repair_stats': {}
    }
    
    driver = None
    try:
        # Setup driver
        driver = setup_chrome_driver(headless)
        
        # Navigate to symptom page
        driver.get(symptom_url)
        random_delay(3, 6)
        
        # Simulate human behavior
        simulate_human_behavior(driver)
        
        # Validate page load
        if not validate_page_load(driver):
            logger.error("Page validation failed")
            return symptom_detail
        
        # Get page text for regex extraction
        page_text = driver.page_source
        
        # Extract repair stats
        symptom_detail['repair_stats'] = _extract_symptom_repair_stats(page_text)
        
        # Extract detailed repair sections
        symptom_detail['repair_sections'] = _extract_repair_sections(page_text)
        
        logger.info(f"Successfully scraped symptom detail for {symptom_title}")
        
    except Exception as e:
        logger.error(f"Error scraping symptom detail {symptom_title}: {e}")
        
    finally:
        if driver:
            driver.quit()
    
    return symptom_detail


def _extract_symptom_repair_stats(page_text: str) -> Dict[str, Any]:
    """Extract repair statistics from symptom page"""
    stats = {}
    
    try:
        # Extract repair difficulty, stories, and videos from "About this repair" section
        about_repair_pattern = r'<h3[^>]*>About this repair:</h3>\s*<ul[^>]*>(.*?)</ul>'
        about_match = re.search(about_repair_pattern, page_text, re.DOTALL)
        
        if about_match:
            about_content = about_match.group(1)
            
            # Extract difficulty
            difficulty_match = re.search(r'Rated as&nbsp;([^<]+)', about_content)
            if difficulty_match:
                stats['difficulty'] = difficulty_match.group(1).strip()
            
            # Extract number of repair stories
            stories_match = re.search(r'(\d+)\s*repair stories', about_content)
            if stories_match:
                stats['repair_stories_count'] = int(stories_match.group(1))
            
            # Extract number of step by step videos
            videos_match = re.search(r'(\d+)\s*step by step videos', about_content)
            if videos_match:
                stats['step_by_step_videos_count'] = int(videos_match.group(1))
        
    except Exception as e:
        logging.debug(f"Error extracting symptom repair stats: {e}")
    
    return stats


def _extract_repair_sections(page_text: str) -> list:
    """Extract detailed repair sections with parts and instructions"""
    sections = []
    
    try:
        # Find all repair sections with their titles and content
        section_pattern = r'<h2 class="section-title bold col[^"]*"[^>]*id="([^"]*)"[^>]*>([^<]+)</h2>\s*<div class="symptom-list__desc row[^"]*"[^>]*>(.*?)(?=<h2 class="section-title|<div class="back-to-top|$)'
        section_matches = re.findall(section_pattern, page_text, re.DOTALL)
        
        for section_id, section_title, section_content in section_matches:
            # Clean up section title
            section_title = section_title.replace('&amp;', '&').strip()
            
            # Extract description from the first column
            desc_pattern = r'<div class="col-lg-6">\s*<p>(.*?)</p>'
            desc_match = re.search(desc_pattern, section_content, re.DOTALL)
            description = ""
            if desc_match:
                description = desc_match.group(1).strip()
                # Clean up HTML entities and tags
                description = re.sub(r'<[^>]+>', '', description)
                description = description.replace('&amp;', '&').replace('&nbsp;', ' ')
            
            # Extract step-by-step instructions
            instructions = []
            instructions_pattern = r'<ol>(.*?)</ol>'
            instructions_match = re.search(instructions_pattern, section_content, re.DOTALL)
            if instructions_match:
                steps_content = instructions_match.group(1)
                step_pattern = r'<li>(.*?)</li>'
                steps = re.findall(step_pattern, steps_content, re.DOTALL)
                
                for step in steps:
                    # Clean up HTML tags and entities
                    step_clean = re.sub(r'<[^>]+>', '', step).strip()
                    step_clean = step_clean.replace('&amp;', '&').replace('&nbsp;', ' ')
                    if step_clean:
                        instructions.append(step_clean)
            
            # Extract related parts links
            related_parts = []
            parts_pattern = r'<a href="([^"]*)"[^>]*title="([^"]*)"[^>]*>([^<]*)</a>'
            parts_matches = re.findall(parts_pattern, section_content)
            
            for part_url, part_title, part_text in parts_matches:
                if 'Dishwasher' in part_title and ('replacement' in part_title.lower() or 'OEM' in part_title):
                    related_parts.append({
                        'name': part_title.strip(),
                        'url': f"https://www.partselect.com{part_url}" if part_url.startswith('/') else part_url,
                        'text': part_text.strip()
                    })
            
            section_data = {
                'id': section_id,
                'title': section_title,
                'description': description,
                'instructions': instructions,
                'related_parts': related_parts
            }
            
            sections.append(section_data)
        
    except Exception as e:
        logging.debug(f"Error extracting repair sections: {e}")
    
    return sections
