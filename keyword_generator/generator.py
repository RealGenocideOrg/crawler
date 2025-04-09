"""
Keyword Generator module for the Common Crawl Domain Extractor.

This module provides tools to:
1. Expand seed keywords using NLP techniques
2. Generate relevant keyword variations
3. Categorize keywords by relevance and type
"""

import os
import json
import argparse
import itertools
import logging
from collections import defaultdict
import nltk
import spacy
from gensim.models import KeyedVectors
from ..utils import load_json, save_json, logger

# Download NLTK data if needed
try:
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('wordnet')
    nltk.download('punkt')

class KeywordGenerator:
    """Generate and expand keywords using various NLP techniques."""

    def __init__(self, spacy_model="en_core_web_lg", load_word2vec=False):
        """
        Initialize the keyword generator.
        
        Args:
            spacy_model (str): Name of the spaCy model to use
            load_word2vec (bool): Whether to load word2vec embeddings (memory intensive)
        """
        logger.info("Initializing KeywordGenerator")
        try:
            self.nlp = spacy.load(spacy_model)
            logger.info(f"Loaded spaCy model: {spacy_model}")
        except OSError:
            logger.warning(f"spaCy model {spacy_model} not found. Please install it with:")
            logger.warning(f"python -m spacy download {spacy_model}")
            raise

        self.word_vectors = None
        if load_word2vec:
            # This would require the model file to be downloaded separately
            # For simplicity, we'll make this an optional dependency
            logger.info("Loading word vectors (this may take a while)...")
            try:
                # User would need to download this file separately
                self.word_vectors = KeyedVectors.load_word2vec_format(
                    'models/GoogleNews-vectors-negative300.bin', 
                    binary=True
                )
                logger.info("Word vectors loaded successfully")
            except Exception as e:
                logger.warning(f"Could not load word vectors: {e}")
                logger.warning("Word embedding expansion will not be available")

    def expand_with_wordnet(self, seed_words, max_synonyms=5):
        """
        Expand seed words using WordNet synonyms.
        
        Args:
            seed_words (list): List of seed words to expand
            max_synonyms (int): Maximum number of synonyms to include per word
            
        Returns:
            set: Expanded set of keywords
        """
        from nltk.corpus import wordnet
        
        expanded = set(seed_words)
        
        for word in seed_words:
            # Get synonyms from WordNet
            for synset in wordnet.synsets(word)[:max_synonyms]:
                # Add lemma names (synonyms)
                for lemma in synset.lemma_names():
                    if lemma != word and '_' not in lemma:  # Filter out phrases with underscores
                        expanded.add(lemma)
        
        return expanded

    def expand_with_word_embeddings(self, seed_words, topn=10):
        """
        Expand seed words using word embeddings.
        
        Args:
            seed_words (list): List of seed words to expand
            topn (int): Number of similar words to find per seed word
            
        Returns:
            set: Expanded set of keywords
        """
        if not self.word_vectors:
            logger.warning("Word vectors not loaded. Skipping embedding expansion.")
            return set(seed_words)
        
        expanded = set(seed_words)
        
        for word in seed_words:
            # Get similar words using embeddings
            try:
                similar = self.word_vectors.most_similar(word, topn=topn)
                expanded.update([w[0] for w in similar])
            except KeyError:
                logger.debug(f"Word '{word}' not in embedding vocabulary")
        
        return expanded

    def extract_entities(self, seed_words, entity_types=None):
        """
        Extract named entities related to seed words.
        
        Args:
            seed_words (list): List of seed words
            entity_types (list): Types of entities to extract (e.g., ["PERSON", "ORG", "GPE"])
            
        Returns:
            set: Set of extracted entity strings
        """
        if entity_types is None:
            entity_types = ["PERSON", "ORG", "GPE", "LOC", "NORP"]
        
        entities = set()
        
        # Join the seed words with spaces for better context
        text = " ".join(seed_words)
        
        # Extract entities using spaCy
        doc = self.nlp(text)
        
        for ent in doc.ents:
            if ent.label_ in entity_types:
                entities.add(ent.text)
        
        return entities

    def generate_combinations(self, categories):
        """
        Generate combinations of words from different categories.
        
        Args:
            categories (dict): Dictionary of word categories
            
        Returns:
            set: Generated combination phrases
        """
        combinations = set()
        
        # Generate combinations between different categories
        for cat1, cat2 in itertools.combinations(categories.keys(), 2):
            for word1, word2 in itertools.product(categories[cat1], categories[cat2]):
                combinations.add(f"{word1} {word2}")
        
        return combinations

    def generate_from_seeds(self, seed_words, use_embeddings=False, use_entities=True):
        """
        Generate an expanded set of keywords from seed words.
        
        Args:
            seed_words (list): Initial seed words
            use_embeddings (bool): Whether to use word embeddings for expansion
            use_entities (bool): Whether to extract entities
            
        Returns:
            dict: Dictionary of keyword categories and combined keywords
        """
        logger.info(f"Generating keywords from {len(seed_words)} seed words")
        
        # Normalize seed words
        normalized_seeds = [w.lower().strip() for w in seed_words]
        
        # Categorize seed words
        categories = defaultdict(set)
        for word in normalized_seeds:
            # Simple categorization by word length
            # In a real system, we would have more sophisticated categorization
            if ' ' in word:
                categories['phrases'].add(word)
            elif len(word) < 5:
                categories['short_words'].add(word)
            else:
                categories['main_terms'].add(word)
        
        # Expand with WordNet
        expanded = self.expand_with_wordnet(normalized_seeds)
        logger.info(f"Expanded to {len(expanded)} keywords using WordNet")
        
        # Expand with word embeddings if available
        if use_embeddings and self.word_vectors:
            expanded = self.expand_with_word_embeddings(normalized_seeds)
            logger.info(f"Expanded to {len(expanded)} keywords using word embeddings")
        
        # Extract entities if enabled
        if use_entities:
            entities = self.extract_entities(normalized_seeds)
            expanded.update(entities)
            categories['entities'] = entities
            logger.info(f"Added {len(entities)} entity keywords")
        
        # Add expanded words to categories
        for word in expanded:
            if word not in normalized_seeds:
                categories['expanded'].add(word)
        
        # Generate combinations
        combinations = self.generate_combinations(categories)
        logger.info(f"Generated {len(combinations)} combination keywords")
        
        # Convert sets to lists for JSON serialization
        result = {
            'seed_words': normalized_seeds,
            'categories': {k: list(v) for k, v in categories.items()},
            'combinations': list(combinations),
            'all_keywords': list(expanded.union(combinations))
        }
        
        return result


