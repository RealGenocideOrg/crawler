# Domain Extraction Task

This document explains how to use the domain extractor module to search Common Crawl data for relevant domains based on keywords.

## Overview

The domain extractor processes Common Crawl data to find domains containing content related to specified keywords. It can work with three types of Common Crawl files:

1. **WET files** - Text extracts from web pages (most comprehensive)
2. **WAT files** - Web page metadata
3. **CC-Index files** - Direct URL indices (most efficient)

## Requirements

- Python 3.9+
- AWS credentials (for accessing Common Crawl data)
- Sufficient disk space for temporary files
- Sufficient memory for processing large files

## Usage

### Basic Usage

```bash
python -m domain_extractor.extractor --keywords keywords.json --output domains.json
```

### With Different Crawl Types

```bash
# Using WET files (extracted text)
python -m domain_extractor.extractor --keywords keywords.json --output domains.json --crawl-type wet

# Using WAT files (metadata)
python -m domain_extractor.extractor --keywords keywords.json --output domains.json --crawl-type wat

# Using CC-Index files (most efficient)
python -m domain_extractor.extractor --keywords keywords.json --output domains.json --crawl-type cc-index
```

### Limiting Results

```bash
python -m domain_extractor.extractor --keywords keywords.json --output domains.json --limit 500
```

### Using Different Crawl ID

```bash
python -m domain_extractor.extractor --keywords keywords.json --output domains.json --crawl-id CC-MAIN-2023-14
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

The output is a JSON file with domains sorted by relevance score:

```json
[
  {
    "domain": "example.com",
    "score": 15.2,
    "matches": {
      "gaza war": 5,
      "idf": 2,
      "israel": 8
    }
  },
  {
    "domain": "another-example.org",
    "score": 9.5,
    "matches": {
      "gaza war": 3,
      "conflict": 4
    }
  },
  ...
]
```

## Choosing the Right Crawl Type

- **WET files** - Best for finding content-based matches, even when keywords appear only in the page body
- **WAT files** - Good for finding domains with keywords in titles, URLs, and metadata
- **CC-Index** - Most efficient for large-scale extraction, but only finds domains with keywords in the URL

## Storage and Performance Considerations

### WET Files

- Average size: ~150MB compressed per file
- Processing speed: ~5-10 files per hour on a typical machine
- Memory usage: Moderate (~1-2GB)

### WAT Files

- Average size: ~250MB compressed per file
- Processing speed: ~3-8 files per hour
- Memory usage: Moderate to high (~2-3GB)

### CC-Index Files

- Average size: ~300MB compressed per file
- Processing speed: Much faster (hundreds of files per hour)
- Memory usage: High (~4-8GB for Pandas operations)

## Optimizing for Limited Storage

If you have limited disk space, you can use streaming methods which never store the full files:

```bash
python -m domain_extractor.extractor --keywords keywords.json --output domains.json --stream-mode
```

## Processing Common Crawl at Scale

For processing the entire Common Crawl dataset (millions of files), consider:

1. Using AWS EC2 instances close to the Common Crawl S3 bucket
2. Using AWS Athena to query the CC-Index
3. Implementing a distributed processing system with Spark

### AWS Athena Example

To use Athena for querying Common Crawl (requires AWS access):

```bash
# Set AWS credentials in environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key

# Run with Athena option
python -m domain_extractor.extractor --keywords keywords.json --output domains.json --crawl-type cc-index --use-athena
```

## Troubleshooting

### Connection Errors

If you encounter connection errors to Common Crawl S3:

- Check your internet connection
- Ensure you have sufficient bandwidth for downloading large files
- Try a different crawl ID (some may be more accessible than others)

### Memory Errors

If you encounter memory errors:

- Reduce the batch size for processing files
- Use a machine with more RAM
- Process fewer keywords at once

### Slow Processing

To improve processing speed:

- Focus on CC-Index files instead of WET/WAT
- Limit the number of keywords
- Process only a few files as a sample first

## Example Workflow

1. Generate a comprehensive set of keywords
2. Start with a small sample of Common Crawl files to test
3. Adjust settings based on initial results
4. Scale up to process more files
5. Upload extracted domains to Supabase 