# Common Crawl Domain Extractor - Project Overview

This project provides a comprehensive solution for extracting domains related to specific keywords from the Common Crawl dataset and storing them in Supabase.

## Modular Architecture

The project is divided into three main components, each operating independently:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│    Keyword      │──▶│     Domain      │──▶│    Supabase     │
│   Generator     │    │    Extractor    │    │    Uploader     │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
       seeds.txt           keywords.json          domains.json
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

### 2. Domain Extractor

**Purpose**: Search Common Crawl data for domains containing content related to keywords.

**Features**:
- Support for WET, WAT, and CC-Index files
- Domain relevance scoring
- Keyword match tracking
- Efficient streaming processing

**Input**: JSON file with keywords
**Output**: JSON file with relevant domains and their scores

### 3. Supabase Uploader

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
3. Process Common Crawl data with the domain extractor to find relevant domains
4. Upload the discovered domains to Supabase for persistent storage and analysis

## Technology Stack

- **Python 3.9+**: Core language for all components
- **NLTK & spaCy**: For NLP processing in keyword generation
- **Gensim**: For word embeddings (optional)
- **Pandas**: For efficient data manipulation
- **Supabase**: For database storage
- **boto3**: For AWS/S3 integration with Common Crawl

## Scalability

The project is designed to scale from small-scale testing to processing millions of records:

- **Small scale**: Process a few Common Crawl files locally (hundreds of domains)
- **Medium scale**: Process selected segments of Common Crawl (thousands of domains)
- **Large scale**: Use AWS infrastructure for full-scale processing (millions of domains)

## Configuration Options

Each module includes multiple configuration options:

- Keyword generation depth and techniques
- Common Crawl data types and volume
- Supabase schema and batch processing settings

## Implementation Approaches

### Approach 1: Local Processing (Limited Resources)

Best for initial exploration or testing with limited resources:

```bash
# Generate keywords
python -m keyword_generator.generator --input seeds.txt --output keywords.json

# Extract domains from a sample of Common Crawl
python -m domain_extractor.extractor --keywords keywords.json --output domains.json --crawl-type wet --limit 500

# Upload to Supabase
python -m supabase_uploader.uploader --input domains.json
```

### Approach 2: AWS Integration (Full Scale)

For processing large portions of Common Crawl:

```bash
# Setup AWS and Supabase credentials in .env file

# Generate comprehensive keywords
python -m keyword_generator.generator --input seeds.txt --output keywords.json --use-embeddings

# Extract domains using AWS Athena for efficiency
python -m domain_extractor.extractor --keywords keywords.json --output domains.json --crawl-type cc-index --use-athena --limit 10000

# Upload in batches to Supabase
python -m supabase_uploader.uploader --input domains.json --batch-size 200
```

## Documentation

Detailed documentation is available for each module:

- [Keyword Generation Task](docs_keyword_generation.md)
- [Domain Extraction Task](docs_domain_extraction.md)
- [Supabase Upload Task](docs_supabase_upload.md)

## Getting Started

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Download required NLP models: `python -m spacy download en_core_web_lg`
4. Set up your `.env` file with credentials
5. Start with a small set of seed keywords
6. Follow the data flow process described above 