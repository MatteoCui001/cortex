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

# Key point type vocabulary
KEY_POINT_TYPES = frozenset(["data", "claim", "prediction", "question"])

# Signal detection types and base priority weights
SIGNAL_TYPES = frozenset([
    "new_signal", "redundant", "contradiction", "answer", "bridge",
])
SIGNAL_TYPE_BASE_PRIORITY: dict[str, float] = {
    "contradiction": 1.0,
    "answer": 0.8,
    "bridge": 0.6,
    "new_signal": 0.4,
    "redundant": 0.0,
}

# Signal feedback verdict types
SIGNAL_FEEDBACK_VERDICTS = frozenset([
    "useful", "not_useful", "wrong", "save_for_later",
])

# Phase 4: Notification constants
NOTIFICATION_STATUSES = frozenset([
    "pending", "delivered", "read", "acked", "dismissed", "failed",
])
NOTIFICATION_CHANNELS = frozenset(["inbox", "webhook"])
PRIORITY_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2}
