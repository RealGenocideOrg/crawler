#!/usr/bin/env python3
"""
Test script for the Google Dork Searcher module.
"""

import argparse
import json
import logging
from google_search import GoogleDorkSearcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main function to test Google Dork Searcher."""
    parser = argparse.ArgumentParser(description="Test Google Dork Searcher")
    parser.add_argument("--keywords", type=str, nargs="+", help="Keywords to search for")
    parser.add_argument("--keywords-file", type=str, help="JSON file containing keywords")
    parser.add_argument("--use-selenium", action="store_true", help="Use Selenium for searches")
    parser.add_argument("--max-dorks", type=int, default=5, help="Maximum number of dorks to use")
    parser.add_argument("--results-per-dork", type=int, default=5, help="Number of results per dork")
    parser.add_argument("--output", default="test_results.json", help="Output file for results")
    
    args = parser.parse_args()
    
    # Load keywords from file if provided
    if args.keywords_file:
        try:
            with open(args.keywords_file, 'r', encoding='utf-8') as f:
                keywords_data = json.load(f)
                
            if isinstance(keywords_data, list):
                args.keywords = keywords_data
            elif isinstance(keywords_data, dict) and 'all_keywords' in keywords_data:
                args.keywords = keywords_data['all_keywords']
            else:
                logger.warning("Unknown format in keywords file. Using default keywords.")
                args.keywords = ["climate change", "renewable energy", "global warming"]
        except Exception as e:
            logger.error(f"Error loading keywords file: {e}")
            args.keywords = ["climate change", "renewable energy", "global warming"]
    
    # Use default keywords if none provided
    if not args.keywords:
        logger.info("No keywords provided, using defaults")
        args.keywords = ["climate change", "renewable energy", "global warming"]
    
    logger.info(f"Testing with keywords: {args.keywords}")
    logger.info(f"Using Selenium: {args.use_selenium}")
    
    # Initialize searcher
    searcher = GoogleDorkSearcher(use_selenium=args.use_selenium)
    
    try:
        # Generate dorks
        dorks = searcher.generate_dorks(args.keywords)
        logger.info(f"Generated {len(dorks)} dorks")
        
        # Print some example dorks
        logger.info("Example dorks:")
        for i, dork in enumerate(dorks[:5]):
            logger.info(f"  {i+1}. {dork}")
        
        # Search with dorks
        results = searcher.search_keywords_with_dorks(
            keywords=args.keywords,
            max_dorks=args.max_dorks,
            results_per_dork=args.results_per_dork
        )
        
        # Print summary of results
        logger.info(f"Found {len(results)} domains")
        
        # Print top 3 domains
        logger.info("Top domains:")
        for i, (domain, data) in enumerate(list(results.items())[:3]):
            logger.info(f"  {i+1}. {domain} (score: {data['score']:.2f}, URLs: {len(data['urls'])})")
        
        # Save results
        output_domains = []
        for domain, metadata in results.items():
            output_domains.append({
                "domain": domain,
                "score": metadata["score"],
                "url_count": metadata["url_count"],
                "urls": metadata["urls"],
                "keyword_matches": metadata["keyword_matches"]
            })
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_domains, f, indent=2)
            
        logger.info(f"Results saved to {args.output}")
        
    finally:
        # Always close the browser
        searcher.close()

if __name__ == "__main__":
    main() 