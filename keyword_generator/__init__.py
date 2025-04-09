"""
Keyword Generation module for expanding seed keywords into comprehensive sets.
"""

try:
    from .generator import (
        KeywordGenerator,
        generate_keywords
    )
except ImportError:
    from keyword_generator.generator import (
        KeywordGenerator,
        generate_keywords
    ) 