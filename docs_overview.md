# Common Crawl Domain Extractor - Project Overview

This project provides a comprehensive solution for extracting domains related to specific keywords from the Common Crawl dataset and storing them in Supabase.

## Modular Architecture

The project is divided into four main components, each operating independently:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │    │                 │
│    Keyword      │──▶│  Google Search  │──▶│     Domain      │──▶│    Supabase     │
│   Generator     │    │  Dork Searcher  │    │    Extractor    │    │    Uploader     │
│                 │    │                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
       seeds.txt           keywords.json        dork_domains.json       domains.json
```

Alternatively, the Google Search and Domain Extractor modules can be used in parallel:

```
                       ┌─────────────────┐
                       │                 │
                    ┌─▶│  Google Search  │─┐
                    │  │  Dork Searcher  │ │
┌─────────────────┐ │  │                 │ │  ┌─────────────────┐
│                 │ │  └─────────────────┘ │  │                 │
│    Keyword      │─┤                      ├─▶│    Supabase     │
│   Generator     │ │  ┌─────────────────┐ │  │    Uploader     │
│                 │ │  │                 │ │  │                 │
└─────────────────┘ │  │     Domain      │ │  └─────────────────┘
                    └─▶│    Extractor    │─┘
                       │                 │
                       └─────────────────┘
```

## Module Descriptions

### 1. Keyword Generator

**Purpose**: Expand a small set of seed keywords into a comprehensive set of related terms.

**Features**:
- WordNet synonym expansion
- Word embedding similarity (optional)
- Named entity extraction
- Keyword combination generation

**Input**: Text file with seed keywords
**Output**: JSON file with expanded keywords

### 2. Google Search Dork Searcher

**Purpose**: Find domains related to keywords using Google search operators.

**Features**:
- Advanced dork query generation
- Multiple search methods (requests or Selenium)
- Anti-blocking measures (user agent rotation, delays)
- Domain relevance scoring based on URL matches

**Input**: JSON file with keywords
**Output**: JSON file with domains found via Google search

### 3. Domain Extractor

**Purpose**: Search Common Crawl data for domains containing content related to keywords.

**Features**:
- Support for WET, WAT, and CC-Index files
- Domain relevance scoring
- Keyword match tracking
- Efficient streaming processing

**Input**: JSON file with keywords
**Output**: JSON file with relevant domains and their scores

### 4. Supabase Uploader

**Purpose**: Store and manage domain data in Supabase.

**Features**:
- Batch uploading for large datasets
- Duplicate domain filtering
- Database schema management
- Error handling and logging

**Input**: JSON file with domain data
**Output**: Data stored in Supabase

## Data Flow

1. Define seed keywords related to your topic of interest
2. Run the keyword generator to expand these to hundreds of related terms
3. Use the Google Search module to find domains using dork techniques
4. Process Common Crawl data with the domain extractor to find more relevant domains
5. Upload the discovered domains to Supabase for persistent storage and analysis

## Technology Stack

- **Python 3.9+**: Core language for all components
- **NLTK & spaCy**: For NLP processing in keyword generation
- **Gensim**: For word embeddings (optional)
- **Selenium & BeautifulSoup**: For Google search automation and parsing
- **Pandas**: For efficient data manipulation
- **Supabase**: For database storage
- **boto3**: For AWS/S3 integration with Common Crawl

## Scalability

The project is designed to scale from small-scale testing to processing millions of records:

- **Small scale**: Process a few search queries or Common Crawl files locally (hundreds of domains)
- **Medium scale**: Process more search queries with proxies or selected segments of Common Crawl (thousands of domains)
- **Large scale**: Use AWS infrastructure for full-scale processing (millions of domains)

## Configuration Options

Each module includes multiple configuration options:

- Keyword generation depth and techniques
- Google search methods and anti-blocking settings
- Common Crawl data types and volume
- Supabase schema and batch processing settings

## Implementation Approaches

### Approach 1: Google Search Focus

Best for quick results without dealing with Common Crawl's large datasets:

```bash
# Generate keywords
python -m keyword_generator.generator --input seeds.txt --output keywords.json

# Search with Google dorks
python -m google_search.dork_searcher --keywords keywords.json --output dork_domains.json --use-selenium

# Upload to Supabase
python -m supabase_uploader.uploader --input dork_domains.json
```

### Approach 2: Common Crawl Focus

For more thorough but resource-intensive processing:

```bash
# Generate keywords
python -m keyword_generator.generator --input seeds.txt --output keywords.json

# Extract domains from Common Crawl
python -m domain_extractor.extractor --keywords keywords.json --output cc_domains.json --crawl-type wet --limit 1000

# Upload to Supabase
python -m supabase_uploader.uploader --input cc_domains.json
```

### Approach 3: Combined Approach (Full Scale)

For processing large portions of multiple data sources:

```bash
# Setup AWS and Supabase credentials in .env file

# Generate comprehensive keywords
python -m keyword_generator.generator --input seeds.txt --output keywords.json --use-embeddings

# Find domains using Google dorks
python -m google_search.dork_searcher --keywords keywords.json --output dork_domains.json --use-selenium --max-dorks 30

# Extract domains using AWS Athena for efficiency
python -m domain_extractor.extractor --keywords keywords.json --output cc_domains.json --crawl-type cc-index --use-athena --limit 10000

# Combine domain results
# (Use custom script to merge domain lists)

# Upload in batches to Supabase
python -m supabase_uploader.uploader --input combined_domains.json --batch-size 200
```

## Documentation

Detailed documentation is available for each module:

- [Keyword Generation Task](docs_keyword_generation.md)
- [Google Search Task](docs_google_search.md)
- [Domain Extraction Task](docs_domain_extraction.md)
- [Supabase Upload Task](docs_supabase_upload.md)

## Getting Started

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Download required NLP models: `python -m spacy download en_core_web_lg`
4. Set up your `.env` file with credentials
5. Start with a small set of seed keywords
6. Follow the data flow process described above 