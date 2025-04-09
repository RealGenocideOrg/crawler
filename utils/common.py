"""
Common utility functions for the domain extraction project.
"""

import os
import json
import logging
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("crawler.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def load_json(filepath):
    """Load data from a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading JSON from {filepath}: {e}")
        return None

def save_json(data, filepath):
    """Save data to a JSON file."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Data saved to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Error saving JSON to {filepath}: {e}")
        return False

def extract_domain(url):
    """Extract domain from a URL."""
    try:
        parsed_url = urlparse(url)
        return parsed_url.netloc
    except Exception:
        return None

def download_file(url, local_path, chunk_size=8192):
    """Download a file from a URL with progress indication."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        logger.info(f"Downloading {url} ({total_size/1_000_000:.2f} MB)")
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
        
        logger.info(f"Downloaded to {local_path}")
        return True
    except Exception as e:
        logger.error(f"Error downloading {url}: {e}")
        return False

def get_common_crawl_index_url(crawl_id='CC-MAIN-2023-50'):
    """Get the base URL for a specific Common Crawl dataset."""
    return f"https://commoncrawl.s3.amazonaws.com/crawl-data/{crawl_id}"

def parse_args_with_defaults(args, defaults):
    """Merge command line arguments with defaults."""
    result = defaults.copy()
    for key, value in vars(args).items():
        if value is not None:
            result[key] = value
    return result 