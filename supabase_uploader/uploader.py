"""
Supabase Uploader module for the Common Crawl Domain Extractor.

This module provides tools to:
1. Upload extracted domains to Supabase
2. Update existing domains with new information
3. Batch process large domain lists efficiently
"""

import os
import json
import time
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
# Try absolute import first, fall back to relative import
try:
    from utils.common import load_json, logger
except ImportError:
    # For when the module is run directly
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.common import load_json, logger

# Load environment variables
load_dotenv()

class DirectSupabaseUploader:
    """Upload and manage domain data in Supabase using direct HTTP requests."""
    
    def __init__(self, url, key, table_name="domains"):
        """
        Initialize the uploader.
        
        Args:
            url (str): Supabase URL
            key (str): Supabase API key or service role key
            table_name (str): Name of the table to store domains
        """
        if not url or not key:
            raise ValueError("Supabase URL and key must be provided")
        
        # Remove trailing slash if present
        self.url = url.rstrip('/')
        self.key = key
        self.table_name = table_name
        
        # Set up headers for authentication
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        logger.info(f"Initialized DirectSupabaseUploader for table '{table_name}'")

    def create_tables_if_not_exist(self):
        """
        Create necessary tables if they don't exist.
        
        This requires Supabase database access.
        """
        # Check if table exists
        check_url = f"{self.url}/rest/v1/{self.table_name}?select=count(*)"
        
        try:
            response = requests.get(check_url, headers=self.headers, params={"limit": 1})
            
            if response.status_code == 200:
                logger.info(f"Table '{self.table_name}' exists")
                return True
            
            # Table might not exist
            logger.warning(f"Table '{self.table_name}' might not exist, attempting to create...")
            
            # Define SQL to create the domain table
            sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                domain TEXT NOT NULL UNIQUE,
                score FLOAT NOT NULL,
                matches JSONB,
                keywords JSONB,
                last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS {self.table_name}_domain_idx ON {self.table_name} (domain);
            CREATE INDEX IF NOT EXISTS {self.table_name}_score_idx ON {self.table_name} (score DESC);
            """
            
            # Execute SQL using RPC
            rpc_url = f"{self.url}/rest/v1/rpc/run_sql"
            rpc_data = {"sql": sql}
            
            response = requests.post(rpc_url, headers=self.headers, json=rpc_data)
            
            if response.status_code in [200, 201, 204]:
                logger.info(f"Created table '{self.table_name}'")
                return True
            else:
                logger.error(f"Failed to create table: {response.text}")
                logger.error("Please create the table manually in the Supabase dashboard")
                return False
                
        except Exception as e:
            logger.error(f"Error checking/creating table: {e}")
            return False

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

    def upsert_domains(self, domains: List[Dict[str, Any]], batch_size=100) -> bool:
        """
        Insert or update domains in Supabase.
        
        Args:
            domains (list): List of domain dictionaries
            batch_size (int): Size of each batch
            
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
                    "score": domain_data.get("score", 1.0),
                    "matches": json.dumps(domain_data.get("matches", {})),
                    "keywords": json.dumps(list(domain_data.get("matches", {}).keys())),
                    "last_updated": timestamp
                }
                formatted_domains.append(record)
            
            # Split into batches for more efficient processing
            batches = self._batch_domains(formatted_domains, batch_size)
            total_batches = len(batches)
            
            logger.info(f"Uploading {len(formatted_domains)} domains in {total_batches} batches")
            
            # Upsert URL
            upsert_url = f"{self.url}/rest/v1/{self.table_name}"
            
            # Process each batch
            for i, batch in enumerate(batches):
                logger.info(f"Processing batch {i+1}/{total_batches} ({len(batch)} domains)")
                
                # Add on_conflict parameter to enable upsert
                params = {"on_conflict": "domain"}
                
                # Upsert data
                response = requests.post(upsert_url, headers=self.headers, params=params, json=batch)
                
                if response.status_code not in [200, 201, 202, 204]:
                    logger.error(f"Error in batch {i+1}: {response.text}")
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
            url = f"{self.url}/rest/v1/{self.table_name}"
            params = {
                "select": "domain",
                "limit": limit
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                domains = [item["domain"] for item in response.json()]
                logger.info(f"Retrieved {len(domains)} existing domains")
                return domains
            else:
                logger.warning(f"Failed to get existing domains: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error retrieving existing domains: {e}")
            return []

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
        uploader = DirectSupabaseUploader(
            url=os.getenv("SUPABASE_URL"), 
            key=os.getenv("SUPABASE_KEY"), 
            table_name=table_name
        )
        
        # Ensure tables exist
        if not uploader.create_tables_if_not_exist():
            logger.error("Failed to ensure required tables exist")
            return False
        
        # Load domains from file
        with open(domains_file, 'r', encoding='utf-8') as f:
            domains = json.load(f)
        
        if not domains:
            logger.error(f"No domains found in {domains_file}")
            return False
        
        logger.info(f"Loaded {len(domains)} domains from {domains_file}")
        
        # Filter existing domains if requested
        if filter_existing:
            existing_domains = uploader.get_existing_domains()
            existing_set = set(existing_domains)
            filtered = [d for d in domains if d["domain"] not in existing_set]
            
            logger.info(f"Filtered out {len(domains) - len(filtered)} existing domains")
            
            if not filtered:
                logger.info("No new domains to upload")
                return True
            
            domains = filtered
        
        # Upload domains
        success = uploader.upsert_domains(domains)
        
        if success:
            logger.info("Domain upload completed successfully")
        else:
            logger.error("Domain upload failed")
        
        return success
    
    except Exception as e:
        logger.error(f"Error uploading domains: {e}")
        logger.exception("Details:")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload domains to Supabase")
    parser.add_argument("--input", required=True, help="Input JSON file with domain data")
    parser.add_argument("--table", default="domains", help="Supabase table name")
    parser.add_argument("--no-filter", action="store_true", help="Don't filter out existing domains")
    
    args = parser.parse_args()
    
    upload_domains(args.input, args.table, not args.no_filter) 