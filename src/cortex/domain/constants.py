"""
Domain constants for the three-dimension information framework.
"""

# Source credibility weights (higher = more trustworthy)
SOURCE_WEIGHTS: dict[str, float] = {
    "first_hand": 0.95,
    "expert":     0.80,
    "curated":    0.65,
    "published":  0.50,
    "ambient":    0.30,
}

# Valid values for enum-like fields
RAW_INPUT_TYPES = frozenset(["text", "link", "audio", "image", "file", "video"])
SOURCE_TYPES    = frozenset(SOURCE_WEIGHTS.keys())
NATURE_TAGS     = frozenset(["claim", "fact", "method", "question", "intuition", "synthesis"])
TEMPORALITIES   = frozenset(["permanent", "trend", "time_sensitive", "prediction"])
USER_STANCES    = frozenset(["agree", "disagree", "uncertain", "skip"])

# Extended event types (Phase 3)
EVENT_TYPES = frozenset([
    "article", "meeting", "note", "thesis", "chat",
    "voice_memo", "image", "document", "video", "agent_analysis",
])
