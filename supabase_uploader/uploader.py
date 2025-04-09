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
        url = url or os.getenv("SUPABASE_URL")
        key = key or os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError("Supabase URL and key must be provided or set as environment variables")
        
        self.client = create_client(url, key)
        self.table_name = table_name
        logger.info(f"Initialized SupabaseUploader for table '{table_name}'")

    def create_tables_if_not_exist(self):
        """
        Create necessary tables if they don't exist.
        
        This requires Supabase database access.
        """
        # Check if table exists (this is a simplified check)
        try:
            result = self.client.table(self.table_name).select("count(*)", count="exact").limit(1).execute()
            logger.info(f"Table '{self.table_name}' exists, contains {result.count} records")
            return True
        except Exception:
            # Table might not exist, try to create it
            logger.warning(f"Table '{self.table_name}' might not exist, attempting to create...")
            
            # Define SQL to create the domain table
            # In practice, you would need administrative access to run this
            # or use Supabase's dashboard to create tables
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
            
            try:
                # Execute SQL (requires admin access)
                self.client.rpc('run_sql', {"sql": sql}).execute()
                logger.info(f"Created table '{self.table_name}'")
                return True
            except Exception as e:
                logger.error(f"Failed to create table: {e}")
                logger.error("Please create the table manually in the Supabase dashboard")
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
            
            # Process each batch
            for i, batch in enumerate(batches):
                logger.info(f"Processing batch {i+1}/{total_batches} ({len(batch)} domains)")
                
                # Upsert data
                result = self.client.table(self.table_name).upsert(
                    batch, 
                    on_conflict="domain"  # Use domain as the unique constraint
                ).execute()
                
                if hasattr(result, 'error') and result.error:
                    logger.error(f"Error in batch {i+1}: {result.error}")
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
            result = self.client.table(self.table_name).select("domain").limit(limit).execute()
            
            if hasattr(result, 'data'):
                domains = [item["domain"] for item in result.data]
                logger.info(f"Retrieved {len(domains)} existing domains")
                return domains
            else:
                logger.warning("No domains found in database")
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
        
        # Ensure tables exist
        if not uploader.create_tables_if_not_exist():
            logger.error("Failed to ensure required tables exist")
            return False
        
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
    parser = argparse.ArgumentParser(description="Upload domains to Supabase")
    parser.add_argument("--input", required=True, help="Input JSON file with domain data")
    parser.add_argument("--table", default="domains", help="Supabase table name")
    parser.add_argument("--no-filter", action="store_true", help="Don't filter out existing domains")
    
    args = parser.parse_args()
    
    upload_domains(args.input, args.table, not args.no_filter) 