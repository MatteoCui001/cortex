"""Tests for parse_user_stance (pattern-based stance detection)."""

import pytest

from cortex.domain.stance import parse_user_stance

# ---------------------------------------------------------------------------
# Chinese patterns
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["有道理", "认同", "同意", "对的", "是的", "没错", "赞同"])
def test_chinese_agree_patterns(text):
    assert parse_user_stance(text) == "agree"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("不对", "disagree"),
        ("扯淡", "disagree"),
        ("不认同", "disagree"),
        ("不同意", "disagree"),
        ("错", "disagree"),
        ("胡说", "disagree"),
        ("瞎说", "disagree"),
    ],
)
def test_chinese_disagree_patterns(text, expected):
    assert parse_user_stance(text) == expected


@pytest.mark.parametrize("text", ["存疑", "不确定", "留着看看", "待验证", "有待观察", "再看看"])
def test_chinese_uncertain_patterns(text):
    assert parse_user_stance(text) == "uncertain"


@pytest.mark.parametrize("text", ["跳过", "不关注", "无所谓", "略过"])
def test_chinese_skip_patterns(text):
    assert parse_user_stance(text) == "skip"


# ---------------------------------------------------------------------------
# English patterns
# ---------------------------------------------------------------------------


def test_english_agree():
    assert parse_user_stance("agree") == "agree"


def test_english_agree_makes_sense():
    assert parse_user_stance("makes sense") == "agree"


def test_english_agree_correct():
    assert parse_user_stance("correct") == "agree"


def test_english_agree_good_point():
    assert parse_user_stance("good point") == "agree"


def test_english_disagree():
    assert parse_user_stance("disagree") == "disagree"


def test_english_disagree_wrong():
    assert parse_user_stance("wrong") == "disagree"


def test_english_disagree_nonsense():
    assert parse_user_stance("nonsense") == "disagree"


def test_english_uncertain():
    assert parse_user_stance("uncertain") == "uncertain"


def test_english_uncertain_maybe():
    assert parse_user_stance("maybe") == "uncertain"


def test_english_uncertain_not_sure():
    assert parse_user_stance("not sure") == "uncertain"


def test_english_skip():
    assert parse_user_stance("skip") == "skip"


def test_english_skip_pass():
    assert parse_user_stance("pass") == "skip"


def test_english_skip_not_relevant():
    assert parse_user_stance("not relevant") == "skip"


# ---------------------------------------------------------------------------
# Case insensitivity
# ---------------------------------------------------------------------------


def test_uppercase_agree():
    assert parse_user_stance("AGREE") == "agree"


def test_mixed_case_disagree():
    assert parse_user_stance("Disagree") == "disagree"


# ---------------------------------------------------------------------------
# Edge cases — should return None
# ---------------------------------------------------------------------------


def test_empty_string_returns_none():
    assert parse_user_stance("") is None


def test_random_text_returns_none():
    assert parse_user_stance("the quick brown fox") is None


def test_whitespace_only_returns_none():
    assert parse_user_stance("   ") is None


def test_unrelated_chinese_returns_none():
    assert parse_user_stance("今天天气很好") is None
