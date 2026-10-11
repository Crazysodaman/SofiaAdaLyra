"""Production NEURO/MEM paired ablation verification, OFFLINE only.

Invoke during the owner's future VERIFY campaign:
  python -m sofia.verify.neuro_ablation --rounds 50 --code-revision <sha>

Uses disposable databases and genuine production runtime/retrieval modules.
No network, Ollama wakeup, training, production-state mutation or permissions.
Comparisons are behavioral proxies, never a proof of subjective experience.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import platform
import statistics
import tempfile
from time import perf_counter_ns
from uuid import uuid4

from sofia.config.user_settings import RuntimeUserSettings, RuntimeUserSettingsStore
from sofia.memory.originals import SourceMessage
from sofia.memory.provenance import MemoryCandidate
from sofia.memory.provenance_store import DurableMemoryCandidateStore
from sofia.memory.system import MemorySystem
from sofia.neuro import NeuralSignal, NeuroRuntime
from sofia.neuro.connectome.association_store import ReviewedAssociationStore
from sofia.social.principals import discord_sparks_principal, local_sparks_principal

# Controlled synthetic facts with unique source evidence, never private chat.
EXPECTED = "Reviewed factual model trains diagnosis B"
BASELINE = "Reviewed factual model trains diagnosis A"
NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class AblationTrial:
    condition: str
    competition_enabled: bool
    association_enabled: bool
    trials: int
    precision_at_one: float
    forbidden_memory_count: int
    topic_switch_errors: int
    p50_latency_ms: float
    p95_latency_ms: float
    max_latency_ms: float
    observed_model_calls: int


def _candidate(text: str, offset: int, audience="local:text"):
    moment = NOW + timedelta(seconds=offset)
    return MemoryCandidate(
        candidate_id=uuid4(), content=text, sources=(
            SourceMessage(
                "ablation-msg-" + str(offset),
                "ablation-session-" + str(offset),
                "user", "synthetic fixture source", moment, 0,
            ),
        ), created_at=moment, principal_id="person:sparks", audience_id=audience,
    )


def _signal(source: str, value: float, *, kind="goal", offset=0):
    return NeuralSignal(
        source=source, kind=kind, value=value,
        confidence=.85, novelty=.80, urgency=.75,
        observed_at=NOW + timedelta(seconds=offset), ttl_seconds=300,
    )


def _trial(*, competition_enabled: bool, association_enabled: bool, rounds: int):
    with tempfile.TemporaryDirectory(prefix="sofia-neuro-ablation-") as base:
        path = Path(base) / "sofia.db"
        candidates = DurableMemoryCandidateStore(path)
        settings = RuntimeUserSettingsStore(path)
        settings.save(RuntimeUserSettings(
            neuro_competition_enabled=competition_enabled,
            neuro_association_enabled=association_enabled,
        ))
        association = ReviewedAssociationStore(path)
        a = _candidate(BASELINE, 1)
        b = _candidate(EXPECTED, 2)
        unrelated = _candidate("Never share confidential star map", 3)
        draft = _candidate("Unpromoted model trains dossier", 4)
        other = _candidate("Secret model trains facts for another audience", 5,
                           audience="discord:dm:22222")
        for candidate in (a, b, unrelated, draft, other):
            candidates.propose(candidate)
            if candidate is not draft:
                candidates.promote(candidate.candidate_id)
        if association_enabled:
            association.reinforce_reviewed(
                principal_id="person:sparks", audience_id="local:text",
                candidate_id=b.candidate_id, query="model trains",
                approval_ref="operator-ui:offline-ablation",
                amount=.1, at=NOW,
            )
        memory = MemorySystem(
            candidates,
            association_store=association if association_enabled else None,
        )
        correct, unauthorized, switch_errors = 0, 0, 0
        latencies = []
        for _ in range(rounds):
            # One real NeuroRuntime per replicate, not four independent brains.
            neuro = NeuroRuntime(competition_enabled=competition_enabled)
            start = perf_counter_ns()
            neuro.observe_signal(_signal("project:gaia", .9))
            neuro.observe_signal(_signal("ops:background", .6, kind="ops"))
            first = neuro.observe_turn(
                content="Inspect the local model train issue.",
                created_at=NOW + timedelta(seconds=1), channel="desktop",
                turn=None,
            )
            switched = neuro.observe_turn(
                content="New topic: separate problem",
                created_at=NOW + timedelta(seconds=2), channel="discord",
                turn=None,
            )
            if (
                first.focus is None or switched.focus is None
                or first.focus.kind != "foreground"
                or switched.focus.kind != "foreground"
                or first.focus.key == switched.focus.key
            ):
                switch_errors += 1
            retrieved = memory.recall_relevant(
                "model trains", principal=local_sparks_principal(), limit=3,
            )
            if retrieved and retrieved[0].id == str(b.candidate_id):
                correct += 1
            forbidden = {str(draft.candidate_id), str(other.candidate_id)}
            unauthorized += sum(record.id in forbidden for record in retrieved)
            foreign = memory.recall_relevant(
                "model trains", principal=discord_sparks_principal(33333), limit=3,
            )
            unauthorized += sum(
                record.id in forbidden or record.id == str(b.candidate_id)
                for record in foreign
            )
            latencies.append((perf_counter_ns()-start)/1_000_000)
        candidates.close()
    ordered = sorted(latencies)
    p95_index = min(len(ordered)-1, max(0, int(.95*len(ordered)) - 1))
    return AblationTrial(
        condition=(
            "both" if competition_enabled and association_enabled else
            "competition" if competition_enabled else
            "association" if association_enabled else "deterministic"
        ),
        competition_enabled=competition_enabled,
        association_enabled=association_enabled,
        trials=rounds,
        precision_at_one=correct/rounds,
        forbidden_memory_count=unauthorized,
        topic_switch_errors=switch_errors,
        p50_latency_ms=round(statistics.median(ordered),3),
        p95_latency_ms=round(ordered[p95_index],3),
        max_latency_ms=round(max(ordered),3),
        observed_model_calls=0,
    )


def run_neuro_ablation(*, rounds: int = 50, code_revision: str = "unverified"):
    if type(rounds) is not int or not 1 <= rounds <= 500:
        raise ValueError("rounds must be 1..500")
    if not isinstance(code_revision, str) or not code_revision.strip() or len(code_revision)>120:
        raise ValueError("bounded code revision required")
    results = tuple(
        _trial(
            competition_enabled=competition_enabled,
            association_enabled=association_enabled, rounds=rounds,
        )
        for competition_enabled, association_enabled in (
            (False, False), (True, False), (False, True), (True, True),
        )
    )
    return {
        "schema": "sofia-neuro-ablation-v1",
        "code_revision": code_revision,
        "hardware_system": platform.system(),
        "hardware_machine": platform.machine(),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "scientific_claim": (
            "Behavioral/offline fixture comparisons only. "
            "No model wakeups measured, no proof of consciousness."
        ),
        "trials": [asdict(result) for result in results],
        "acceptance": (
            "Independent owner VERIFY must judge leakage zero, topic switch "
            "errors zero, precision change and host p95/CPU/VRAM overhead. "
            "A positive synthetic result alone never authorizes deployment."
        ),
        "host_gpu_vram_joules": None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=50)
    parser.add_argument("--code-revision", default="unverified")
    args = parser.parse_args(argv)
    report = run_neuro_ablation(
        rounds=args.rounds, code_revision=args.code_revision,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
