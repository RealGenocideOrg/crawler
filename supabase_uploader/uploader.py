"""
Supabase Uploader module for the Common Crawl Domain Extractor.

This module provides tools to:
1. Upload extracted domains to Supabase
2. Update existing domains with new information
3. Batch process large domain lists efficiently
"""

import os
import sys
import json
import time
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import requests
from supabase import create_client, Client
from dotenv import load_dotenv
# Try absolute import first, fall back to relative import
try:
    from utils.common import load_json, logger
except ImportError:
    # For when the module is run directly
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.common import load_json, logger

# Load environment variables
load_dotenv()

class SupabaseUploader:
    """Upload and manage domain data in Supabase."""
    
    def __init__(self, url=None, key=None, table_name="domains"):
        """
        Initialize the Supabase uploader.
        
        Args:
            url (str): Supabase URL (if None, read from environment variable)
            key (str): Supabase API key (if None, read from environment variable)
            table_name (str): Name of the table to store domains
        """
        # Get credentials from environment if not provided
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            raise ValueError("Supabase URL and key must be provided or set as environment variables")
        
        # Ensure URL doesn't end with a slash
        if self.url.endswith('/'):
            self.url = self.url[:-1]
            
        # Create Supabase client with proper headers
        try:
            self.client = create_client(self.url, self.key)
        except Exception as e:
            logger.warning(f"Failed to create Supabase client: {e}")
            logger.warning("Will use direct REST API only")
            self.client = None
        
        self.table_name = table_name
        
        # Set REST API endpoint for direct requests
        self.rest_url = f"{self.url}/rest/v1"
            
        # Default headers for direct REST API calls
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        logger.info(f"Initialized SupabaseUploader for table '{table_name}'")
        logger.debug(f"Using REST API URL: {self.rest_url}")

    def _batch_domains(self, domains, batch_size=100):
        """
        Split domains into batches for more efficient uploading.
        
        Args:
            domains (list): List of domain dictionaries
            batch_size (int): Size of each batch
            
        Returns:
            list: List of batches
        """
        return [domains[i:i + batch_size] for i in range(0, len(domains), batch_size)]

    def upsert_domains(self, domains: List[Dict[str, Any]]) -> bool:
        """
        Insert or update domains in Supabase.
        
        Args:
            domains (list): List of domain dictionaries
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not domains:
            logger.warning("No domains to upload")
            return True
        
        try:
            # Prepare data for upsert
            formatted_domains = []
            timestamp = datetime.now().isoformat()
            
            for domain_data in domains:
                # Format record for Supabase
                record = {
                    "domain": domain_data["domain"],
                    "score": domain_data["score"],
                    "matches": json.dumps(domain_data.get("matches", {})),
                    "keywords": json.dumps(list(domain_data.get("matches", {}).keys())),
                    "last_updated": timestamp
                }
                formatted_domains.append(record)
            
            # Split into batches for more efficient processing
            batches = self._batch_domains(formatted_domains)
            total_batches = len(batches)
            
            logger.info(f"Uploading {len(formatted_domains)} domains in {total_batches} batches")
            
            # Process each batch using direct REST API
            for i, batch in enumerate(batches):
                logger.info(f"Processing batch {i+1}/{total_batches} ({len(batch)} domains)")
                
                # Use direct REST API call
                upsert_url = f"{self.rest_url}/{self.table_name}"
                logger.debug(f"Upserting to: {upsert_url}")
                
                response = requests.post(
                    upsert_url,
                    headers={**self.headers, "Prefer": "resolution=merge-duplicates"},
                    json=batch
                )
                
                if response.status_code not in (200, 201):
                    logger.error(f"Error in batch {i+1}: {response.status_code} - {response.text}")
                    return False
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            logger.info(f"Successfully uploaded {len(formatted_domains)} domains")
            return True
            
        except Exception as e:
            logger.error(f"Error upserting domains: {e}")
            return False

    def get_existing_domains(self, limit=10000) -> List[str]:
        """
        Get list of domains already in the database.
        
        Args:
            limit (int): Maximum number of domains to retrieve
            
        Returns:
            list: List of domain strings
        """
        try:
            # Use direct REST API call
            domains_url = f"{self.rest_url}/{self.table_name}?select=domain&limit={limit}"
            logger.debug(f"Getting existing domains from: {domains_url}")
            
            response = requests.get(domains_url, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                domains = [item["domain"] for item in data]
                logger.info(f"Retrieved {len(domains)} existing domains")
                return domains
            else:
                logger.warning(f"Error retrieving domains: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error retrieving existing domains: {e}")
            return []

    def filter_new_domains(self, domains: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out domains that already exist in the database.
        
        Args:
            domains (list): List of domain dictionaries
            
        Returns:
            list: Filtered list of domains
        """
        existing_domains = set(self.get_existing_domains())
        
        if not existing_domains:
            return domains
        
        filtered = [d for d in domains if d["domain"] not in existing_domains]
        
        logger.info(f"Filtered out {len(domains) - len(filtered)} existing domains")
        return filtered

    def upload_domains_from_file(self, file_path: str, filter_existing=True, batch_size=100) -> bool:
        """
        Upload domains from a JSON file to Supabase.
        
        Args:
            file_path (str): Path to JSON file with domain data
            filter_existing (bool): Whether to filter out existing domains
            batch_size (int): Size of each batch
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Load domains from file
        domains = load_json(file_path)
        
        if not domains:
            logger.error(f"No domains found in {file_path}")
            return False
        
        logger.info(f"Loaded {len(domains)} domains from {file_path}")
        
        # Filter existing domains if requested
        if filter_existing:
            domains = self.filter_new_domains(domains)
            
            if not domains:
                logger.info("No new domains to upload")
                return True
        
        # Upload domains
        return self.upsert_domains(domains)


def upload_domains(domains_file, table_name="domains", filter_existing=True):
    """
    Main function to upload domains to Supabase.
    
    Args:
        domains_file (str): Path to JSON file with domain data
        table_name (str): Name of the table to store domains
        filter_existing (bool): Whether to filter out existing domains
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize uploader
        uploader = SupabaseUploader(table_name=table_name)
        
        # Table creation logic removed - assuming table exists
        
        # Upload domains
        success = uploader.upload_domains_from_file(
            domains_file,
            filter_existing=filter_existing
        )
        
        if success:
            logger.info("Domain upload completed successfully")
        else:
            logger.error("Domain upload failed")
        
        return success
    
    except Exception as e:
        logger.error(f"Error uploading domains: {e}")
        return False


if __name__ == "__main__":
    # Configure logging with more detail
    logging.basicConfig(level=logging.DEBUG)
    
    parser = argparse.ArgumentParser(description="Upload domains to Supabase")
    parser.add_argument("--input", required=True, help="Input JSON file with domain data")
    parser.add_argument("--table", default="domains", help="Supabase table name")
    parser.add_argument("--no-filter", action="store_true", help="Don't filter out existing domains")
    parser.add_argument("--url", help="Supabase URL (optional, defaults to env var)")
    parser.add_argument("--key", help="Supabase API key (optional, defaults to env var)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Initialize uploader with optional CLI credentials
    try:
        uploader = SupabaseUploader(url=args.url, key=args.key, table_name=args.table)
        
        # Table creation logic removed - assuming table exists
        
        # Upload domains
        success = uploader.upload_domains_from_file(
            args.input,
            filter_existing=not args.no_filter
        )
        
        if success:
            logger.info("Domain upload completed successfully")
            sys.exit(0)
        else:
            logger.error("Domain upload failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error uploading domains: {e}")
        sys.exit(1) 