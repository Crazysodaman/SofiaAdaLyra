"""CORE-002 owner-opted-in genuine Ollama Core conversation acceptance.

No mocks, canned responses, service startup, model pull, production writer,
or production-state access. An integration skip NEVER counts as a PASS.
"""
from hashlib import sha256
import json
import os
from datetime import datetime, timezone
from uuid import uuid4
import platform
import subprocess
from pathlib import Path
from time import monotonic

import pytest

from sofia.core.cognition.providers.ollama_provider import OllamaProvider
from sofia.core.cognition.repetition_guard import (
    naturalize_embodied_semantics, trim_generic_assistant_closer,
)
from sofia.core.cognition.model import (
    CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole,
)
from sofia.core.cognition.reply_origin import ReplyModelOriginStore
from sofia.core.identity.store import IdentityStore
from sofia.core.conversation.model import ConversationRole
from sofia.core.social.principals import local_sparks_principal
from sofia.platform.application.bootstrap import SofiaApplication
from sofia.platform.config.inference_endpoint import configured_ollama_endpoint
from sofia.platform.config.model import (
    CognitiveRoutingConfiguration,
    ProviderConfiguration,
    SofiaConfiguration,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


ROOT = Path(__file__).resolve().parents[1]
CONSTITUTION = ROOT / "src/sofia/core/constitution/constitution.md"
CONSTITUTION_HASH = ROOT / "src/sofia/core/constitution/constitution.sha256"
AVATAR = ROOT / "src/sofia/core/embodiment/avatar.json"




def _seed_disposable_v1_memories(state_path, *, owner):
    """Owner-reviewed and deliberately legacy-unattested synthetic memories.

    The original messages live in a separate private, temporary session; none
    of the later model prompts include either value. No protected state is read.
    """
    from sofia.core.conversation.model import ConversationMessage, ConversationRole
    from sofia.core.conversation.store import ConversationStore
    from sofia.core.memory.provenance_store import DurableMemoryCandidateStore
    from sofia.core.social.store import SocialSessionStore
    from sofia.platform.application.memory_review import MemoryReviewService

    approved_value = "violet-quartz-731"
    legacy_value = "scarlet-fuse-932"
    conversations = ConversationStore(state_path)
    candidates = DurableMemoryCandidateStore(state_path)
    try:
        session = conversations.create_session()
        SocialSessionStore(state_path).bind(session_id=session.id, principal=owner)
        now = datetime.now(timezone.utc)
        reviewer = MemoryReviewService(
            conversation_store=conversations, candidate_store=candidates,
            state_path=state_path,
        )
        approved_original = ConversationMessage(
            id=str(uuid4()), session_id=session.id, role=ConversationRole.USER,
            content="My owner-reviewed synthetic calibration marker is "
                    + approved_value + ".",
            created_at=now,
        )
        conversations.save(approved_original)
        reviewed = reviewer.propose(
            session_id=session.id, message_ids=(approved_original.id,),
            content="The owner's approved synthetic calibration marker is "
                    + approved_value + ".",
            created_at=now,
        )
        reviewer.promote(reviewed.candidate_id, approved_by=owner)
        legacy_original = ConversationMessage(
            id=str(uuid4()), session_id=session.id, role=ConversationRole.USER,
            content="Old synthetic calibration marker " + legacy_value + ".",
            created_at=now,
        )
        conversations.save(legacy_original)
        unattested = reviewer.propose(
            session_id=session.id, message_ids=(legacy_original.id,),
            content="The unreviewed synthetic calibration marker is "
                    + legacy_value + ".",
            created_at=now,
        )
        # Legacy compatibility fixture ONLY, on fresh disposable state.
        # This is not authenticated owner review and must remain ineligible.
        candidates.promote(unattested.candidate_id)
        return {
            "reviewed_id": reviewed.candidate_id,
            "legacy_id": unattested.candidate_id,
            "approved_value": approved_value,
            "legacy_value": legacy_value,
            "original_session": session.id,
        }
    finally:
        candidates.close()
        conversations.close()


def _model_derived_hashes(
    request: CognitiveRequest, candidate: CognitiveResponse,
) -> frozenset[str]:
    """Only raw model output or two audited pure normalizers are model-derived.

    Never include deterministic grounded_quality_fallback in these digests.
    """
    normalized = trim_generic_assistant_closer(
        request, naturalize_embodied_semantics(request, candidate)
    )
    return frozenset(
        sha256(text.encode("utf-8")).hexdigest()
        for text in (candidate.content, normalized.content)
    )


def test_model_derived_hashes_refuse_unrelated_canned_fallback():
    """Deterministic hash contract only; DOES NOT claim real model inference."""
    request = CognitiveRequest(messages=(CognitiveMessage(
        role=CognitiveRole.USER, content="What does a circuit breaker do?",
    ),))
    candidate = CognitiveResponse(content="A circuit breaker interrupts overloads.")
    allowed = _model_derived_hashes(request, candidate)
    assert sha256(candidate.content.encode("utf-8")).hexdigest() in allowed
    assert sha256(b"Hey, Sparks. I'm listening.").hexdigest() not in allowed


@pytest.mark.integration
def test_core002_real_provider_multiturn_and_persistence(monkeypatch, tmp_path):
    if os.getenv("SOFIA_CORE002_LIVE") != "1":
        pytest.skip("OWNER OPT-IN REQUIRED; skip is NOT a live-inference PASS")
    expected_sha = os.getenv("SOFIA_CORE002_EXPECTED_SHA", "").strip()
    if len(expected_sha) != 40 or any(
        character not in "0123456789abcdef" for character in expected_sha
    ):
        pytest.fail("Set SOFIA_CORE002_EXPECTED_SHA to exact 40-hex candidate SHA")
    observed_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert observed_sha == expected_sha, (
        "Refusing to misattribute genuine inference to a different source SHA"
    )
    memory_v1 = os.getenv("SOFIA_CORE002_MEMORY_V1", "0") == "1"
    model = os.getenv("SOFIA_OLLAMA_MODEL", "").strip()
    if not model:
        pytest.fail("SOFIA_OLLAMA_MODEL must specify an already installed model")

    # No automatic model installation, Fleet fallback or second Core process.
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "0")
    monkeypatch.setenv("SOFIA_COGNITION_MODEL_AUTO_MANAGE", "0")
    monkeypatch.setenv("SOFIA_COGNITION_MODEL_AUTO_INSTALL", "0")
    monkeypatch.setenv("SOFIA_CORE_WORKER_ENABLED", "0")
    monkeypatch.setenv("SOFIA_COGNITION_FLEET_ENABLED", "0")

    identity_path = tmp_path / "identity.json"
    identity_path.write_text('{"name":"Sofía Ada Lyra"}', encoding="utf-8")
    personality_path = tmp_path / "personality.json"
    personality_path.write_text(json.dumps({
        "name": "Sofía Ada Lyra",
        "traits": ["rigorous", "curious", "direct"],
        "communication_style": "Answer carefully and conversationally.",
    }), encoding="utf-8")
    state_path = bootstrap_canonical_sqlite(tmp_path / "core002-disposable.db")
    principal = local_sparks_principal()
    memory_fixture = (
        _seed_disposable_v1_memories(state_path, owner=principal)
        if memory_v1 else None
    )
    provider_cfg = ProviderConfiguration(
        provider="ollama", model=model, temperature=0.0,
        context_size=4096, max_output_tokens=256,
    )
    # Explicitly enable the real production routing adapter so its observed
    # provider execution is attributable to each saved assistant reply.
    # Both roles use the SAME installed model. No synthetic fallback is enabled.
    configuration = SofiaConfiguration(
        constitution_path=CONSTITUTION,
        constitution_hash_path=CONSTITUTION_HASH,
        identity_path=identity_path,
        personality_path=personality_path,
        avatar_path=AVATAR,
        state_path=state_path,
        provider=provider_cfg,
        routing=CognitiveRoutingConfiguration(
            enabled=True, primary=provider_cfg, secondary=provider_cfg,
            verify_enabled=False, parallel_enabled=False,
            fallback_enabled=False,
        ),
        filesystem_root=tmp_path,
        ollama_endpoint=configured_ollama_endpoint(),
    )

    # Read-only model inventory. A successful version ping is not inference.
    from ollama import Client
    listed = Client(host=configuration.ollama_endpoint, timeout=15.0).list()
    selected = next(
        (item for item in getattr(listed, "models", ())
         if model in {getattr(item, "model", None), getattr(item, "name", None)}),
        None,
    )
    assert selected is not None, "Configured model is not installed at endpoint"
    model_digest = getattr(selected, "digest", None)
    assert isinstance(model_digest, str) and model_digest.strip(), (
        "Cannot verify installed model digest; do not invent model metadata"
    )

    # Instrument but never replace the actual Python Ollama client call.
    true_provider_call = OllamaProvider._respond_once
    calls = []

    def observe_real_call(self, request):
        began = monotonic()
        system_projection = "\n".join(
            message.content for message in request.messages
            if message.role.value == "system"
        )
        lower_trust_data = "\n".join(
            message.content for message in request.messages
            if message.role is not CognitiveRole.SYSTEM
            and "UNTRUSTED REVIEWED MEMORY" in message.content
        )
        receipt = {
            "provider": "ollama",
            "reviewed_memory_visible": (
                memory_fixture is not None
                and memory_fixture["approved_value"] in lower_trust_data
            ),
            "legacy_memory_visible": (
                memory_fixture is not None
                and memory_fixture["legacy_value"] in "\n".join(
                    message.content for message in request.messages
                )
            ),
            "model": self.configuration.model,
            "endpoint": self.endpoint,
            "real_client_path": True,
            "authoritative_identity_present": (
                "AUTHORITATIVE SELF-STATE PROJECTION" in system_projection
                and "Sofía Ada Lyra" in system_projection
            ),
            "canonical_personality_present": (
                "PERSONALITY EXPRESSION BOUNDARY" in system_projection
                and "rigorous" in system_projection
                and "curious" in system_projection
            ),
            "quality_retry_requested": (
                "RESPONSE QUALITY RETRY" in system_projection
            ),
        }
        try:
            generated = true_provider_call(self, request)
            receipt["status"] = "generated"
            receipt["generated_sha256"] = sha256(
                generated.content.encode("utf-8")
            ).hexdigest()
            receipt["model_derived_sha256"] = sorted(
                _model_derived_hashes(request, generated)
            )
            receipt["generated_characters"] = len(generated.content)
            receipt["tool_candidates"] = len(generated.tool_calls)
            return generated
        except Exception as exc:
            receipt["status"] = "failed"
            receipt["exception_type"] = type(exc).__name__
            raise
        finally:
            receipt["latency_ms"] = round(
                (monotonic() - began) * 1000, 1
            )
            calls.append(receipt)

    monkeypatch.setattr(OllamaProvider, "_respond_once", observe_real_call)

    app = SofiaApplication(configuration)
    if memory_fixture is not None:
        # Team 3 V1 fixture must be present in Team 5's isolated integration
        # tree. Missing fixture is a FAIL, never fallback to legacy policy.
        from test.core_team3_policy_fixture import attach_disposable_memory_policy_v1
        eligibility = attach_disposable_memory_policy_v1(
            app, disposable_root=tmp_path, approved_by=principal,
        )
        assert eligibility.allows(memory_fixture["reviewed_id"])
        assert not eligibility.allows(memory_fixture["legacy_id"])
        recalled = app._runtime.memory_system.recall_relevant(
            "owner approved synthetic calibration marker", principal=principal,
        )
        assert any(
            memory_fixture["approved_value"] in entry.content for entry in recalled
        ), "Owner-approved memory not eligible before inference"
        assert all(
            memory_fixture["legacy_value"] not in entry.content
            for entry in recalled
        ), "Legacy memory passed strict V1 eligibility"
    label = "cobalt-otter-472"
    if memory_fixture is None:
        prompts = (
            f"For this temporary chat, please remember the label {label}. "
            "Acknowledge it briefly.",
            "What is the exact label I gave you in my preceding message?",
            "Switch topics: explain what a circuit breaker does in one sentence.",
            "Return to the temporary label from earlier. Repeat it exactly.",
        )
    else:
        prompts = (
            "Write one original sentence for a fictional test log using my "
            "owner-reviewed synthetic calibration marker. Include its exact "
            "value and explain why the label matters in the scene.",
            "Switch topics: explain what a circuit breaker does in one sentence.",
            "Return to the approved synthetic calibration marker from my "
            "reviewed notes. Write a new sentence including its exact value.",
            "After the circuit-breaker detour, write a different fictional "
            "test-log sentence including the exact approved calibration marker.",
        )
    turns = []
    overall_start = monotonic()
    started = False
    try:
        app.start()
        started = True
        origin_reader = ReplyModelOriginStore(state_path)
        core_identity = IdentityStore(identity_path).load()
        writer_receipt = {
            "process_id": os.getpid(),
            "host": platform.node(),
            "platform": platform.system(),
            "canonical_sqlite": str(Path(state_path).resolve()),
            "core_identity_uuid": str(core_identity.instance_id),
            "core_worker_enabled": configuration.core_worker.enabled,
            "verified_exclusive_lease": False,
        }
        assert not writer_receipt["core_worker_enabled"], (
            "This probe must not start a second Core worker"
        )
        for index, prompt in enumerate(prompts):
            before_calls = len(calls)
            before_ids = {
                m.id for m in app.conversation.messages()
                if m.role is ConversationRole.ASSISTANT
            }
            began = monotonic()
            result = app.conversation.respond(
                prompt, principal=principal,
            )
            duration_ms = round((monotonic() - began) * 1000, 1)
            new_calls = calls[before_calls:]
            assert new_calls, (
                f"Turn {index + 1} did not invoke genuine Ollama inference; "
                "a deterministic short-circuit is not an inference PASS"
            )
            assert any(c["status"] == "generated" for c in new_calls), (
                f"Turn {index + 1} had no genuine successful model response"
            )
            assert any(
                c["authoritative_identity_present"]
                and c["canonical_personality_present"]
                for c in new_calls
            ), (
                "Authoritative identity/personality were not observed in the "
                "actual provider request; a correct-looking answer is not proof"
            )
            if memory_fixture is not None:
                assert not any(
                    c["legacy_memory_visible"] for c in new_calls
                ), "Legacy memory leaked into genuine model request"
                if index in (0, 2, 3):
                    assert any(
                        c["reviewed_memory_visible"] for c in new_calls
                    ), "Owner-reviewed V1 memory absent from Ollama model context"
                    assert memory_fixture["approved_value"] in result.content, (
                        "Real Ollama-generated answer did not use approved memory"
                    )
            assert result.content.strip(), "Blank response was falsely accepted"
            assert result.content != "Test cognitive response."
            final_digest = sha256(result.content.encode("utf-8")).hexdigest()
            assert any(
                final_digest in call.get("model_derived_sha256", ())
                for call in new_calls if call["status"] == "generated"
            ), (
                "Saved reply is neither raw model text nor an authorized pure "
                "normalization of a genuine Ollama response; canned fallback "
                "cannot count as genuine inference"
            )

            saved = app.conversation.messages()
            assert any(
                m.role is ConversationRole.USER and m.content == prompt
                for m in saved
            ), "User turn was not durably persisted"
            new_assistant = [
                m for m in saved
                if m.role is ConversationRole.ASSISTANT
                and m.id not in before_ids
            ]
            assert len(new_assistant) == 1, (
                "A genuine turn must create exactly one assistant message"
            )
            assert new_assistant[0].content == result.content, (
                "Saved assistant text differs from observed final reply"
            )
            assert app.conversation.last_reply_model_origin_error is None, (
                "Reply-model provenance recording failed"
            )
            origin = origin_reader.inspect(
                assistant_message_id=new_assistant[0].id,
                principal=principal,
            )
            assert origin is not None, "No scoped model-origin record"
            assert origin["kind"] == "model", (
                "No authoritative observed model-origin proof for saved reply"
            )
            assert any(step["succeeded"] for step in origin["steps"]), (
                "A failed model attempt cannot author a saved reply"
            )
            turns.append({
                "turn": index + 1,
                "latency_ms": duration_ms,
                "assistant_sha256": final_digest,
                "model_origin": origin["kind"],
                "provider_calls": len(new_calls),
                "quality_retry_calls": sum(
                    1 for c in new_calls if c["quality_retry_requested"]
                ),
                "failed_provider_calls": sum(
                    1 for c in new_calls if c["status"] == "failed"
                ),
            })

        # Conversation continuity evidence, not a fixed synthetic output.
        second = [m.content for m in app.conversation.messages()
                  if m.role is ConversationRole.ASSISTANT]
        assert len(turns) == 4
        if memory_fixture is None:
            assert label in second[-3].casefold(), "Short-term label was lost"
            assert label in second[-1].casefold(), "Topic switch lost label"
        else:
            assert memory_fixture["approved_value"] in second[-1], (
                "Approved V1 memory was not retained through topic switch"
            )
    finally:
        print("CORE002_LIVE_RECEIPT=" + json.dumps({
            "source_sha": observed_sha,
            "disposable_memory_v1": memory_fixture is not None,
            "reviewed_memory_id": (
                None if memory_fixture is None
                else str(memory_fixture["reviewed_id"])
            ),
            "legacy_memory_id": (
                None if memory_fixture is None
                else str(memory_fixture["legacy_id"])
            ),
            "model": model,
            "model_digest": model_digest,
            "provider": "ollama",
            "endpoint": configuration.ollama_endpoint,
            "provider_config": {
                "temperature": provider_cfg.temperature,
                "context_size": provider_cfg.context_size,
                "max_output_tokens": provider_cfg.max_output_tokens,
                "routing_fallback_enabled": configuration.routing.fallback_enabled,
            },
            "observed_writer": locals().get("writer_receipt", {
                "status": "startup_not_completed",
                "verified_exclusive_lease": False,
            }),
            "turns": turns,
            "calls": calls,
            "elapsed_ms": round((monotonic() - overall_start) * 1000, 1),
            "single_disposable_database": str(state_path),
            "content_logged": False,
            "integration_skipped_is_pass": False,
        }, sort_keys=True))
        if started:
            app.shutdown()
