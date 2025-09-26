import re
import time
import random
from typing import List, Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

from pathlib import Path
import json, os, hashlib


def setup_logging():
    """Setup logging with single log file - NO STDOUT to avoid MCP protocol corruption"""
    logging.basicConfig(
        level=logging.INFO,  # Changed from DEBUG to reduce noise
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('scraper.log', mode='a'),  # Single file, append mode
            # NO StreamHandler() to avoid stdout corruption
        ]
    )
    return logging.getLogger(__name__)

def random_delay(min_seconds: int = 2, max_seconds: int = 4):
    """Add random delay to avoid detection"""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)

def extract_with_patterns(text: str, patterns: List[str], group: int = 1) -> Optional[str]:
    """Extract text using multiple regex patterns"""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(group).strip()
    return None

def extract_all_with_pattern(text: str, pattern: str, group: int = 1) -> List[str]:
    """Extract all matches for a pattern"""
    matches = re.findall(pattern, text, re.IGNORECASE)
    return [match.strip() for match in matches if match.strip()]

def safe_find_element(driver, selectors: List[str], timeout: int = 3) -> Optional[str]:
    """Safely find element using multiple selectors"""
    for selector in selectors:
        try:
            # Use a shorter timeout and direct find instead of WebDriverWait
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements and elements[0].text.strip():
                return elements[0].text.strip()
        except Exception:
            continue
    return None

def safe_find_elements(driver, selector: str) -> List:
    """Safely find multiple elements"""
    try:
        return driver.find_elements(By.CSS_SELECTOR, selector)
    except Exception as e:
        logging.error(f"Error finding elements with selector '{selector}': {e}")
        return []

def clean_price(price_text: str) -> Optional[float]:
    """Clean and convert price text to float"""
    if not price_text:
        return None
    
    # Remove currency symbols and extra whitespace
    cleaned = re.sub(r'[^\d.]', '', price_text)
    try:
        return float(cleaned)
    except ValueError:
        return None

def split_and_clean(text: str, delimiter: str = ',') -> List[str]:
    """Split text by delimiter and clean each item"""
    if not text:
        return []
    
    items = text.split(delimiter)
    return [item.strip() for item in items if item.strip()]

def validate_page_load(driver, min_content_length: int = 1000) -> bool:
    """Validate that the page loaded properly"""
    title = driver.title.lower()
    
    # Check for access denied or error pages
    if any(error in title for error in ['access denied', '403', 'error', 'not found']):
        logging.error(f"Page access denied or error: {title}")
        return False
    
    # Check content length
    page_source = driver.page_source
    if len(page_source) < min_content_length:
        logging.error(f"Page content too short: {len(page_source)} chars")
        return False
    
    return True

def setup_anti_detection(driver):
    """Apply enhanced anti-detection measures to the driver"""
    try:
        # Remove webdriver property
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Override webdriver-related properties
        driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
        driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
        
        # Set realistic screen properties
        driver.execute_script("""
            Object.defineProperty(screen, 'width', {get: () => 1920});
            Object.defineProperty(screen, 'height', {get: () => 1080});
            Object.defineProperty(screen, 'availWidth', {get: () => 1920});
            Object.defineProperty(screen, 'availHeight', {get: () => 1040});
        """)
        
        # Override chrome property
        driver.execute_script("""
            Object.defineProperty(window, 'chrome', {
                get: () => ({
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                })
            });
        """)
        
        # Add realistic permissions
        driver.execute_script("""
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        # Hide automation indicators
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => false})")
        
        logging.info("Enhanced anti-detection measures applied")
    except Exception as e:
        logging.warning(f"Could not apply all anti-detection measures: {e}")

def simulate_human_behavior(driver):
    """Simulate human-like behavior"""
    try:
        # Scroll down a bit to simulate reading
        driver.execute_script("window.scrollTo(0, 200);")
        random_delay(1, 2)
        
        # Scroll back up
        driver.execute_script("window.scrollTo(0, 0);")
        random_delay(0.5, 1)
        
        logging.debug("Human behavior simulation completed")
    except Exception as e:
        logging.debug(f"Could not simulate human behavior: {e}")

def extract_youtube_videos(driver, page_source: str) -> List[Dict[str, str]]:
    """Extract YouTube installation videos"""
    videos = []
    
    try:
        # Method 1: Find video containers with data-iframe-id
        video_containers = safe_find_elements(driver, '[data-iframe-id]')
        
        for container in video_containers:
            try:
                # Get thumbnail image
                thumbnail_img = container.find_element(By.CSS_SELECTOR, 'img[src*="img.youtube.com"]')
                src = thumbnail_img.get_attribute('src')
                
                # Extract video ID from thumbnail URL
                video_id_match = re.search(r'/vi/([a-zA-Z0-9_-]+)/', src)
                if video_id_match:
                    video_id = video_id_match.group(1)
                    
                    # Get title from img title/alt or nearby h4
                    title = (thumbnail_img.get_attribute('title') or 
                            thumbnail_img.get_attribute('alt') or
                            "Installation Video")
                    
                    try:
                        h4_element = container.find_element(By.CSS_SELECTOR, 'h4')
                        if h4_element.text.strip():
                            title = h4_element.text.strip()
                    except NoSuchElementException:
                        pass
                    
                    videos.append({
                        'title': title,
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'video_id': video_id
                    })
            except Exception as e:
                logging.debug(f"Error extracting video from container: {e}")
                continue
    
    except Exception as e:
        logging.debug(f"Error finding video containers: {e}")
    
    # Method 2: Fallback - Direct regex search in page source
    if not videos:
        try:
            youtube_matches = re.findall(r'https://img\.youtube\.com/vi/([a-zA-Z0-9_-]+)/[^"\']*', page_source)
            for video_id in youtube_matches[:5]:  # Limit to first 5
                videos.append({
                    'title': 'Installation Video',
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'video_id': video_id
                })
        except Exception as e:
            logging.debug(f"Fallback video extraction failed: {e}")
    
    return videos

def extract_model_compatibility(driver) -> List[Dict[str, str]]:
    """Extract compatible models by clicking Model Cross Reference section"""
    models = []
    
    try:
        # Click on Model Cross Reference section
        model_section = driver.find_element(By.ID, "ModelCrossReference")
        driver.execute_script("arguments[0].click();", model_section)
        
        # Wait a bit for content to load
        time.sleep(2)
        
        # Get updated page source
        updated_html = driver.page_source
        
        # Extract model data with regex
        model_pattern = r'<div class="row">\s*<div class="col-6 col-md-3">([^<]+)</div>\s*<a class="col-6 col-md-3 col-lg-2"[^>]*>([^<]+)</a>\s*<div class="col col-md-6 col-lg-7">\s*([^<]+)\s*</div>\s*</div>'
        
        matches = re.findall(model_pattern, updated_html, re.DOTALL)
        for match in matches:
            brand, model_number, description = match
            models.append({
                'brand': brand.strip(),
                'model_number': model_number.strip(),
                'description': description.strip()
            })
        
        logging.info(f"Extracted {len(models)} compatible models")
        
    except Exception as e:
        logging.debug(f"Could not extract model compatibility: {e}")
    
    return models




