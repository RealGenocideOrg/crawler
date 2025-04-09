"""
Google Dork Searcher module for the Common Crawl Domain Extractor.

This module provides tools to:
1. Generate Google search dorks based on keywords
2. Execute search queries using dorks to find relevant URLs
3. Extract and filter domains from search results
"""

import os
import re
import time
import json
import random
import argparse
import logging
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from ..utils import (
    load_json, 
    save_json, 
    extract_domain,
    logger
)

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
                 delay_range: Tuple[float, float] = (1.0, 5.0),
                 max_results_per_dork: int = 50,
                 country_tlds: List[str] = None):
        """
        Initialize the Google Dork Searcher.
        
        Args:
            use_selenium (bool): Whether to use Selenium for browser automation
            proxy (str, optional): Proxy to use for requests (e.g., "http://user:pass@ip:port")
            delay_range (tuple): Range of random delay between requests in seconds
            max_results_per_dork (int): Maximum number of results to get per dork
            country_tlds (list): List of country TLDs to use in domain-specific searches
        """
        self.use_selenium = use_selenium
        self.proxy = proxy
        self.min_delay, self.max_delay = delay_range
        self.max_results_per_dork = max_results_per_dork
        self.country_tlds = country_tlds or ['.us', '.uk', '.ca', '.au', '.de', '.fr', '.ru', '.cn', '.jp', '.br', '.in']
        
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
        
        logger.info(f"Initialized GoogleDorkSearcher (use_selenium={use_selenium})")

    def _setup_selenium_driver(self):
        """Set up Selenium WebDriver for browser automation."""
        try:
            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(f"user-agent={random.choice(self.USER_AGENTS)}")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            
            if self.proxy:
                options.add_argument(f'--proxy-server={self.proxy}')
            
            service = Service(ChromeDriverManager().install())
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
            
            logger.info("Selenium WebDriver set up successfully")
        except Exception as e:
            logger.error(f"Failed to set up Selenium WebDriver: {e}")
            self.use_selenium = False

    def _random_delay(self):
        """Sleep for a random amount of time to avoid being blocked."""
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)

    def _rotate_user_agent(self):
        """Rotate user agent for requests to avoid detection."""
        self.headers["User-Agent"] = random.choice(self.USER_AGENTS)
        if self.driver:
            self.driver.execute_cdp_cmd("Network.setUserAgentOverride", {
                "userAgent": self.headers["User-Agent"]
            })

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
        Search Google using Selenium and extract result URLs.
        
        Args:
            query (str): Search query or dork
            num_results (int): Number of results to retrieve
            
        Returns:
            list: List of extracted URLs
        """
        if not self.driver:
            logger.error("Selenium WebDriver not initialized")
            return []
        
        try:
            # Encode the query parameters
            params = {
                'q': query,
                'num': min(100, num_results)  # Google allows max 100 results per page
            }
            
            # Construct the URL
            query_string = urlencode(params)
            url = f"{self.GOOGLE_SEARCH_URL}?{query_string}"
            
            logger.info(f"Searching with Selenium: {query}")
            self.driver.get(url)
            
            # Wait for search results to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.g"))
            )
            
            # Extract URLs from search results
            urls = []
            result_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.g")
            
            for element in result_elements:
                try:
                    # Find the link
                    link_element = element.find_element(By.CSS_SELECTOR, "a")
                    href = link_element.get_attribute("href")
                    
                    # Filter out non-http URLs and Google's own URLs
                    if href and href.startswith(("http://", "https://")) and "google." not in urlparse(href).netloc:
                        urls.append(href)
                        
                        if len(urls) >= num_results:
                            break
                except NoSuchElementException:
                    continue
            
            # Click "Next" if we need more results
            if len(urls) < num_results:
                try:
                    next_button = self.driver.find_element(By.ID, "pnnext")
                    next_button.click()
                    
                    # Wait for the new results to load
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.g"))
                    )
                    
                    # Get more URLs
                    more_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.g")
                    for element in more_elements:
                        try:
                            link_element = element.find_element(By.CSS_SELECTOR, "a")
                            href = link_element.get_attribute("href")
                            
                            if href and href.startswith(("http://", "https://")) and "google." not in urlparse(href).netloc:
                                urls.append(href)
                                
                                if len(urls) >= num_results:
                                    break
                        except NoSuchElementException:
                            continue
                except (NoSuchElementException, TimeoutException):
                    pass  # No next page or loading failed
            
            logger.info(f"Retrieved {len(urls)} URLs with Selenium")
            return urls
            
        except Exception as e:
            logger.error(f"Error during Selenium search: {e}")
            return []

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
                self.driver.quit()
                logger.info("Selenium WebDriver closed")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")


def search_with_dorks(keywords_file: str, output_file: str, 
                    use_selenium: bool = False, 
                    max_dorks: int = 20,
                    results_per_dork: int = 10,
                    targeted_domains_file: Optional[str] = None):
    """
    Main function to search for domains using Google dorks based on keywords.
    
    Args:
        keywords_file (str): Path to JSON file with keywords
        output_file (str): Path to save the extracted domains
        use_selenium (bool): Whether to use Selenium for searches
        max_dorks (int): Maximum number of dorks to use
        results_per_dork (int): Number of results to get per dork
        targeted_domains_file (str, optional): Path to file with targeted domains
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Load keywords
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
        if len(keywords) > 20:
            logger.warning(f"Too many keywords ({len(keywords)}), limiting to 20")
            keywords = keywords[:20]
        
        logger.info(f"Loaded {len(keywords)} keywords")
        
        # Load targeted domains if specified
        targeted_domains = None
        if targeted_domains_file:
            targeted_domains_data = load_json(targeted_domains_file)
            if targeted_domains_data:
                if isinstance(targeted_domains_data, list):
                    targeted_domains = targeted_domains_data
                elif isinstance(targeted_domains_data, dict) and 'domains' in targeted_domains_data:
                    targeted_domains = targeted_domains_data['domains']
                else:
                    logger.warning(f"Invalid format in {targeted_domains_file}, ignoring targeted domains")
        
        # Initialize searcher
        searcher = GoogleDorkSearcher(use_selenium=use_selenium)
        
        try:
            # Search for domains
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
            
            # Save to output file
            save_json(output_domains, output_file)
            
            logger.info(f"Extracted {len(output_domains)} domains using Google dorks and saved to {output_file}")
            return True
            
        finally:
            # Make sure to close the browser
            searcher.close()
    
    except Exception as e:
        logger.error(f"Error searching with Google dorks: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search for domains using Google dorks")
    parser.add_argument("--keywords", required=True, help="Input JSON file with keywords")
    parser.add_argument("--output", default="dork_domains.json", help="Output JSON file for extracted domains")
    parser.add_argument("--use-selenium", action="store_true", help="Use Selenium for searches")
    parser.add_argument("--max-dorks", type=int, default=20, help="Maximum number of dorks to use")
    parser.add_argument("--results-per-dork", type=int, default=10, help="Number of results to get per dork")
    parser.add_argument("--targeted-domains", help="Optional file with targeted domains")
    
    args = parser.parse_args()
    
    search_with_dorks(
        args.keywords, 
        args.output, 
        args.use_selenium, 
        args.max_dorks, 
        args.results_per_dork,
        args.targeted_domains
    ) 