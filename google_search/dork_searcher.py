"""
Google Dork Searcher module for the Common Crawl Domain Extractor.

This module provides tools to:
1. Generate Google search dorks based on keywords
2. Execute search queries using dorks to find relevant URLs
3. Extract and filter domains from search results
"""

import os
import re
import sys # Add sys import
import time
import json
import random
import argparse
import logging
import traceback
from typing import List, Dict, Set, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
import platform
import subprocess
import shutil

# Try absolute import first, fall back to adding parent dir to sys.path
try:
    # Assumes 'utils' is directly under the project root (/home/crawler/crawler)
    from utils import load_json, save_json, extract_domain, logger
except ImportError:
    # This handles running the script directly
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.append(project_root)
    # Retry the import
    from utils import load_json, save_json, extract_domain, logger

class GoogleDorkSearcher:
    """Search for URLs using Google dorks based on keywords."""
    
    # Google search URL
    GOOGLE_SEARCH_URL = "https://www.google.com/search"
    
    # Default headers to mimic browser behavior
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "DNT": "1"
    }
    
    # User agents for rotation (to avoid blocking)
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ]
    
    # Dork templates that can be applied to keywords
    DORK_TEMPLATES = [
        '"{keyword}"',                            # Exact match
        'intitle:"{keyword}"',                    # In page title
        'intext:"{keyword}"',                     # In page text
        'inurl:"{keyword}"',                      # In URL
        'site:{domain} "{keyword}"',              # On specific domain
        '"{keyword}" filetype:pdf',               # PDF files
        '"{keyword}" filetype:doc OR filetype:docx', # Word documents
        'related:{domain}',                       # Related to domain
        'cache:{domain}',                         # Cached version
        'link:{domain}',                          # Links to domain
        'site:.gov "{keyword}"',                  # Government sites
        'site:.edu "{keyword}"',                  # Educational sites
        'site:.org "{keyword}"',                  # Organization sites
        'site:.com "{keyword}"',                  # Commercial sites
        'allintitle: "{keyword}"',                # All words in title
        'allintext: "{keyword}"',                 # All words in text
        'allinurl: "{keyword}"',                  # All words in URL
        '"{keyword}" -site:wikipedia.org',        # Exclude Wikipedia
        '"{keyword}" before:2023',                # Before specific year
        '"{keyword}" after:2020',                 # After specific year
        '"{keyword}" inanchor:click',             # Specific anchor text
        '"{keyword}" AND "{related_keyword}"',    # Two keywords
        '"{keyword}" OR "{related_keyword}"',     # Either keyword
        'intitle:"{keyword}" intext:"{related_keyword}"', # Title and text
        '"{keyword}" site:{country_tld}'          # Country-specific search
    ]
    
    def __init__(self, 
                 use_selenium: bool = False,
                 proxy: Optional[str] = None,
                 delay_range: Tuple[float, float] = (3.0, 8.0),
                 max_results_per_dork: int = 50,
                 country_tlds: List[str] = None,
                 selenium_timeout: int = 20,
                 max_retries: int = 3,
                 debug_mode: bool = True):
        """
        Initialize the Google Dork Searcher.
        
        Args:
            use_selenium (bool): Whether to use Selenium for browser automation
            proxy (str, optional): Proxy to use for requests (e.g., "http://user:pass@ip:port")
            delay_range (tuple): Range of random delay between requests in seconds
            max_results_per_dork (int): Maximum number of results to get per dork
            country_tlds (list): List of country TLDs to use in domain-specific searches
            selenium_timeout (int): Timeout for Selenium operations in seconds
            max_retries (int): Maximum number of retries for failed operations
            debug_mode (bool): Enable detailed debug logging
        """
        self.use_selenium = use_selenium
        self.proxy = proxy
        self.min_delay, self.max_delay = delay_range
        self.max_results_per_dork = max_results_per_dork
        self.country_tlds = country_tlds or ['.us', '.uk', '.ca', '.au', '.de', '.fr', '.ru', '.cn', '.jp', '.br', '.in']
        self.selenium_timeout = selenium_timeout
        self.max_retries = max_retries
        self.debug_mode = debug_mode
        
        # Set up session for requests
        self.session = requests.Session()
        self.headers = self.DEFAULT_HEADERS.copy()
        
        if proxy:
            self.session.proxies = {
                "http": proxy,
                "https": proxy
            }
        
        # Set up Selenium WebDriver if enabled
        self.driver = None
        if use_selenium:
            self._setup_selenium_driver()
        
        logger.info(f"Initialized GoogleDorkSearcher (use_selenium={use_selenium}, debug_mode={debug_mode})")

    def _check_chrome_installed(self) -> bool:
        """
        Check if Chrome/Chromium is installed on the system.
        
        Returns:
            bool: True if Chrome is installed, False otherwise
        """
        try:
            system = platform.system()
            
            if system == "Windows":
                # Check common Chrome installation paths on Windows
                chrome_paths = [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
                ]
                for path in chrome_paths:
                    if os.path.exists(path):
                        logger.info(f"Chrome found at: {path}")
                        return True
                
                # Try running 'where chrome'
                try:
                    result = subprocess.run(['where', 'chrome'], capture_output=True, text=True, check=True)
                    if result.stdout.strip():
                        logger.info(f"Chrome found using 'where': {result.stdout.strip()}")
                        return True
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass
                    
            elif system == "Linux":
                # Check common binaries on Linux
                chrome_binaries = ["google-chrome", "chromium", "chromium-browser"]
                for binary in chrome_binaries:
                    if shutil.which(binary):
                        logger.info(f"Chrome/Chromium found: {binary}")
                        return True
                    
            elif system == "Darwin":  # macOS
                # Check common macOS paths
                chrome_paths = [
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
                ]
                for path in chrome_paths:
                    if os.path.exists(path):
                        logger.info(f"Chrome found at: {path}")
                        return True
            
            logger.error("Chrome/Chromium not found on the system")
            return False
            
        except Exception as e:
            logger.error(f"Error checking Chrome installation: {e}")
            return False

    def _setup_selenium_driver(self):
        """Set up Selenium WebDriver for browser automation with extensive error handling."""
        chrome_installed = self._check_chrome_installed()
        if not chrome_installed:
            logger.error("Chrome is not installed. Selenium cannot be used.")
            self.use_selenium = False
            return
            
        logger.info("Setting up Selenium WebDriver...")
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"WebDriver setup attempt {attempt}/{self.max_retries}")
                
                options = Options()
                options.add_argument("--headless")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument(f"user-agent={random.choice(self.USER_AGENTS)}")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("--disable-extensions")
                options.add_argument("--disable-gpu")
                options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
                options.add_experimental_option("useAutomationExtension", False)
                
                # Additional options to make detection harder
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--start-maximized")
                
                if self.proxy:
                    logger.info(f"Using proxy: {self.proxy}")
                    options.add_argument(f'--proxy-server={self.proxy}')
                
                # Log Chrome version
                try:
                    system = platform.system()
                    if system == "Windows":
                        try:
                            result = subprocess.run(['reg', 'query', 'HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon', '/v', 'version'], 
                                                  capture_output=True, text=True)
                            if result.returncode == 0:
                                version = re.search(r'version\s+REG_SZ\s+([\d\.]+)', result.stdout)
                                if version:
                                    logger.info(f"Chrome version: {version.group(1)}")
                        except Exception as e:
                            logger.warning(f"Failed to get Chrome version: {e}")
                except Exception as e:
                    logger.warning(f"Error checking Chrome version: {e}")
                
                # Get ChromeDriver
                logger.info("Attempting to get ChromeDriver...")
                driver_path = None
                try:
                    driver_path = ChromeDriverManager().install()
                    logger.info(f"ChromeDriver installed at: {driver_path}")
                except Exception as e:
                    logger.error(f"ChromeDriverManager().install() failed: {e}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    if attempt < self.max_retries:
                        logger.info(f"Retrying in 5 seconds...")
                        time.sleep(5)
                        continue
                    else:
                        logger.error("Maximum retries reached. Falling back to requests.")
                        self.use_selenium = False
                        return
                
                if driver_path is None:
                    logger.error("ChromeDriverManager().install() returned None.")
                    if attempt < self.max_retries:
                        logger.info(f"Retrying in 5 seconds...")
                        time.sleep(5)
                        continue
                    else:
                        logger.error("Maximum retries reached. Falling back to requests.")
                        self.use_selenium = False
                        return
                
                # Create service and driver
                try:
                    logger.info(f"Creating Chrome service with driver path: {driver_path}")
                    service = Service(driver_path)
                    
                    logger.info("Creating Chrome WebDriver...")
                    self.driver = webdriver.Chrome(service=service, options=options)
                    
                    # Set window size
                    self.driver.set_window_size(1920, 1080)
                    
                    # Execute CDP commands to prevent detection
                    self.driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                        "userAgent": random.choice(self.USER_AGENTS)
                    })
                    
                    # Set navigator webdriver to undefined
                    self.driver.execute_script(
                        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                    )
                    
                    # Additional anti-detection measures
                    self.driver.execute_script("""
                        // Overwrite the 'navigator.webdriver' property
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                        
                        // Create a fake language list to appear more human
                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['en-US', 'en', 'es']
                        });
                        
                        // Overwrite the permissions property
                        const originalQuery = window.navigator.permissions.query;
                        window.navigator.permissions.query = (parameters) => (
                            parameters.name === 'notifications' ?
                                Promise.resolve({ state: Notification.permission }) :
                                originalQuery(parameters)
                        );
                    """)
                    
                    # Test the WebDriver
                    logger.info("Testing WebDriver...")
                    self.driver.get("https://www.google.com")
                    time.sleep(2)  # Wait to ensure page loads
                    page_title = self.driver.title
                    logger.info(f"Test navigation successful. Page title: {page_title}")
                    
                    logger.info("Selenium WebDriver set up successfully")
                    return  # Success
                    
                except WebDriverException as e:
                    logger.error(f"WebDriverException: {e}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    # Try to clean up
                    if self.driver:
                        try:
                            self.driver.quit()
                        except:
                            pass
                    self.driver = None
                    
            except Exception as e:
                logger.error(f"Failed to set up Selenium WebDriver: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
            
            # If we reach here, the attempt failed
            if attempt < self.max_retries:
                wait_time = 5 * attempt  # Incremental backoff
                logger.info(f"Retrying WebDriver setup in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error("Maximum retries reached. Falling back to requests method.")
                self.use_selenium = False
                
    def _random_delay(self, extended: bool = False):
        """
        Sleep for a random amount of time to avoid being blocked.
        
        Args:
            extended (bool): Use an extended delay range for sensitive operations
        """
        if extended:
            # Extended delay for more sensitive operations
            delay = random.uniform(self.min_delay * 1.5, self.max_delay * 2)
        else:
            delay = random.uniform(self.min_delay, self.max_delay)
            
        if self.debug_mode:
            logger.info(f"Applying random delay of {delay:.2f} seconds")
            
        time.sleep(delay)

    def generate_dorks(self, keywords: List[str], targeted_domains: List[str] = None) -> List[str]:
        """
        Generate Google search dorks from keywords.
        
        Args:
            keywords (list): List of keywords to create dorks from
            targeted_domains (list, optional): Specific domains to target in dorks
            
        Returns:
            list: List of generated dork queries
        """
        dorks = []
        
        # Get some related keywords by combining pairs
        related_keywords = []
        if len(keywords) > 1:
            for i in range(min(5, len(keywords))):
                for j in range(i+1, min(i+3, len(keywords))):
                    related_keywords.append(f"{keywords[i]} {keywords[j]}")
        
        # If no related keywords, use the primary ones
        if not related_keywords:
            related_keywords = keywords.copy()
        
        # Generate dorks for each keyword
        for keyword in keywords:
            for template in self.DORK_TEMPLATES:
                # Skip domain-specific templates if no domains provided
                if "{domain}" in template and not targeted_domains:
                    continue
                
                # Skip country-specific templates if country_tlds is empty
                if "{country_tld}" in template and not self.country_tlds:
                    continue
                
                # Generate dorks based on the template
                if "{related_keyword}" in template:
                    # Use related keywords if available
                    for related in related_keywords:
                        if related != keyword:  # Avoid using the same keyword
                            dork = template.format(
                                keyword=keyword,
                                related_keyword=related
                            )
                            dorks.append(dork)
                elif "{domain}" in template and targeted_domains:
                    # Use targeted domains if available
                    for domain in targeted_domains:
                        dork = template.format(
                            keyword=keyword,
                            domain=domain
                        )
                        dorks.append(dork)
                elif "{country_tld}" in template:
                    # Use country TLDs
                    for tld in self.country_tlds:
                        dork = template.format(
                            keyword=keyword,
                            country_tld=tld
                        )
                        dorks.append(dork)
                else:
                    # Simple substitution
                    dork = template.format(keyword=keyword)
                    dorks.append(dork)
        
        # Remove duplicates and return
        unique_dorks = list(set(dorks))
        logger.info(f"Generated {len(unique_dorks)} unique dorks from {len(keywords)} keywords")
        return unique_dorks

    def search_with_selenium(self, query: str, num_results: int = 10) -> List[str]:
        """
        Search Google using Selenium and extract result URLs with robust error handling.
        
        Args:
            query (str): Search query or dork
            num_results (int): Number of results to retrieve
            
        Returns:
            list: List of extracted URLs
        """
        if not self.driver:
            logger.error("Selenium WebDriver not initialized")
            logger.info("Falling back to requests method")
            return self.search_with_requests(query, num_results)
        
        urls = []
        try:
            # Encode the query parameters
            params = {
                'q': query,
                'num': min(100, num_results),  # Google allows max 100 results per page
                'hl': 'en'  # Force English language
            }
            
            # Construct the URL
            query_string = urlencode(params)
            url = f"{self.GOOGLE_SEARCH_URL}?{query_string}"
            
            logger.info(f"Searching with Selenium: {query}")
            
            # Load the Google search page
            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.info(f"Attempt {attempt}/{self.max_retries} to load search URL: {url}")
                    self.driver.get(url)
                    
                    # Check for Google bot detection or CAPTCHA
                    if "unusual traffic" in self.driver.page_source.lower() or "captcha" in self.driver.page_source.lower():
                        logger.warning("Google bot detection triggered. Applying extra delay...")
                        self._random_delay(extended=True)
                        continue  # Try again
                        
                    # Wait for search results to load
                    logger.info("Waiting for search results to load...")
                    try:
                        WebDriverWait(self.driver, self.selenium_timeout).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.g"))
                        )
                        logger.info("Search results loaded successfully")
                        break  # Success
                    except TimeoutException:
                        logger.warning("Timeout waiting for search results")
                        # Try alternative selectors
                        try:
                            # Try different selectors for search results
                            alternative_selectors = [
                                "div.tF2Cxc", "div.yuRUbf", "h3.LC20lb", "div[data-sokoban-container]", 
                                "a[ping]", "div[class*='result']", "a[href^='http']"
                            ]
                            for selector in alternative_selectors:
                                logger.info(f"Trying alternative selector: {selector}")
                                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                if elements:
                                    logger.info(f"Found {len(elements)} elements with selector: {selector}")
                                    break
                        except Exception as e:
                            logger.error(f"Error with alternative selectors: {e}")
                            
                        # Log page source for debugging if in debug mode
                        if self.debug_mode:
                            logger.debug(f"Page title: {self.driver.title}")
                            page_source_snippet = self.driver.page_source[:1000].replace('\n', ' ')
                            logger.debug(f"Page source snippet: {page_source_snippet}")
                        
                        if attempt < self.max_retries:
                            wait_time = 5 * attempt  # Incremental backoff
                            logger.info(f"Retrying in {wait_time} seconds...")
                            time.sleep(wait_time)
                        else:
                            logger.error("Maximum retries reached")
                            return []
                
                except WebDriverException as e:
                    logger.error(f"WebDriverException: {e}")
                    if "ERR_PROXY_CONNECTION_FAILED" in str(e) and self.proxy:
                        logger.error("Proxy connection failed")
                    
                    if attempt < self.max_retries:
                        wait_time = 5 * attempt  # Incremental backoff
                        logger.info(f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        logger.error("Maximum retries reached")
                        return []
            
            # Extract URLs from search results
            logger.info("Extracting URLs from search results")
            
            # Try different CSS selectors for result elements
            selectors_to_try = [
                "div.g", 
                "div.tF2Cxc", 
                "div.yuRUbf", 
                "div[data-sokoban-container]"
            ]
            
            result_elements = []
            for selector in selectors_to_try:
                try:
                    logger.info(f"Trying to find elements with selector: {selector}")
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        logger.info(f"Found {len(elements)} elements with selector: {selector}")
                        result_elements = elements
                        break
                except Exception as e:
                    logger.warning(f"Error with selector '{selector}': {e}")
            
            if not result_elements:
                # Fallback: try to find any links
                logger.info("No search result elements found with standard selectors, trying fallback")
                try:
                    result_elements = self.driver.find_elements(By.TAG_NAME, "a")
                    logger.info(f"Found {len(result_elements)} link elements using fallback")
                except Exception as e:
                    logger.error(f"Fallback also failed: {e}")
            
            # Process result elements
            for element in result_elements:
                try:
                    # Find the link using different strategies
                    link_element = None
                    href = None
                    
                    # Strategy 1: Element itself is a link
                    if element.tag_name == "a":
                        link_element = element
                    else:
                        # Strategy 2: Find link inside the element
                        try:
                            link_element = element.find_element(By.CSS_SELECTOR, "a")
                        except NoSuchElementException:
                            # Strategy 3: Try parent elements
                            try:
                                parent = element.find_element(By.XPATH, "./..")
                                link_element = parent.find_element(By.CSS_SELECTOR, "a")
                            except (NoSuchElementException, StaleElementReferenceException):
                                pass
                    
                    # Get href attribute if we found a link
                    if link_element:
                        href = link_element.get_attribute("href")
                    
                    # Filter out non-http URLs and Google's own URLs
                    if href and href.startswith(("http://", "https://")) and "google." not in urlparse(href).netloc:
                        # Clean up the URL (remove Google redirects)
                        clean_url = href
                        if "/url?q=" in href:
                            # Extract the actual URL from Google's redirect
                            clean_url = parse_qs(urlparse(href).query).get('q', [href])[0]
                        
                        # Ensure it's still a valid URL after cleaning
                        if clean_url.startswith(("http://", "https://")):
                            urls.append(clean_url)
                            logger.debug(f"Extracted URL: {clean_url}")
                            
                            if len(urls) >= num_results:
                                logger.info(f"Reached target of {num_results} URLs")
                                break
                except StaleElementReferenceException:
                    logger.warning("Element became stale, skipping")
                    continue
                except Exception as e:
                    logger.warning(f"Error extracting URL: {e}")
                    continue
            
            # Click "Next" if we need more results and haven't found enough
            if len(urls) < num_results:
                try:
                    logger.info("Trying to navigate to next page of results")
                    next_button = None
                    
                    # Try different selectors for the "Next" button
                    next_selectors = ["#pnnext", "a.pn", "a[id='pnnext']", "a:contains('Next')"]
                    for selector in next_selectors:
                        try:
                            if ":" in selector:  # Special case for text content selector
                                # Find all links and check text
                                links = self.driver.find_elements(By.TAG_NAME, "a")
                                for link in links:
                                    if "Next" in link.text:
                                        next_button = link
                                        break
                            else:
                                next_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                            
                            if next_button:
                                logger.info(f"Found next button with selector: {selector}")
                                break
                        except NoSuchElementException:
                            continue
                    
                    if next_button:
                        logger.info("Clicking 'Next' button")
                        # Scroll to make the button visible
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                        time.sleep(1)  # Give time for the scroll to complete
                        
                        # Click with JavaScript to avoid ElementClickInterceptedException
                        self.driver.execute_script("arguments[0].click();", next_button)
                        
                        # Wait for the new results to load
                        logger.info("Waiting for next page results to load")
                        try:
                            WebDriverWait(self.driver, self.selenium_timeout).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "div.g"))
                            )
                            logger.info("Next page loaded successfully")
                            
                            # Get more URLs
                            more_elements = []
                            for selector in selectors_to_try:
                                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                if elements:
                                    more_elements = elements
                                    break
                            
                            logger.info(f"Found {len(more_elements)} additional result elements")
                            for element in more_elements:
                                try:
                                    # Use the same extraction logic as above
                                    link_element = None
                                    if element.tag_name == "a":
                                        link_element = element
                                    else:
                                        try:
                                            link_element = element.find_element(By.CSS_SELECTOR, "a")
                                        except NoSuchElementException:
                                            try:
                                                parent = element.find_element(By.XPATH, "./..")
                                                link_element = parent.find_element(By.CSS_SELECTOR, "a")
                                            except (NoSuchElementException, StaleElementReferenceException):
                                                pass
                                    
                                    if link_element:
                                        href = link_element.get_attribute("href")
                                        
                                        if href and href.startswith(("http://", "https://")) and "google." not in urlparse(href).netloc:
                                            clean_url = href
                                            if "/url?q=" in href:
                                                clean_url = parse_qs(urlparse(href).query).get('q', [href])[0]
                                            
                                            if clean_url.startswith(("http://", "https://")):
                                                urls.append(clean_url)
                                                
                                                if len(urls) >= num_results:
                                                    break
                                except (StaleElementReferenceException, NoSuchElementException):
                                    continue
                                except Exception as e:
                                    logger.warning(f"Error extracting URL from next page: {e}")
                                    continue
                                    
                        except TimeoutException:
                            logger.warning("Timeout waiting for next page to load")
                        
                    else:
                        logger.info("No 'Next' button found, possibly the last page")
                        
                except (NoSuchElementException, TimeoutException) as e:
                    logger.info(f"No next page available: {e}")
                except Exception as e:
                    logger.error(f"Error navigating to next page: {e}")
            
            logger.info(f"Retrieved {len(urls)} URLs with Selenium")
            return urls[:num_results]  # Ensure we don't return more than requested
            
        except Exception as e:
            logger.error(f"Error during Selenium search: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Try to recover the driver if possible
            if self.driver:
                try:
                    # Check if driver is still responsive
                    current_url = self.driver.current_url
                    logger.info(f"Driver is still responsive, current URL: {current_url}")
                except:
                    logger.error("Driver is not responsive, attempting to recreate it")
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None
                    self._setup_selenium_driver()
            
            # If we have some URLs already, return them
            if urls:
                logger.info(f"Returning {len(urls)} URLs found before error")
                return urls
            
            # Fall back to requests method
            logger.info("Falling back to requests method after Selenium failure")
            return self.search_with_requests(query, num_results)

    def search_with_requests(self, query: str, num_results: int = 10) -> List[str]:
        """
        Search Google using requests and extract result URLs.
        
        Args:
            query (str): Search query or dork
            num_results (int): Number of results to retrieve
            
        Returns:
            list: List of extracted URLs
        """
        try:
            # Rotate user agent
            self._rotate_user_agent()
            
            # Encode the query parameters
            params = {
                'q': query,
                'num': min(100, num_results)  # Google allows max 100 results per page
            }
            
            logger.info(f"Searching with requests: {query}")
            response = self.session.get(
                self.GOOGLE_SEARCH_URL,
                params=params,
                headers=self.headers,
                timeout=15
            )
            
            if response.status_code != 200:
                logger.warning(f"Got status code {response.status_code} from Google. Might be rate-limited.")
                return []
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract URLs
            urls = []
            for result in soup.select('div.g'):
                link_element = result.select_one('a')
                if link_element and link_element.has_attr('href'):
                    href = link_element['href']
                    
                    # Filter out non-http URLs and Google's own URLs
                    if href and href.startswith(("http://", "https://")) and "google." not in urlparse(href).netloc:
                        urls.append(href)
            
            # Also try another selector for URLs
            if not urls:
                for link in soup.select('a'):
                    if link.has_attr('href'):
                        href = link['href']
                        
                        # Google search results often contain URLs in this format
                        if href.startswith('/url?q='):
                            # Extract the actual URL
                            actual_url = parse_qs(urlparse(href).query).get('q', [''])[0]
                            
                            if actual_url and actual_url.startswith(("http://", "https://")) and "google." not in urlparse(actual_url).netloc:
                                urls.append(actual_url)

            # Add logging if no URLs found after trying both selectors
            if not urls:
                logger.warning(f"No URLs extracted from response for query: {query}")
                logger.debug(f"Response status code: {response.status_code}")
                # Log snippet of response text for debugging
                response_snippet = response.text[:500].replace('\n', ' ') # Limit length and remove newlines
                logger.debug(f"Response text snippet: {response_snippet}")
            
            logger.info(f"Retrieved {len(urls)} URLs with requests")
            return urls[:num_results]
            
        except Exception as e:
            logger.error(f"Error during requests search: {e}")
            return []

    def search(self, query: str, num_results: int = 10) -> List[str]:
        """
        Search Google using the preferred method.
        
        Args:
            query (str): Search query or dork
            num_results (int): Number of results to retrieve
            
        Returns:
            list: List of extracted URLs
        """
        if self.use_selenium and self.driver:
            return self.search_with_selenium(query, num_results)
        else:
            return self.search_with_requests(query, num_results)

    def extract_domains_from_urls(self, urls: List[str]) -> Dict[str, List[str]]:
        """
        Extract domains from URLs and group URLs by domain.
        
        Args:
            urls (list): List of URLs
            
        Returns:
            dict: Dictionary with domains as keys and lists of URLs as values
        """
        domains_dict = {}
        
        for url in urls:
            try:
                domain = extract_domain(url)
                if domain:
                    if domain not in domains_dict:
                        domains_dict[domain] = []
                    domains_dict[domain].append(url)
            except Exception:
                continue
        
        return domains_dict

    def search_keywords_with_dorks(self, 
                                 keywords: List[str], 
                                 targeted_domains: List[str] = None,
                                 max_dorks: int = 20,
                                 results_per_dork: int = 10) -> Dict[str, Dict[str, Any]]:
        """
        Search for URLs related to keywords using generated dorks.
        
        Args:
            keywords (list): List of keywords to search for
            targeted_domains (list, optional): Specific domains to target
            max_dorks (int): Maximum number of dorks to use
            results_per_dork (int): Number of results to get per dork
            
        Returns:
            dict: Dictionary with domains as keys and metadata as values
        """
        # Generate dorks
        all_dorks = self.generate_dorks(keywords, targeted_domains)
        
        # Limit the number of dorks to avoid excessive requests
        dorks_to_use = all_dorks[:max_dorks]
        logger.info(f"Using {len(dorks_to_use)} dorks out of {len(all_dorks)} generated")
        
        # Initialize results
        all_urls = []
        dork_results = {}
        
        # Search with each dork
        for i, dork in enumerate(dorks_to_use):
            logger.info(f"Processing dork {i+1}/{len(dorks_to_use)}: {dork}")
            
            # Search with the dork
            urls = self.search(dork, results_per_dork)
            dork_results[dork] = urls
            all_urls.extend(urls)
            
            # Add random delay between requests
            if i < len(dorks_to_use) - 1:  # Not necessary after the last dork
                self._random_delay()
        
        # Extract and group domains
        domains_dict = self.extract_domains_from_urls(all_urls)
        
        # Count dork matches per domain
        domain_metadata = {}
        for domain, urls in domains_dict.items():
            # Initialize domain data
            domain_metadata[domain] = {
                "urls": urls,
                "url_count": len(urls),
                "dork_matches": {},
                "keyword_matches": {k: 0 for k in keywords}
            }
            
            # Count matches per dork
            for dork, dork_urls in dork_results.items():
                matches = sum(1 for url in urls if url in dork_urls)
                if matches > 0:
                    domain_metadata[domain]["dork_matches"][dork] = matches
            
            # Count keyword occurrences in URLs
            for keyword in keywords:
                keyword_lower = keyword.lower()
                for url in urls:
                    if keyword_lower in url.lower():
                        domain_metadata[domain]["keyword_matches"][keyword] += 1
            
            # Calculate a score based on URL count and keyword matches
            match_score = sum(domain_metadata[domain]["keyword_matches"].values())
            domain_metadata[domain]["score"] = len(urls) * (1.0 + 0.1 * match_score)
        
        # Sort domains by score
        sorted_domains = {
            k: v for k, v in sorted(
                domain_metadata.items(),
                key=lambda item: item[1]["score"],
                reverse=True
            )
        }
        
        logger.info(f"Found {len(sorted_domains)} domains using Google dorks")
        return sorted_domains

    def close(self):
        """Close the Selenium WebDriver if it was used."""
        if self.driver:
            try:
                logger.info("Closing Selenium WebDriver")
                self.driver.quit()
                logger.info("Selenium WebDriver closed successfully")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")

    def _rotate_user_agent(self):
        """Rotate user agent for requests to avoid detection."""
        self.headers["User-Agent"] = random.choice(self.USER_AGENTS)
        if self.driver:
            self.driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                "userAgent": self.headers["User-Agent"]
            })


