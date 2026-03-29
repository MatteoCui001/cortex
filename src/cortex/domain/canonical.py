"""
Entity name canonicalization.

Generates a deterministic canonical key from raw entity names so that
"OpenAI", "openai", "Open AI", "OPENAI" all resolve to the same entity.

Rules are intentionally conservative (low-risk, high-yield):
  1. Strip and lowercase
  2. Normalize whitespace / hyphens / underscores to single space
  3. Normalize fullwidth characters to ASCII
  4. Strip common corporate suffixes (Inc., Ltd., Corp., Co., etc.)
  5. Strip trailing punctuation
"""
from __future__ import annotations

import re
import unicodedata


# Corporate suffixes to strip (case-insensitive, with optional trailing dot)
_CORP_SUFFIXES = re.compile(
    r"\s*\b(inc\.?|ltd\.?|corp\.?|co\.?|llc\.?|plc\.?|gmbh|s\.?a\.?|"
    r"limited|corporation|company|incorporated)\s*$",
    re.IGNORECASE,
)

# Whitespace / separator normalization
_SEPARATORS = re.compile(r"[\s\-_]+")

# Trailing punctuation
_TRAILING_PUNCT = re.compile(r"[.,;:!?]+$")


def canonical_key(name: str) -> str:
    """Return a deterministic canonical key for entity dedup.

    >>> canonical_key("OpenAI")
    'openai'
    >>> canonical_key("Open AI")
    'open ai'
    >>> canonical_key("open-ai")
    'open ai'
    >>> canonical_key("Tesla, Inc.")
    'tesla'
    >>> canonical_key("  NVIDIA  Corp. ")
    'nvidia'
    """
    if not name:
        return ""
    # Fullwidth -> ASCII (e.g. Ｏｐｅｎ -> Open)
    text = unicodedata.normalize("NFKC", name)
    # Lowercase
    text = text.lower().strip()
    # Normalize separators
    text = _SEPARATORS.sub(" ", text)
    # Strip corporate suffixes
    text = _CORP_SUFFIXES.sub("", text).strip()
    # Strip trailing punctuation
    text = _TRAILING_PUNCT.sub("", text).strip()
    return text
