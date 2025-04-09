# Supabase Upload Task

This document explains how to use the Supabase uploader module to store extracted domains in a Supabase database.

## Overview

The Supabase uploader manages the storage and organization of domain data in Supabase. It provides functionality for:

1. Creating necessary database tables
2. Uploading domains with their relevance scores
3. Updating existing domains with new information
4. Filtering duplicate domains to avoid redundancy

## Requirements

- Python 3.9+
- Supabase account and API credentials
- Supabase database access (for creating tables)

## Setup

### Supabase Project Configuration

1. Create a Supabase project at [https://supabase.com](https://supabase.com)
2. Get your project URL and API key from the project settings
3. Configure environment variables:

```bash
# Add to your .env file
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-api-key
```

### Database Schema

The uploader expects a table with the following schema:

```sql
CREATE TABLE domains (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain TEXT NOT NULL UNIQUE,
    score FLOAT NOT NULL,
    matches JSONB,
    keywords JSONB,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX domains_domain_idx ON domains (domain);
CREATE INDEX domains_score_idx ON domains (score DESC);
```

The uploader will attempt to create this table if it doesn't exist (requires database admin privileges).

## Usage

### Basic Usage

```bash
python -m supabase_uploader.uploader --input domains.json
```

### Custom Table Name

```bash
python -m supabase_uploader.uploader --input domains.json --table custom_domains
```

### Include Existing Domains

By default, the uploader filters out domains that already exist in the database. To update all domains:

```bash
python -m supabase_uploader.uploader --input domains.json --no-filter
```

## Input Format

The input is a JSON file with domains, typically the output from the domain extractor:

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

## Batch Processing

For large domain lists, the uploader processes data in batches (default: 100 domains per batch) to:
- Reduce memory usage
- Handle API rate limits
- Provide progress feedback

You can adjust the batch size when using the class directly:

```python
from supabase_uploader import SupabaseUploader

uploader = SupabaseUploader()
uploader.upload_domains_from_file("domains.json", batch_size=50)
```

## Error Handling

The uploader includes robust error handling:
- Connection errors to Supabase
- Invalid JSON in input files
- Database constraint violations
- API rate limiting

All errors are logged to both the console and a log file.

## Programmatic Usage

You can use the SupabaseUploader class directly in your code:

```python
from supabase_uploader import SupabaseUploader

# Initialize with custom credentials
uploader = SupabaseUploader(
    url="https://your-project.supabase.co",
    key="your-api-key",
    table_name="domains"
)

# Upload domains from file
uploader.upload_domains_from_file("domains.json", filter_existing=True)

# Or upload domains directly
domains = [
    {
        "domain": "example.com",
        "score": 15.2,
        "matches": {"keyword1": 5, "keyword2": 3}
    },
    # More domains...
]
uploader.upsert_domains(domains)
```

## Checking Existing Data

You can check what domains are already in your Supabase database:

```python
from supabase_uploader import SupabaseUploader

uploader = SupabaseUploader()
existing_domains = uploader.get_existing_domains(limit=1000)
print(f"Found {len(existing_domains)} existing domains")
```

## Performance Considerations

- Uploading 10,000 domains typically takes 5-10 minutes (depending on network)
- Supabase may have rate limits on the number of API calls
- The uploader includes small delays between batches to avoid rate limiting
- For extremely large datasets (>100,000 domains), consider splitting into multiple files

## Security Considerations

- Store your Supabase credentials securely
- Use environment variables or a .env file rather than hardcoding credentials
- Consider using a dedicated API key with restricted permissions for the uploader

## Example Workflow

1. Extract domains using the domain extractor
2. Review and filter domains if needed
3. Set up Supabase environment variables
4. Run the uploader to store domains
5. Verify data in Supabase dashboard

## Supabase Query Examples

Once your domains are in Supabase, you can query them using SQL in the Supabase dashboard:

```sql
-- Get top 100 domains by score
SELECT domain, score FROM domains ORDER BY score DESC LIMIT 100;

-- Find domains matching a specific keyword
SELECT domain, score FROM domains 
WHERE keywords @> '["gaza war"]'
ORDER BY score DESC;

-- Count domains by score range
SELECT 
  CASE 
    WHEN score >= 10 THEN 'High'
    WHEN score >= 5 THEN 'Medium'
    ELSE 'Low'
  END as relevance,
  COUNT(*) 
FROM domains
GROUP BY relevance;
``` 