def search_with_dorks(keywords_file: str, output_file: str, 
                    use_selenium: bool = False, 
                    max_dorks: int = 20,
                    results_per_dork: int = 10,
                    targeted_domains_file: Optional[str] = None,
                    selenium_timeout: int = 20,
                    debug_mode: bool = True,
                    max_retries: int = 3,
                    delay_range: Tuple[float, float] = (3.0, 8.0)):
    """
    Main function to search for domains using Google dorks based on keywords.
    
    Args:
        keywords_file (str): Path to JSON file with keywords
        output_file (str): Path to save the extracted domains
        use_selenium (bool): Whether to use Selenium for searches
        max_dorks (int): Maximum number of dorks to use
        results_per_dork (int): Number of results to get per dork
        targeted_domains_file (str, optional): Path to file with targeted domains
        selenium_timeout (int): Timeout for Selenium operations in seconds
        debug_mode (bool): Enable detailed debug logging
        max_retries (int): Maximum number of retries for failed operations
        delay_range (tuple): Range of random delay between requests in seconds
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Configure logging level based on debug_mode
        if debug_mode:
            logger.setLevel(logging.DEBUG)
            logger.info("Debug mode enabled - verbose logging activated")
        
        logger.info(f"Starting Google dork search with params: use_selenium={use_selenium}, max_dorks={max_dorks}, results_per_dork={results_per_dork}")
        
        # Load keywords
        logger.info(f"Loading keywords from {keywords_file}")
        keywords_data = load_json(keywords_file)
        if not keywords_data:
            logger.error(f"Could not load keywords from {keywords_file}")
            return False
        
        # Get list of keywords
        if isinstance(keywords_data, dict) and 'all_keywords' in keywords_data:
            keywords = keywords_data['all_keywords']
        elif isinstance(keywords_data, list):
            keywords = keywords_data
        else:
            logger.error(f"Invalid keywords format in {keywords_file}")
            return False
        
        # Limit the number of keywords to avoid too many dorks
        original_keyword_count = len(keywords)
        if len(keywords) > 20:
            logger.warning(f"Too many keywords ({len(keywords)}), limiting to 20")
            keywords = keywords[:20]
        
        logger.info(f"Loaded {len(keywords)} keywords from {original_keyword_count} total")
        logger.debug(f"Keywords: {', '.join(keywords[:5])}{'...' if len(keywords) > 5 else ''}")
        
        # Load targeted domains if specified
        targeted_domains = None
        if targeted_domains_file:
            logger.info(f"Loading targeted domains from {targeted_domains_file}")
            targeted_domains_data = load_json(targeted_domains_file)
            if targeted_domains_data:
                if isinstance(targeted_domains_data, list):
                    targeted_domains = targeted_domains_data
                elif isinstance(targeted_domains_data, dict) and 'domains' in targeted_domains_data:
                    targeted_domains = targeted_domains_data['domains']
                else:
                    logger.warning(f"Invalid format in {targeted_domains_file}, ignoring targeted domains")
            
            if targeted_domains:
                logger.info(f"Loaded {len(targeted_domains)} targeted domains")
                logger.debug(f"Targeted domains: {', '.join(targeted_domains[:5])}{'...' if len(targeted_domains) > 5 else ''}")
        
        # Initialize searcher with improved parameters
        logger.info(f"Initializing GoogleDorkSearcher with use_selenium={use_selenium}")
        searcher = GoogleDorkSearcher(
            use_selenium=use_selenium,
            delay_range=delay_range,
            max_results_per_dork=results_per_dork,
            selenium_timeout=selenium_timeout,
            max_retries=max_retries,
            debug_mode=debug_mode
        )
        
        # Check if Selenium is still enabled after initialization
        if use_selenium and not searcher.use_selenium:
            logger.warning("Selenium was requested but could not be initialized. Using requests instead.")
        
        try:
            # Search for domains
            logger.info(f"Starting domain search with max_dorks={max_dorks}, results_per_dork={results_per_dork}")
            domain_results = searcher.search_keywords_with_dorks(
                keywords=keywords,
                targeted_domains=targeted_domains,
                max_dorks=max_dorks,
                results_per_dork=results_per_dork
            )
            
            # Format results for output
            output_domains = []
            for domain, metadata in domain_results.items():
                output_domains.append({
                    "domain": domain,
                    "score": metadata["score"],
                    "url_count": metadata["url_count"],
                    "urls": metadata["urls"],
                    "keyword_matches": metadata["keyword_matches"]
                })
            
            # Check if we got any results
            if not output_domains:
                logger.warning("No domains found in search results")
                return False
            
            # Sort by score in descending order
            output_domains.sort(key=lambda x: x["score"], reverse=True)
            
            # Save to output file
            logger.info(f"Saving {len(output_domains)} domains to {output_file}")
            save_json(output_domains, output_file)
            
            # Log top domains for visibility
            top_domains = [d["domain"] for d in output_domains[:5]]
            logger.info(f"Top domains: {', '.join(top_domains)}")
            
            return True
            
        finally:
            # Make sure to close the browser
            logger.info("Closing searcher resources")
            searcher.close()
    
    except Exception as e:
        logger.error(f"Error searching with Google dorks: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search for domains using Google dorks")
    parser.add_argument("--keywords", required=True, help="Input JSON file with keywords")
    parser.add_argument("--output", default="dork_domains.json", help="Output JSON file for extracted domains")
    parser.add_argument("--use-selenium", action="store_true", help="Use Selenium for searches")
    parser.add_argument("--max-dorks", type=int, default=20, help="Maximum number of dorks to use")
    parser.add_argument("--results-per-dork", type=int, default=10, help="Number of results to get per dork")
    parser.add_argument("--targeted-domains", help="Optional file with targeted domains")
    parser.add_argument("--selenium-timeout", type=int, default=20, help="Timeout for Selenium operations in seconds")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode with verbose logging")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum number of retries for failed operations")
    parser.add_argument("--min-delay", type=float, default=3.0, help="Minimum delay between requests in seconds")
    parser.add_argument("--max-delay", type=float, default=8.0, help="Maximum delay between requests in seconds")
    
    args = parser.parse_args()
    
    search_with_dorks(
        args.keywords, 
        args.output, 
        args.use_selenium, 
        args.max_dorks, 
        args.results_per_dork,
        args.targeted_domains,
        args.selenium_timeout,
        args.debug,
        args.max_retries,
        (args.min_delay, args.max_delay)
    ) 