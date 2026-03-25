"""
Three-dimension information classifier.
Uses the same LLM adapter pattern as adapter.py.
"""
from __future__ import annotations

import json
import re

from cortex.domain.constants import KEY_POINT_TYPES, SOURCE_WEIGHTS


CLASSIFY_PROMPT = """Analyze the following content and classify it along three information dimensions.
Return ONLY valid JSON with these fields:

1. source_type: How was this information obtained?
   - first_hand: direct personal experience, own analysis, first-person account
   - expert: interview or conversation with domain expert
   - curated: secondary curation (newsletter, roundup, analyst note)
   - published: public article, research report, press release
   - ambient: overheard, social media, casual mention

2. nature_tags: What kinds of information does this contain? (list, one or more)
   - claim: assertion or opinion about the world
   - fact: verifiable data point
   - method: how-to or framework
   - question: open question or uncertainty
   - intuition: gut feeling without full justification
   - synthesis: integration of multiple prior pieces

3. temporality: How long is this information valid?
   - permanent: timeless fact or principle
   - trend: multi-year directional trend
   - time_sensitive: relevant for days or weeks only
   - prediction: a claim about a future state

4. key_points: The 3-5 most important assertions. Each has:
   - text: the assertion in one sentence
   - type: one of data|claim|prediction|question

5. stance: For each major topic the content takes a position on:
   - topic_name: bearish|bullish|neutral|cautious

Content:
{content}"""


STANCE_PARSE_PROMPT = """The user wrote this annotation about some content they just read:
"{annotation}"

What is their stance? Return ONLY one word: agree, disagree, uncertain, or skip.
If unclear, return uncertain."""


def parse_classification(text: str) -> dict:
    """Parse LLM classification response into structured dict."""
    # Try direct JSON parse
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try extracting from markdown code fence
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}

    source_type = data.get("source_type", "published")
    key_points = _validate_key_points(data.get("key_points", []))
    return {
        "source_type": source_type,
        "source_weight": SOURCE_WEIGHTS.get(source_type, 0.5),
        "nature_tags": data.get("nature_tags", []),
        "temporality": data.get("temporality", "trend"),
        "key_points": key_points,
        "stance": data.get("stance", {}),
    }


# ---------------------------------------------------------------------------
# Key points validation
# ---------------------------------------------------------------------------

_KEY_POINTS_SENTINEL = [{"text": "(no structured key points)", "type": "claim"}]


def _validate_key_points(raw: list) -> list[dict]:
    """Validate and normalize key_points from LLM output."""
    if not isinstance(raw, list):
        return list(_KEY_POINTS_SENTINEL)

    validated = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = item.get("text", "")
        if not isinstance(text, str) or len(text.strip()) < 10:
            continue
        kp_type = item.get("type", "claim")
        if kp_type not in KEY_POINT_TYPES:
            kp_type = "claim"
        validated.append({"text": text.strip(), "type": kp_type})

    if not validated:
        return list(_KEY_POINTS_SENTINEL)

    return validated[:5]


def is_weak_key_points(kps: list[dict]) -> bool:
    """Check if key_points are too weak to be useful for signal detection."""
    if not kps:
        return True
    # Check for sentinel
    if kps == _KEY_POINTS_SENTINEL:
        return True
    if len(kps) == 1 and kps[0].get("text") == "(no structured key points)":
        return True
    # All entries have very short text
    if all(len(kp.get("text", "")) < 15 for kp in kps):
        return True
    return False
