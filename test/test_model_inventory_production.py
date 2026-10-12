"""Observed Ollama model catalog, source-only regression fixtures."""
from datetime import datetime, timezone, timedelta
from pathlib import Path

from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite
import pytest

from sofia.cognition.model_inventory import (
    ModelInventoryStore, collect_local_model_inventory,
)
from sofia.config.cognitive_models import CognitiveModelSelection
from sofia.config.model import ProviderConfiguration
from sofia.config.user_settings import RuntimeUserSettingsStore

pytestmark = pytest.mark.pkg_core
NOW = datetime(2026, 10, 11, tzinfo=timezone.utc)


def _trusted_test_state(tmp_path):
    """Explicit first-install test setup for canonical model inventory reads."""
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    seed = Path(__file__).resolve().parents[1] / "src" / "sofia"
    protected = tmp_path / "protected"
    protected.mkdir(exist_ok=True)
    for dest, source in (
        ("constitution.md", seed / "constitution" / "constitution.md"),
        ("constitution.sha256", seed / "constitution" / "constitution.sha256"),
        ("identity.json", seed / "identity" / "identity.json"),
    ):
        (protected / dest).write_bytes(source.read_bytes())
    return state


class LocalOllama:
    def __init__(self):
        self.calls = []
        self.fail_details = False

    def models(self):
        self.calls.append("tags")
        return {"models": [
            {"name": "primary:stable", "digest": "a" * 64,
             "size": 3_000_000_000,
             "details": {"quantization_level": "Q4_K_M"}},
            {"name": "orphan:old", "digest": "b" * 64,
             "size": 120_000_000},
        ]}

    def version(self):
        self.calls.append("version")
        return {"version": "0.12.0"}

    def show(self, name):
        self.calls.append("show:" + name)
        if self.fail_details:
            raise OSError("Ollama show temporarily unavailable")
        return {
            "capabilities": ["vision", "tools", "completion"],
            "model_info": {"synthetic.context_length": 8192},
            "license": "owner must review this license, not auto-accept it",
        }

    def pull(self, *_a, **_kw):
        pytest.fail("Read-only discovery must never pull a model")

    def load(self, *_a, **_kw):
        pytest.fail("Read-only discovery must never load a model")


def selection():
    return CognitiveModelSelection(
        routing_enabled=True,
        primary=ProviderConfiguration("ollama", "primary:stable"),
        secondary=ProviderConfiguration("ollama", "secondary:missing"),
    )


def test_inventory_uses_actual_tags_and_show_without_inference():
    adapter = LocalOllama()
    records = collect_local_model_inventory(
        selection=selection(), backend=adapter,
        host_id="venus", at=NOW,
    )
    assert [item.model for item in records] == [
        "orphan:old", "primary:stable", "secondary:missing",
    ]
    primary = next(item for item in records if item.model == "primary:stable")
    assert primary.installed is True
    assert primary.configured_roles == ("primary",)
    assert primary.digest == "a" * 64
    assert primary.size_bytes == 3_000_000_000
    assert primary.quantization == "Q4_K_M"
    assert primary.advertised_context_length == 8192
    assert primary.advertised_capabilities == (
        "completion", "tools", "vision",
    )
    assert primary.license_sha256 is not None
    missing = next(item for item in records if item.model == "secondary:missing")
    assert missing.installed is False
    assert missing.digest is None
    assert missing.advertised_capabilities == ()
    assert adapter.calls == [
        "tags", "version", "show:orphan:old", "show:primary:stable",
    ]


def test_partial_show_failure_retains_unknowns_not_fabricated_capability():
    adapter = LocalOllama()
    adapter.fail_details = True
    records = collect_local_model_inventory(
        selection=selection(), backend=adapter,
        host_id="venus", at=NOW,
    )
    installed = next(item for item in records if item.model == "primary:stable")
    assert installed.installed is True
    assert installed.advertised_capabilities == ()
    assert installed.details_error == "OSError"


def test_canonical_inventory_store_replaces_one_host_atomically(tmp_path):
    path = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    RuntimeUserSettingsStore(path).save(
        RuntimeUserSettingsStore(path).load()
    )
    store = ModelInventoryStore(path)
    records = collect_local_model_inventory(
        selection=selection(), backend=LocalOllama(),
        host_id="venus", at=NOW,
    )
    store.replace_host(host_id="venus", observations=records)
    read = store.readable(host_id="venus")
    assert "primary:stable" in read
    assert "secondary:missing" in read
    assert "ADVERTISED" in read
    assert "NOT VERIFIED" in read
    assert "terms require human review" in read
    observed_terms = store.license_text(host_id="venus", model="primary:stable")
    assert "owner must review this license" in observed_terms
    assert "not accepted by discovery" in observed_terms
    assert "SHA-256:" in observed_terms
    assert "No observed license" in store.license_text(
        host_id="venus", model="unknown:model",
    )
    assert store.readable(host_id="artemis").startswith("No successful")
    with pytest.raises(ValueError, match="observed host"):
        store.replace_host(host_id="artemis", observations=records)
    assert "primary:stable" in store.readable(host_id="venus")


