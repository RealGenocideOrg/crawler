# Common Crawl Domain Extractor

A modular system for extracting domain URLs related to specific keywords from Common Crawl datasets and storing them in Supabase.

## Project Overview

This project consists of three main components:

1. **Google Search** - Finds domains related to keywords using Google dork techniques
2. **Domain Extractor** - Searches Common Crawl data for domains related to specified keywords
3. **Supabase Uploader** - Stores extracted domains and related metadata in Supabase

## Setup Instructions

### Prerequisites

- Python 3.9+
- pip package manager
- AWS credentials (for accessing Common Crawl data in S3)
- Supabase account and API credentials
- Chrome or Chromium browser (for Google search module)

### Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/common-crawl-domain-extractor.git
   cd common-crawl-domain-extractor
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   Create a `.env` file in the project root with:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   AWS_ACCESS_KEY_ID=your_aws_access_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret_key
   ```

## Usage

Each component can be run independently:

### 1. Google Search

```
python -m google_search.dork_searcher --keywords keywords.json --output dork_domains.json
```

### 2. Domain Extraction

```
python -m domain_extractor.extractor --keywords keywords.json --output domains.json --crawl-type wet
```

### 3. Supabase Upload

```
python -m supabase_uploader.uploader --input domains.json
```

## Data Flow

```
Input Keywords → Google Search/Domain Extraction → Supabase Storage
```

## Supported Common Crawl Data Types

- WET files (extracted text)
- WAT files (metadata)
- CC-Index files (URL indices)

## Google Search Features

- Advanced dork generation using various Google search operators
- Support for both requests and Selenium-based search
- Domain extraction and relevance scoring
- Anti-blocking measures with rotating user agents and delays

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 