"""
Domain Extractor module for the Common Crawl Domain Extractor.

This module provides tools to:
1. Search Common Crawl data for domains related to keywords
2. Process different types of Common Crawl files (WET, WAT, CC-Index)
3. Score and rank domains by relevance
"""

import os
import re
import json
import gzip
import time
import tempfile
import argparse
import logging
from io import BytesIO
from collections import defaultdict, Counter
from urllib.parse import urlparse
import requests
import boto3
import pandas as pd
from bs4 import BeautifulSoup
from ..utils import (
    load_json, 
    save_json, 
    extract_domain, 
    download_file,
    get_common_crawl_index_url,
    logger
)

class DomainExtractor:
    """Extract domains from Common Crawl data based on keywords."""
    
    def __init__(self, keywords, crawl_id='CC-MAIN-2023-50', min_score=1.0):
        """
        Initialize the domain extractor.
        
        Args:
            keywords (list): List of keywords to search for
            crawl_id (str): Common Crawl ID to search
            min_score (float): Minimum relevance score for domains
        """
        self.keywords = keywords
        self.crawl_id = crawl_id
        self.min_score = min_score
        self.base_url = get_common_crawl_index_url(crawl_id)
        
        # Compile regex patterns for faster matching
        self.patterns = {
            kw: re.compile(r'\b' + re.escape(kw.lower()) + r'\b', re.I) 
            for kw in keywords
        }
        
        # Initialize domain tracking
        self.domain_scores = defaultdict(float)
        self.domain_matches = defaultdict(Counter)
        
        logger.info(f"Initialized DomainExtractor with {len(keywords)} keywords")

    def get_paths_list(self, file_type='wet'):
        """
        Get list of file paths for a specific Common Crawl file type.
        
        Args:
            file_type (str): Type of Common Crawl file ('wet', 'wat', 'cc-index', etc.)
            
        Returns:
            list: List of paths
        """
        paths_url = f"{self.base_url}/{file_type}.paths.gz"
        
        try:
            logger.info(f"Downloading paths list from {paths_url}")
            response = requests.get(paths_url)
            response.raise_for_status()
            
            # Decompress and decode
            paths = gzip.decompress(response.content).decode('utf-8').splitlines()
            logger.info(f"Retrieved {len(paths)} {file_type} paths")
            
            return paths
        except Exception as e:
            logger.error(f"Error retrieving paths list: {e}")
            return []

    def process_wet_file(self, wet_path, max_domains=1000):
        """
        Process a WET file to find domains with content matching keywords.
        
        Args:
            wet_path (str): Path to the WET file within Common Crawl
            max_domains (int): Maximum number of domains to extract
            
        Returns:
            dict: Dictionary of domains with scores and matches
        """
        wet_url = f"https://commoncrawl.s3.amazonaws.com/{wet_path}"
        logger.info(f"Processing WET file: {wet_path}")
        
        try:
            # Stream response
            response = requests.get(wet_url, stream=True)
            response.raise_for_status()
            
            # Process the gzipped content
            with gzip.GzipFile(fileobj=BytesIO(response.content)) as f:
                current_url = None
                current_domain = None
                recording = False
                content = []
                domains_found = 0
                
                for line in f:
                    try:
                        line_str = line.decode('utf-8', errors='ignore').strip()
                        
                        # Extract URL from WARC headers
                        if line_str.startswith('WARC-Target-URI:'):
                            # If we were recording a previous page, process it
                            if recording and current_domain and content:
                                self._process_content(current_domain, content)
                                domains_found += 1
                                if domains_found >= max_domains:
                                    break
                            
                            # Get new URL and reset
                            current_url = line_str.split(':', 1)[1].strip()
                            current_domain = extract_domain(current_url)
                            content = []
                            recording = False
                        
                        # Start recording when we hit a blank line after headers
                        elif not recording and line_str == '':
                            recording = True
                        
                        # Record content
                        elif recording and current_domain:
                            content.append(line_str)
                
                # Process the last page if needed
                if recording and current_domain and content:
                    self._process_content(current_domain, content)
            
            return dict(self.domain_scores)
        
        except Exception as e:
            logger.error(f"Error processing WET file {wet_path}: {e}")
            return {}

    def process_wat_file(self, wat_path, max_domains=1000):
        """
        Process a WAT file to find domains with metadata matching keywords.
        
        Args:
            wat_path (str): Path to the WAT file within Common Crawl
            max_domains (int): Maximum number of domains to extract
            
        Returns:
            dict: Dictionary of domains with scores and matches
        """
        wat_url = f"https://commoncrawl.s3.amazonaws.com/{wat_path}"
        logger.info(f"Processing WAT file: {wat_path}")
        
        try:
            # Stream response
            response = requests.get(wat_url, stream=True)
            response.raise_for_status()
            
            # Process the gzipped content
            with gzip.GzipFile(fileobj=BytesIO(response.content)) as f:
                current_url = None
                current_domain = None
                current_record = {}
                recording = False
                domains_found = 0
                
                for line in f:
                    try:
                        line_str = line.decode('utf-8', errors='ignore').strip()
                        
                        # Extract URL from WARC headers
                        if line_str.startswith('WARC-Target-URI:'):
                            # If we were recording a previous page, process it
                            if recording and current_domain and current_record:
                                self._process_wat_record(current_domain, current_record)
                                domains_found += 1
                                if domains_found >= max_domains:
                                    break
                            
                            # Get new URL and reset
                            current_url = line_str.split(':', 1)[1].strip()
                            current_domain = extract_domain(current_url)
                            current_record = {'url': current_url}
                            recording = False
                        
                        # Check for JSON payload (WAT files contain JSON metadata)
                        elif line_str.startswith('{') and line_str.endswith('}'):
                            try:
                                metadata = json.loads(line_str)
                                if current_record:
                                    current_record.update(metadata)
                                recording = True
                            except json.JSONDecodeError:
                                pass
                
                # Process the last record if needed
                if recording and current_domain and current_record:
                    self._process_wat_record(current_domain, current_record)
            
            return dict(self.domain_scores)
        
        except Exception as e:
            logger.error(f"Error processing WAT file {wat_path}: {e}")
            return {}

    def process_cc_index(self, limit=1000, use_athena=False):
        """
        Process CC-Index files to find domains related to keywords.
        
        Args:
            limit (int): Maximum number of domains to extract
            use_athena (bool): Whether to use AWS Athena for querying
            
        Returns:
            dict: Dictionary of domains with scores
        """
        if use_athena:
            return self._process_cc_index_with_athena(limit)
        else:
            return self._process_cc_index_direct(limit)

    def _process_cc_index_direct(self, limit=1000):
        """
        Process CC-Index files directly by downloading and parsing.
        
        Args:
            limit (int): Maximum number of domains to extract
            
        Returns:
            dict: Dictionary of domains with scores
        """
        logger.info("Processing CC-Index files directly")
        
        # Get paths to index files
        index_paths = self.get_paths_list('cc-index-table')
        if not index_paths:
            logger.error("No index paths found")
            return {}
        
        total_domains = 0
        
        # Process a sample of index files
        for path in index_paths[:5]:  # Limit to 5 files for demonstration
            try:
                # Download index file to temporary location
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    index_url = f"https://commoncrawl.s3.amazonaws.com/{path}"
                    download_file(index_url, temp_file.name)
                    
                    # Process the file with pandas
                    df = pd.read_parquet(temp_file.name)
                    
                    # Filter for URLs containing any of our keywords
                    for keyword in self.keywords:
                        matching_df = df[df['url'].str.contains(keyword, case=False, na=False)]
                        
                        for _, row in matching_df.iterrows():
                            domain = extract_domain(row['url'])
                            if domain:
                                self.domain_scores[domain] += 1.0
                                self.domain_matches[domain][keyword] += 1
                                total_domains += 1
                                
                                if total_domains >= limit:
                                    break
                        
                        if total_domains >= limit:
                            break
                    
                # Clean up
                os.unlink(temp_file.name)
                
                if total_domains >= limit:
                    break
                    
            except Exception as e:
                logger.error(f"Error processing index file {path}: {e}")
        
        return dict(self.domain_scores)

    def _process_cc_index_with_athena(self, limit=1000):
        """
        Process CC-Index using AWS Athena for efficient querying.
        
        Args:
            limit (int): Maximum number of domains to extract
            
        Returns:
            dict: Dictionary of domains with scores
        """
        logger.info("Using AWS Athena to query CC-Index")
        
        try:
            # Initialize Athena client
            athena = boto3.client('athena')
            
            # Construct query with keywords
            keywords_clause = " OR ".join([f"url LIKE '%{kw}%'" for kw in self.keywords])
            query = f"""
            SELECT url_host_name as domain, url
            FROM "ccindex"."ccindex"
            WHERE crawl = '{self.crawl_id}'
            AND ({keywords_clause})
            LIMIT {limit}
            """
            
            # Start query execution
            response = athena.start_query_execution(
                QueryString=query,
                QueryExecutionContext={'Database': 'ccindex'},
                ResultConfiguration={
                    'OutputLocation': 's3://your-bucket/athena-results/'
                }
            )
            
            execution_id = response['QueryExecutionId']
            state = 'RUNNING'
            
            # Wait for query to complete
            while state in ['RUNNING', 'QUEUED']:
                response = athena.get_query_execution(QueryExecutionId=execution_id)
                state = response['QueryExecution']['Status']['State']
                
                if state in ['RUNNING', 'QUEUED']:
                    time.sleep(5)
            
            # Get results
            if state == 'SUCCEEDED':
                results = athena.get_query_results(QueryExecutionId=execution_id)
                
                # Process results
                for row in results['ResultSet']['Rows'][1:]:  # Skip header
                    domain = row['Data'][0]['VarCharValue']
                    url = row['Data'][1]['VarCharValue']
                    
                    self.domain_scores[domain] += 1.0
                    
                    # Track which keywords matched
                    for keyword in self.keywords:
                        if keyword.lower() in url.lower():
                            self.domain_matches[domain][keyword] += 1
                
                return dict(self.domain_scores)
            else:
                logger.error(f"Athena query failed with state: {state}")
                return {}
                
        except Exception as e:
            logger.error(f"Error querying with Athena: {e}")
            return {}

    def _process_content(self, domain, content_lines):
        """
        Process content of a WET file for a specific domain.
        
        Args:
            domain (str): Domain to process
            content_lines (list): List of content lines
        """
        # Join content lines
        content = ' '.join(content_lines)
        content_lower = content.lower()
        
        # Check for keyword matches
        matches = Counter()
        for keyword, pattern in self.patterns.items():
            matches[keyword] = len(pattern.findall(content_lower))
        
        # If we have matches, update domain score
        if matches:
            # Calculate a score based on matches
            # More keywords = higher score
            score = sum(matches.values()) * (1 + 0.1 * len(matches))
            
            self.domain_scores[domain] += score
            for kw, count in matches.items():
                if count > 0:
                    self.domain_matches[domain][kw] += count

    def _process_wat_record(self, domain, record):
        """
        Process a WAT record for a specific domain.
        
        Args:
            domain (str): Domain to process
            record (dict): WAT record data
        """
        # Extract metadata fields
        metadata = record.get('Envelope', {}).get('Payload-Metadata', {})
        
        # Get fields to search
        fields_to_search = []
        
        # Add URL
        if 'url' in record:
            fields_to_search.append(record['url'])
        
        # Add HTTP headers
        http_headers = metadata.get('HTTP-Response-Metadata', {}).get('Headers', {})
        if http_headers:
            for k, v in http_headers.items():
                fields_to_search.append(f"{k}: {v}")
        
        # Add HTML metadata
        html_meta = metadata.get('HTTP-Response-Metadata', {}).get('HTML-Metadata', {})
        
        # Add page title
        if 'Title' in html_meta:
            fields_to_search.append(html_meta['Title'])
        
        # Add meta tags
        for meta in html_meta.get('Metas', []):
            for k, v in meta.items():
                fields_to_search.append(f"{k}: {v}")
        
        # Join all fields
        all_text = ' '.join(fields_to_search)
        all_text_lower = all_text.lower()
        
        # Check for keyword matches
        matches = Counter()
        for keyword, pattern in self.patterns.items():
            matches[keyword] = len(pattern.findall(all_text_lower))
        
        # If we have matches, update domain score
        if matches:
            # Calculate a score based on matches
            # More keywords = higher score
            score = sum(matches.values()) * (1 + 0.1 * len(matches))
            
            self.domain_scores[domain] += score
            for kw, count in matches.items():
                if count > 0:
                    self.domain_matches[domain][kw] += count

    def get_top_domains(self, limit=1000):
        """
        Get the top scoring domains.
        
        Args:
            limit (int): Maximum number of domains to return
            
        Returns:
            list: List of dictionaries with domain information
        """
        # Filter domains with score above threshold
        filtered_domains = {
            domain: score for domain, score in self.domain_scores.items()
            if score >= self.min_score
        }
        
        # Sort domains by score
        sorted_domains = sorted(
            filtered_domains.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        # Format result
        result = []
        for domain, score in sorted_domains:
            result.append({
                "domain": domain,
                "score": score,
                "matches": dict(self.domain_matches[domain])
            })
        
        return result


def extract_domains(keywords_file, output_file, crawl_type='wet', limit=1000, crawl_id='CC-MAIN-2023-50'):
    """
    Main function to extract domains based on keywords.
    
    Args:
        keywords_file (str): Path to JSON file with keywords
        output_file (str): Path to save the extracted domains
        crawl_type (str): Type of Common Crawl file to process ('wet', 'wat', 'cc-index')
        limit (int): Maximum number of domains to extract
        crawl_id (str): Common Crawl ID to search
    
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
        
        logger.info(f"Loaded {len(keywords)} keywords")
        
        # Initialize extractor
        extractor = DomainExtractor(keywords, crawl_id=crawl_id)
        
        # Process files based on type
        if crawl_type == 'wet':
            # Get paths for WET files
            paths = extractor.get_paths_list('wet')
            if not paths:
                logger.error("No WET paths found")
                return False
            
            # Process a limited number of WET files
            for path in paths[:5]:  # Limit to 5 files for demonstration
                extractor.process_wet_file(path, max_domains=limit//5)
        
        elif crawl_type == 'wat':
            # Get paths for WAT files
            paths = extractor.get_paths_list('wat')
            if not paths:
                logger.error("No WAT paths found")
                return False
            
            # Process a limited number of WAT files
            for path in paths[:5]:  # Limit to 5 files for demonstration
                extractor.process_wat_file(path, max_domains=limit//5)
        
        elif crawl_type == 'cc-index':
            # Process CC-Index
            extractor.process_cc_index(limit=limit)
        
        else:
            logger.error(f"Unsupported crawl type: {crawl_type}")
            return False
        
        # Get top domains
        domains = extractor.get_top_domains(limit=limit)
        
        # Save to output file
        save_json(domains, output_file)
        
        logger.info(f"Extracted {len(domains)} domains and saved to {output_file}")
        return True
    
    except Exception as e:
        logger.error(f"Error extracting domains: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract domains from Common Crawl based on keywords")
    parser.add_argument("--keywords", required=True, help="Input JSON file with keywords")
    parser.add_argument("--output", default="domains.json", help="Output JSON file for extracted domains")
    parser.add_argument("--crawl-type", choices=['wet', 'wat', 'cc-index'], default='wet',
                       help="Type of Common Crawl file to process")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum number of domains to extract")
    parser.add_argument("--crawl-id", default='CC-MAIN-2023-50', help="Common Crawl ID to search")
    
    args = parser.parse_args()
    
    extract_domains(args.keywords, args.output, args.crawl_type, args.limit, args.crawl_id) 