def test_malformed_or_unbounded_tag_inventory_never_claims_empty_machine():
    adapter = LocalOllama()
    adapter.models = lambda: {"models": [1]}
    with pytest.raises(ValueError, match="invalid model metadata"):
        collect_local_model_inventory(
            selection=selection(), backend=adapter,
            host_id="venus", at=NOW,
        )
    adapter.models = lambda: {"models": [{}] * 65}
    with pytest.raises(ValueError, match="64-model bound"):
        collect_local_model_inventory(
            selection=selection(), backend=adapter,
            host_id="venus", at=NOW,
        )


def test_run_owned_readonly_discovery_uses_reviewed_local_ollama_roles(
    tmp_path, monkeypatch,
):
    from sofia.config.user_settings import RuntimeUserSettings
    from sofia.cognition.model_inventory import refresh_local_model_inventory
    state=_trusted_test_state(tmp_path)
    RuntimeUserSettingsStore(state).save(
        RuntimeUserSettings(
            cognitive_primary_model="primary:stable",
            cognitive_secondary_model="secondary:missing",
        )
    )
    adapter=LocalOllama()
    rows=refresh_local_model_inventory(
        state_path=state,host_id="venus",at=NOW,
        details_limit=1,backend=adapter,
    )
    assert len(rows)==3
    # The only metadata /show goes to the configured primary, not to an
    # unreviewed installed candidate that happens to sort first.
    assert adapter.calls == ["tags","version","show:primary:stable"]
    secondary=next(row for row in rows if row.model=="secondary:missing")
    assert secondary.installed is False
    unconfigured=next(row for row in rows if row.model=="orphan:old")
    assert unconfigured.details_error=="details_deferred_budget"
    candidates=ModelInventoryStore(state).candidate_review(host_id="venus", at=NOW)
    assert "orphan:old" in candidates
    assert "primary:stable" not in candidates
    assert "suitability=unverified" in candidates


def test_failed_unattended_scan_keeps_prior_confirmed_inventory(tmp_path):
    from sofia.config.user_settings import RuntimeUserSettings
    from sofia.cognition.model_inventory import refresh_local_model_inventory
    state=_trusted_test_state(tmp_path)
    RuntimeUserSettingsStore(state).save(
        RuntimeUserSettings(
            cognitive_primary_model="primary:stable",
            cognitive_secondary_model="secondary:missing",
        )
    )
    refresh_local_model_inventory(
        state_path=state,host_id="venus",at=NOW,
        details_limit=1,backend=LocalOllama(),
    )
    backend=LocalOllama()
    def offline():
        raise ConnectionError("local Ollama is unavailable")
    backend.models=offline
    with pytest.raises(ConnectionError):
        refresh_local_model_inventory(
            state_path=state,host_id="venus",at=NOW,
            details_limit=1,backend=backend,
        )
    assert "primary:stable" in ModelInventoryStore(state).readable(
        host_id="venus",
    )


def test_unreviewed_model_never_gets_a_rank_or_role_from_discovery(tmp_path):
    from sofia.config.user_settings import RuntimeUserSettings
    from sofia.cognition.model_inventory import refresh_local_model_inventory
    state=_trusted_test_state(tmp_path)
    RuntimeUserSettingsStore(state).save(
        RuntimeUserSettings(
            cognitive_primary_model="primary:stable",
            cognitive_secondary_model="secondary:missing",
        )
    )
    refresh_local_model_inventory(
        state_path=state,host_id="venus",at=NOW,
        details_limit=0,backend=LocalOllama(),
    )
    decision=ModelInventoryStore(state).candidate_review(host_id="venus", at=NOW)
    assert "DISCOVERY ONLY" in decision
    assert "license" in decision
    assert "unverified" in decision
    assert "switch" not in decision.casefold()


