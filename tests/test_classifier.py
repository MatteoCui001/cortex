"""Tests for parse_classification (LLM response parser)."""
import json

from cortex.adapters.llm.classifier import (
    _validate_key_points,
    is_weak_key_points,
    parse_classification,
)
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


def test_missing_key_points_defaults_to_sentinel():
    result = parse_classification(json.dumps({}))
    # Empty key_points from LLM produces the sentinel
    assert len(result["key_points"]) == 1
    assert result["key_points"][0]["text"] == "(no structured key points)"


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
    required = {"source_type", "source_weight", "nature_tags", "temporality", "key_points", "stance"}
    for text in ("", "{}", "garbage", '{"source_type": "expert"}'):
        result = parse_classification(text)
        assert required <= result.keys(), f"Missing keys for input: {text!r}"


# ---------------------------------------------------------------------------
# Key points validation
# ---------------------------------------------------------------------------

def test_validate_key_points_removes_empty_text():
    raw = [{"text": "", "type": "claim"}, {"text": "Valid assertion here", "type": "data"}]
    result = _validate_key_points(raw)
    assert len(result) == 1
    assert result[0]["text"] == "Valid assertion here"


def test_validate_key_points_removes_short_text():
    raw = [{"text": "Short", "type": "claim"}, {"text": "This is a valid key point", "type": "data"}]
    result = _validate_key_points(raw)
    assert len(result) == 1
    assert result[0]["text"] == "This is a valid key point"


def test_validate_key_points_coerces_bad_type():
    raw = [{"text": "Some valid assertion about AI", "type": "opinion"}]
    result = _validate_key_points(raw)
    assert result[0]["type"] == "claim"


def test_validate_key_points_returns_sentinel_when_all_filtered():
    raw = [{"text": "Hi", "type": "claim"}, {"text": "", "type": "data"}]
    result = _validate_key_points(raw)
    assert len(result) == 1
    assert result[0]["text"] == "(no structured key points)"


def test_validate_key_points_caps_at_five():
    raw = [{"text": f"Key point number {i} is long enough", "type": "claim"} for i in range(8)]
    result = _validate_key_points(raw)
    assert len(result) == 5


def test_validate_key_points_non_list_returns_sentinel():
    result = _validate_key_points("not a list")
    assert result[0]["text"] == "(no structured key points)"


def test_validate_key_points_non_dict_items_skipped():
    raw = ["string item", {"text": "Valid key point assertion", "type": "claim"}, 42]
    result = _validate_key_points(raw)
    assert len(result) == 1
    assert result[0]["text"] == "Valid key point assertion"


def test_parse_classification_validates_key_points():
    payload = {
        "source_type": "expert",
        "key_points": [
            {"text": "Valid point about markets", "type": "unknown_type"},
            {"text": "Short", "type": "claim"},
        ],
    }
    result = parse_classification(json.dumps(payload))
    assert len(result["key_points"]) == 1
    assert result["key_points"][0]["type"] == "claim"


# ---------------------------------------------------------------------------
# Weak key points detection
# ---------------------------------------------------------------------------

def test_is_weak_key_points_true_for_sentinel():
    sentinel = [{"text": "(no structured key points)", "type": "claim"}]
    assert is_weak_key_points(sentinel) is True


def test_is_weak_key_points_true_for_empty():
    assert is_weak_key_points([]) is True


def test_is_weak_key_points_true_for_all_short():
    kps = [{"text": "Short text", "type": "claim"}, {"text": "Also short", "type": "data"}]
    assert is_weak_key_points(kps) is True


def test_is_weak_key_points_false_for_good_points():
    kps = [
        {"text": "AI infrastructure spending is accelerating", "type": "data"},
        {"text": "Cloud costs will decrease by 30% in 2026", "type": "prediction"},
    ]
    assert is_weak_key_points(kps) is False
