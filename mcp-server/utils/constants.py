# Constants for PartSelect scraper

# Base URLs
PARTSELECT_BASE_URL = "https://www.partselect.com"
PARTSELECT_PART_URL_TEMPLATE = "https://www.partselect.com/{part_number}-1.htm"

# User agents
CHROME_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Timeouts and delays
DEFAULT_TIMEOUT = 10
MIN_DELAY = 2
MAX_DELAY = 4
MIN_CONTENT_LENGTH = 1000

# CSS Selectors
PRODUCT_NAME_SELECTORS = [
    'h1.product-name',
    'h1[data-testid="product-name"]', 
    '.product-title h1',
    'h1'
]

PRODUCT_DESCRIPTION_SELECTORS = [
    '.product-description',
    '.description', 
    '[data-testid="description"]'
]

# Regex patterns
PRICE_PATTERNS = [
    r'\$(\d+\.?\d*)',
    r'Price[:\s]*\$(\d+\.?\d*)',
    r'(\d+\.?\d*)\s*USD'
]

PART_NUMBER_PATTERNS = [
    r'PartSelect Number[:\s]*([A-Z0-9]+)',
    r'PS Number[:\s]*([A-Z0-9]+)',
    r'Part Number[:\s]*([A-Z0-9]+)'
]

MANUFACTURER_PART_PATTERNS = [
    r'Manufacturer Part Number[:\s]*([A-Z0-9]+)',
    r'Manufactured by[^:]*:?\s*([A-Z0-9]+)',
    r'OEM Part Number[:\s]*([A-Z0-9]+)'
]

# Error indicators
ERROR_INDICATORS = ['access denied', '403', 'error', 'not found']

# Chrome options for anti-detection
CHROME_OPTIONS = [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-blink-features=AutomationControlled',
    '--disable-images',
    '--disable-extensions',
    '--disable-plugins'
]

CHROME_EXPERIMENTAL_OPTIONS = {
    "excludeSwitches": ["enable-automation"],
    "useAutomationExtension": False
}