def test_old_or_future_inventory_does_not_offer_models_for_current_role_review(
    tmp_path,
):
    from sofia.config.user_settings import RuntimeUserSettings
    from sofia.cognition.model_inventory import refresh_local_model_inventory
    state=_trusted_test_state(tmp_path)
    RuntimeUserSettingsStore(state).save(RuntimeUserSettings(
        cognitive_primary_model="primary:stable",
        cognitive_secondary_model="secondary:missing",
    ))
    refresh_local_model_inventory(
        state_path=state,host_id="venus",at=NOW,
        backend=LocalOllama(),details_limit=0,
    )
    store=ModelInventoryStore(state)
    assert "orphan:old" in store.candidate_review(host_id="venus",at=NOW)
    later=store.candidate_review(
        host_id="venus",at=NOW+timedelta(minutes=16),
    )
    assert "No FRESH" in later
    assert "Stale/invalid observations: 3" in later
    before=store.candidate_review(
        host_id="venus",at=NOW-timedelta(seconds=1),
    )
    assert "No FRESH" in before
    # Historical facts remain visible for diagnosis, never repurposed as
    # a verified current install or a reason to pull/switch models.
    assert "orphan:old" in store.readable(host_id="venus")
    with pytest.raises(ValueError,match="aware"):
        store.candidate_review(
            host_id="venus",at=NOW.replace(tzinfo=None),
        )


def test_model_without_content_address_is_only_historical_inventory(tmp_path):
    from sofia.config.user_settings import RuntimeUserSettings
    from sofia.cognition.model_inventory import refresh_local_model_inventory
    state=_trusted_test_state(tmp_path)
    RuntimeUserSettingsStore(state).save(RuntimeUserSettings(
        cognitive_primary_model="primary:stable",
        cognitive_secondary_model="secondary:missing",
    ))
    adapter=LocalOllama()
    real_tags=adapter.models
    def malformed_digest_tags():
        payload=real_tags()
        payload["models"][1]["digest"]="not-a-sha256"
        return payload
    adapter.models=malformed_digest_tags
    result=refresh_local_model_inventory(
        state_path=state,host_id="venus",at=NOW,
        details_limit=0,backend=adapter,
    )
    orphan=next(row for row in result if row.model=="orphan:old")
    assert orphan.installed is True
    assert orphan.digest is None
    store=ModelInventoryStore(state)
    candidate=store.candidate_review(host_id="venus",at=NOW)
    assert "No FRESH" in candidate
    assert "without SHA-256 identity: 1" in candidate
    assert "orphan:old" in store.readable(host_id="venus")


def test_out_of_order_inventory_scan_cannot_rewind_host_snapshot(tmp_path):
    from sofia.config.user_settings import RuntimeUserSettings
    from sofia.cognition.model_inventory import refresh_local_model_inventory
    state=_trusted_test_state(tmp_path)
    RuntimeUserSettingsStore(state).save(RuntimeUserSettings(
        cognitive_primary_model="primary:stable",
        cognitive_secondary_model="secondary:missing",
    ))
    first=collect_local_model_inventory(
        selection=selection(),backend=LocalOllama(),
        host_id="venus",at=NOW,
    )
    newer=collect_local_model_inventory(
        selection=selection(),backend=LocalOllama(),
        host_id="venus",at=NOW+timedelta(seconds=30),
    )
    store=ModelInventoryStore(state)
    store.replace_host(host_id="venus",observations=newer)
    with pytest.raises(RuntimeError,match="stale model inventory"):
        store.replace_host(host_id="venus",observations=first)
    assert "orphan:old" in store.candidate_review(
        host_id="venus",at=NOW+timedelta(seconds=30),
    )
    assert (NOW+timedelta(seconds=30)).isoformat() in store.readable(host_id="venus")


def test_inconsistent_inventory_snapshot_cannot_publish(tmp_path):
    from dataclasses import replace
    state=_trusted_test_state(tmp_path)
    RuntimeUserSettingsStore(state).load()
    store=ModelInventoryStore(state)
    observations=collect_local_model_inventory(
        selection=selection(),backend=LocalOllama(),
        host_id="venus",at=NOW,
    )
    with pytest.raises(ValueError,match="one observed snapshot"):
        store.replace_host(
            host_id="venus",
            observations=(observations[0],replace(
                observations[1],observed_at=NOW+timedelta(seconds=1),
            )),
        )
    with pytest.raises(ValueError,match="duplicate observed model"):
        store.replace_host(
            host_id="venus",observations=(observations[0],observations[0]),
        )
    with pytest.raises(ValueError,match="nonempty"):
        store.replace_host(host_id="venus",observations=())
    assert store.readable(host_id="venus").startswith("No successful")
