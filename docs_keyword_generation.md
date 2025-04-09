# Keyword Generation Task

This document explains how to use the keyword generation module to create expanded sets of relevant keywords from seed terms.

## Overview

The keyword generator takes a set of seed keywords and expands them using a combination of:
1. WordNet synonyms
2. Word embeddings (optional)
3. Entity extraction
4. Keyword combinations

## Requirements

- Python 3.9+
- NLTK with WordNet corpus
- spaCy with a language model (default: en_core_web_lg)
- Gensim (for word embeddings)

## Usage

### Basic Usage

```bash
python -m keyword_generator.generator --input seeds.txt --output keywords.json
```

### With Word Embeddings

```bash
python -m keyword_generator.generator --input seeds.txt --output keywords.json --use-embeddings
```

## Input Format

The input file should contain one seed keyword per line:

```
gaza war
idf
israel war
...
```

## Output Format

The output is a JSON file with the following structure:

```json
{
  "seed_words": ["gaza war", "idf", "israel war"],
  "categories": {
    "phrases": ["gaza war", "israel war"],
    "short_words": ["idf"],
    "main_terms": ["gaza", "israel"],
    "entities": ["Gaza", "Israel", "IDF"],
    "expanded": ["conflict", "battle", "military", ...]
  },
  "combinations": ["gaza conflict", "israel military", ...],
  "all_keywords": ["gaza war", "idf", "israel war", "conflict", ...]
}
```

## Advanced Configuration

### Customizing Word Embeddings

To use custom word embeddings:

1. Download pre-trained word vectors (e.g., Google News word2vec)
2. Place them in the `models/` directory
3. Update the path in the `KeywordGenerator` initialization

### Tuning Keyword Expansion

The keyword generator allows several parameters to be adjusted:

- `max_synonyms`: Maximum number of WordNet synonyms per word (default: 5)
- `topn`: Number of similar words to find with embeddings (default: 10)
- `entity_types`: Types of named entities to extract (default: ["PERSON", "ORG", "GPE", "LOC", "NORP"])

### Programmatic Usage

You can use the KeywordGenerator class directly in your code:

```python
from keyword_generator import KeywordGenerator

# Initialize generator
generator = KeywordGenerator(spacy_model="en_core_web_sm", load_word2vec=False)

# Generate keywords
seed_words = ["gaza war", "idf", "israel war"]
keywords = generator.generate_from_seeds(
    seed_words, 
    use_embeddings=False,
    use_entities=True
)

# Access expanded keywords
all_keywords = keywords["all_keywords"]
```

## Performance Considerations

- The spaCy model (especially `en_core_web_lg`) requires significant memory
- Word embeddings can consume 3-5GB of RAM when loaded
- Processing large sets of seed keywords (>1000) may take several minutes

## Troubleshooting

### Missing NLTK Data

If you encounter errors about missing NLTK data:

```bash
python -m nltk.downloader wordnet
python -m nltk.downloader punkt
```

### Missing spaCy Model

If you encounter errors about missing spaCy models:

```bash
python -m spacy download en_core_web_lg
# Or for a smaller model
python -m spacy download en_core_web_sm
```

## Example Workflow

1. Start with a focused set of seed words (10-20 terms)
2. Run the keyword generator to expand to hundreds of related terms
3. Review generated keywords and filter if needed
4. Use the expanded set for domain extraction 