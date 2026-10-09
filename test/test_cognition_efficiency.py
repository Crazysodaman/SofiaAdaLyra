"""Batch 10 efficiency contracts: bounded projections, DB access and budgets."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread

from sofia.cognition.budgets import model_token_budget
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveRole
from sofia.cognition.performance import efficiency_snapshot
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.model import ProviderConfiguration
from sofia.runtime.hot_state import HotState, HotStateEntry
from sofia.state.sqlite_access import shared_sqlite_access


NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


def test_dynamic_budget_is_complexity_aware_and_configuration_bounded():
    fast = model_token_budget(
        "fast", configured_context=20000, configured_output=5000,
    )
    deep = model_token_budget(
        "deep", configured_context=20000, configured_output=5000,
    )
    constrained = model_token_budget(
        "verify", configured_context=3000, configured_output=500,
    )

    assert fast.context_tokens < deep.context_tokens
    assert fast.output_tokens < deep.output_tokens
    assert constrained.context_tokens == 3000
    assert constrained.output_tokens == 500


def test_ollama_uses_route_budget_in_actual_generation_options():
    provider = OllamaProvider(ProviderConfiguration(
        provider="ollama", model="test", context_size=20000,
        max_output_tokens=5000,
    ))
    request = CognitiveRequest(
        messages=(CognitiveMessage(CognitiveRole.USER, "hello"),),
        route_hint="fast",
    )

    options = provider._build_generation_options(request=request)
    assert options["num_ctx"] == 2048
    assert options["num_predict"] == 384


def test_hot_state_requires_monotonic_revision_expires_and_counts_hits():
    state = HotState(capacity=2)
    entry = HotStateEntry(
        value={"status": "ready"}, revision=2, observed_at=NOW,
        expires_at=NOW + timedelta(seconds=10), source="runtime:test",
    )
    assert state.publish("runtime", entry)
    assert state.get("runtime", now=NOW) == entry
    assert not state.publish("runtime", HotStateEntry(
        value={"status": "old"}, revision=1, observed_at=NOW,
        expires_at=NOW + timedelta(seconds=10), source="runtime:test",
    ))
    assert state.get("runtime", now=NOW + timedelta(seconds=11)) is None
    assert state.stats().hits == 1
    assert state.stats().misses == 1
    assert state.stats().expirations == 1


def test_hot_state_publication_wakes_event_waiter():
    state = HotState()
    observed: list[int] = []
    waiter = Thread(target=lambda: observed.append(
        state.wait_for_change(0, timeout=2)
    ))
    waiter.start()
    state.publish("key", HotStateEntry(
        value="value", revision=1, observed_at=NOW,
        expires_at=NOW + timedelta(seconds=30), source="test:event",
    ))
    waiter.join(timeout=2)
    assert observed == [1]


def test_shared_sqlite_access_enables_wal_verifies_indexes_and_counts(tmp_path: Path):
    access = shared_sqlite_access(tmp_path / "sofia.db")
    assert access is shared_sqlite_access(tmp_path / "sofia.db")
    before = efficiency_snapshot()
    with closing(access.connect()) as db, db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        db.execute("CREATE TABLE item(id INTEGER PRIMARY KEY, value TEXT)")
        db.execute("CREATE INDEX idx_item_value ON item(value)")
        db.executemany("INSERT INTO item(value) VALUES (?)", (("a",), ("b",)))
        assert db.execute("SELECT count(*) FROM item").fetchone()[0] == 2
    metrics = access.metrics()
    after = efficiency_snapshot()

    assert metrics.connections == 1
    assert metrics.queries >= 8
    assert metrics.writes >= 3
    assert access.verify_indexes("idx_item_value") == ()
    assert access.verify_indexes("idx_missing") == ("idx_missing",)
    assert after.sqlite_queries > before.sqlite_queries


def test_long_quality_repair_bounds_dialogue_but_preserves_system_grounding():
    from sofia.cognition.quality_repair import build_rephrase_request

    system = CognitiveMessage(CognitiveRole.SYSTEM, "grounding")
    dialogue = tuple(
        CognitiveMessage(
            CognitiveRole.USER if index % 2 == 0 else CognitiveRole.ASSISTANT,
            f"message {index}",
        )
        for index in range(21)
    )
    request = CognitiveRequest(messages=(system, *dialogue))
    repair = build_rephrase_request(request, issue="near_duplicate")

    assert repair.messages[0] == system
    assert repair.messages[-1] == request.messages[-1]
    assert len(repair.messages) == 11  # system + 8 dialogue + repair + latest
    assert repair.tools == () and repair.allow_tools is False
