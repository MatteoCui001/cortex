"""Tests for parse_classification (LLM response parser)."""

import json

from cortex.adapters.llm.classifier import parse_classification
from cortex.domain.constants import SOURCE_WEIGHTS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_payload(**overrides) -> dict:
    base = {
        "source_type": "expert",
        "nature_tags": ["claim", "fact"],
        "temporality": "trend",
        "key_points": [{"text": "AI is growing", "type": "claim"}],
        "stance": {"ai": "bullish"},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Valid JSON input
# ---------------------------------------------------------------------------


def test_parses_valid_json():
    payload = _valid_payload()
    result = parse_classification(json.dumps(payload))
    assert result["source_type"] == "expert"
    assert result["nature_tags"] == ["claim", "fact"]
    assert result["temporality"] == "trend"
    assert result["key_points"] == [{"text": "AI is growing", "type": "claim"}]
    assert result["stance"] == {"ai": "bullish"}


def test_source_weight_populated_from_constants():
    payload = _valid_payload(source_type="first_hand")
    result = parse_classification(json.dumps(payload))
    assert result["source_weight"] == SOURCE_WEIGHTS["first_hand"]


def test_source_weight_for_each_known_type():
    for source_type, expected_weight in SOURCE_WEIGHTS.items():
        result = parse_classification(json.dumps(_valid_payload(source_type=source_type)))
        assert result["source_weight"] == expected_weight


# ---------------------------------------------------------------------------
# Markdown code-fence wrapping
# ---------------------------------------------------------------------------


def test_parses_markdown_json_fence():
    payload = _valid_payload()
    wrapped = f"```json\n{json.dumps(payload)}\n```"
    result = parse_classification(wrapped)
    assert result["source_type"] == "expert"


def test_parses_markdown_fence_no_language_tag():
    payload = _valid_payload()
    wrapped = f"```\n{json.dumps(payload)}\n```"
    result = parse_classification(wrapped)
    assert result["source_type"] == "expert"


# ---------------------------------------------------------------------------
# Defaults on missing fields
# ---------------------------------------------------------------------------


def test_missing_source_type_defaults_to_published():
    result = parse_classification(json.dumps({}))
    assert result["source_type"] == "published"


def test_missing_temporality_defaults_to_trend():
    result = parse_classification(json.dumps({}))
    assert result["temporality"] == "trend"


def test_missing_nature_tags_defaults_to_empty_list():
    result = parse_classification(json.dumps({}))
    assert result["nature_tags"] == []


def test_missing_key_points_defaults_to_empty_list():
    result = parse_classification(json.dumps({}))
    assert result["key_points"] == []


def test_missing_stance_defaults_to_empty_dict():
    result = parse_classification(json.dumps({}))
    assert result["stance"] == {}


def test_unknown_source_type_weight_defaults_to_half():
    result = parse_classification(json.dumps({"source_type": "unknown_type"}))
    assert result["source_weight"] == 0.5


# ---------------------------------------------------------------------------
# Malformed / unparseable input
# ---------------------------------------------------------------------------


def test_empty_string_returns_defaults():
    result = parse_classification("")
    assert result["source_type"] == "published"
    assert result["nature_tags"] == []


def test_plain_text_no_json_returns_defaults():
    result = parse_classification("This is just plain text, not JSON at all.")
    assert result["source_type"] == "published"
    assert result["temporality"] == "trend"


def test_broken_json_returns_defaults():
    result = parse_classification("{source_type: expert, nature_tags: [claim}")
    assert result["source_type"] == "published"


def test_broken_json_in_fence_returns_defaults():
    result = parse_classification("```json\n{bad json\n```")
    assert result["source_type"] == "published"


def test_result_always_has_required_keys():
    required = {
        "source_type",
        "source_weight",
        "nature_tags",
        "temporality",
        "key_points",
        "stance",
    }
    for text in ("", "{}", "garbage", '{"source_type": "expert"}'):
        result = parse_classification(text)
        assert required <= result.keys(), f"Missing keys for input: {text!r}"
