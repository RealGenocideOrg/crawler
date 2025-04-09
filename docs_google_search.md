# Google Dork Search Task

This document explains how to use the Google Dork Searcher module to find relevant domains by leveraging Google search operators (dorks).

## Overview

The Google Dork Searcher uses advanced search operators to find targeted URLs and domains relevant to specific keywords. It can:

1. Generate dork queries from keywords
2. Execute searches using either the requests library or Selenium
3. Extract domains from search results
4. Score and rank domains based on relevance

## Requirements

- Python 3.9+
- BeautifulSoup4 for HTML parsing
- Selenium (optional, for browser automation)
- Chrome or Chromium browser (when using Selenium)
- webdriver-manager for automatic driver management

## Usage

### Basic Usage

```bash
python -m google_search.dork_searcher --keywords keywords.json --output dork_domains.json
```

### With Selenium (more robust against blocking)

```bash
python -m google_search.dork_searcher --keywords keywords.json --output dork_domains.json --use-selenium
```

### Limiting Dork Queries

```bash
python -m google_search.dork_searcher --keywords keywords.json --output dork_domains.json --max-dorks 10
```

### Custom Results Per Dork

```bash
python -m google_search.dork_searcher --keywords keywords.json --output dork_domains.json --results-per-dork 20
```

### Using Targeted Domains

```bash
python -m google_search.dork_searcher --keywords keywords.json --output dork_domains.json --targeted-domains targeted_domains.json
```

## Input Format

The input is a JSON file with keywords, which can be either:

1. A simple array of keywords:
   ```json
   ["gaza war", "idf", "israel war", ...]
   ```

2. The output from the keyword generator:
   ```json
   {
     "seed_words": [...],
     "categories": {...},
     "combinations": [...],
     "all_keywords": ["gaza war", "idf", "israel war", ...]
   }
   ```

## Output Format

The output is a JSON file with domains and their associated data:

```json
[
  {
    "domain": "example.com",
    "score": 5.5,
    "url_count": 5,
    "urls": [
      "https://example.com/article-about-keyword",
      "https://example.com/another-relevant-page",
      ...
    ],
    "keyword_matches": {
      "gaza war": 3,
      "israel": 2,
      "conflict": 0
    }
  },
  ...
]
```

## Google Dork Techniques

The module uses a variety of Google search operators, including:

- `"keyword"` - Exact match
- `intitle:"keyword"` - In page title
- `intext:"keyword"` - In page text
- `inurl:"keyword"` - In URL
- `site:domain "keyword"` - On specific domain
- `filetype:pdf "keyword"` - PDF files
- `site:.gov "keyword"` - Government sites
- `site:.edu "keyword"` - Educational sites
- `"keyword" -site:wikipedia.org` - Exclude Wikipedia
- `"keyword" before:2023` - Before specific year
- `"keyword" after:2020` - After specific year
- `"keyword" AND "related_keyword"` - Multiple keywords

## Avoiding Google Blocking

Google may block automated queries. The module implements several techniques to reduce the risk:

1. Rotating user agents
2. Random delays between requests
3. Optional proxy support
4. Selenium browser automation (more realistic behavior)

### Using Proxies

You can use proxies programmatically (not available via command line):

```python
from google_search import GoogleDorkSearcher

searcher = GoogleDorkSearcher(
    use_selenium=True, 
    proxy="http://username:password@proxy-server:port"
)

results = searcher.search_keywords_with_dorks(keywords)
```

## Performance Considerations

- Without Selenium: Faster but more likely to be blocked
- With Selenium: More reliable but slower and requires more resources
- Google has rate limits: Using too many dorks or making requests too quickly may lead to temporary blocks
- Recommended maximum: 20-30 dorks per session with adequate delays

## Integration with Other Modules

The Google Search module can be used together with other modules in the project:

1. Generate keywords with the keyword generator
2. Use these keywords with the Google Dork Searcher to find domains
3. Further investigate these domains with the Domain Extractor
4. Store all results in Supabase

### Complete Workflow Example

```bash
# Generate keywords
python -m keyword_generator.generator --input seeds.txt --output keywords.json

# Find domains using Google dorks
python -m google_search.dork_searcher --keywords keywords.json --output dork_domains.json --use-selenium

# Extract data from Common Crawl for these domains
python -m domain_extractor.extractor --keywords keywords.json --output combined_domains.json

# Upload to Supabase
python -m supabase_uploader.uploader --input combined_domains.json
```

## Programmatic Usage

You can use the GoogleDorkSearcher class directly in your code:

```python
from google_search import GoogleDorkSearcher

# Initialize searcher
searcher = GoogleDorkSearcher(
    use_selenium=True,
    delay_range=(2.0, 7.0),  # Random delay between 2 and 7 seconds
    max_results_per_dork=50
)

# Generate dorks from keywords
keywords = ["gaza war", "israel conflict", "ceasefire"]
dorks = searcher.generate_dorks(keywords)

# Search with all dorks
try:
    domain_results = searcher.search_keywords_with_dorks(
        keywords=keywords,
        max_dorks=15,
        results_per_dork=10
    )
    
    # Process results
    for domain, data in domain_results.items():
        print(f"Domain: {domain}, Score: {data['score']}, URLs: {len(data['urls'])}")
finally:
    # Always close the browser
    searcher.close()
```

## Legal and Ethical Considerations

- Respect Google's Terms of Service
- Use reasonable delays between requests
- Consider implementing a CAPTCHA solver for longer sessions
- Be mindful of websites' `robots.txt` exclusions
- Use responsibly and avoid excessive scraping 