def generate_keywords(seed_file, output_file, use_embeddings=False):
    """
    Main function to generate keywords from a seed file.
    
    Args:
        seed_file (str): Path to file containing seed keywords
        output_file (str): Path to save the generated keywords
        use_embeddings (bool): Whether to use word embeddings for expansion
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Load seed words from file
        with open(seed_file, 'r', encoding='utf-8') as f:
            seed_words = [line.strip() for line in f if line.strip()]
        
        # Initialize generator
        generator = KeywordGenerator(load_word2vec=use_embeddings)
        
        # Generate keywords
        keywords = generator.generate_from_seeds(
            seed_words, 
            use_embeddings=use_embeddings
        )
        
        # Save to output file
        save_json(keywords, output_file)
        
        logger.info(f"Generated {len(keywords['all_keywords'])} keywords and saved to {output_file}")
        return True
    
    except Exception as e:
        logger.error(f"Error generating keywords: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate keywords from seed words")
    parser.add_argument("--input", required=True, help="Input file with seed keywords (one per line)")
    parser.add_argument("--output", default="keywords.json", help="Output JSON file for generated keywords")
    parser.add_argument("--use-embeddings", action="store_true", help="Use word embeddings for expansion")
    
    args = parser.parse_args()
    
    generate_keywords(args.input, args.output, args.use_embeddings) 