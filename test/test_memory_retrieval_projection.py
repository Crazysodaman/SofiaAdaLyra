"""Offline selection checks, not durable memory or per-user authentication."""
from datetime import datetime, timezone

import pytest
from sofia.conversation.model import ConversationMessage, ConversationRole
from sofia.memory.retrieval_projection import project_originals

T = datetime(2026, 9, 21, tzinfo=timezone.utc)


def msg(mid, session="a", content="hello", when=T):
    return ConversationMessage(id=mid, session_id=session, role=ConversationRole.USER, content=content, created_at=when)


def select(messages, ids, budget=99, session="a"):
    return project_originals(session_id=session, originals=messages, requested_ids=ids, budget_characters=budget)


def test_exact_original_text_and_provenance():
    original = msg("1", content="  exact  ")
    result = select([original], ["1"])
    assert result.selected[0].content == "  exact  "
    assert (result.selected[0].session_id, result.selected[0].message_id, result.selected[0].position) == ("a", "1", 0)


def test_does_not_leak_other_session_or_existence():
    result = select([msg("secret", "b"), msg("public")], ["secret", "unknown", "public"])
    assert [m.message_id for m in result.selected] == ["public"]
    assert result.missing_ids == ("secret", "unknown")


def test_requested_order_and_deduplication():
    result = select([msg("1"), msg("2")], ["2", "2", "1"])
    assert [m.message_id for m in result.selected] == ["2", "1"]


def test_budget_omits_without_truncation():
    result = select([msg("1", content="abcd"), msg("2", content="efg")], ["1", "2"], 6)
    assert [m.content for m in result.selected] == ["abcd"]
    assert result.omitted_ids == ("2",)


def test_larger_later_item_does_not_block_shorter_one():
    result = select([msg("1", content="12345"), msg("2", content="a")], ["1", "2"], 1)
    assert result.omitted_ids == ("1",)
    assert result.selected[0].message_id == "2"


def test_zero_budget_records_omission():
    assert select([msg("1")], ["1"], 0).omitted_ids == ("1",)

@pytest.mark.parametrize("bad", [-1, 0.5, True, "100", None])
def test_bad_budgets(bad):
    with pytest.raises(ValueError):
        select([msg("1")], ["1"], bad)

@pytest.mark.parametrize("bad", ["", " ", None, 1])
def test_bad_session(bad):
    with pytest.raises(ValueError):
        select([msg("1")], ["1"], session=bad)

@pytest.mark.parametrize("bad", ["", " ", None, 0])
def test_bad_requested_id(bad):
    with pytest.raises(ValueError):
        select([msg("1")], [bad])


def test_bad_original_type():
    with pytest.raises(TypeError):
        select([object()], ["1"])


def test_duplicate_original_ids_fail_closed():
    with pytest.raises(ValueError):
        select([msg("1"), msg("1")], ["1"])


def test_naive_original_timestamp_fails_closed():
    with pytest.raises(ValueError):
        select([msg("1", when=datetime(2026, 1, 1))], ["1"])


def test_no_originals_no_fabricated_memory():
    result = select([], ["imagined"])
    assert result.selected == () and result.missing_ids == ("imagined",)
