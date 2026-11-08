"""CORE-002 owner-opted-in genuine Ollama Core conversation acceptance.

No mocks, canned responses, service startup, model pull, production writer,
or production-state access. An integration skip NEVER counts as a PASS.
"""
from hashlib import sha256
import json
import os
import platform
from pathlib import Path
from time import monotonic

import pytest

from sofia.core.cognition.providers.ollama_provider import OllamaProvider
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


@pytest.mark.integration
def test_core002_real_provider_multiturn_and_persistence(monkeypatch, tmp_path):
    if os.getenv("SOFIA_CORE002_LIVE") != "1":
        pytest.skip("OWNER OPT-IN REQUIRED; skip is NOT a live-inference PASS")
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
        receipt = {
            "provider": "ollama",
            "model": self.configuration.model,
            "endpoint": self.endpoint,
            "real_client_path": True,
        }
        try:
            generated = true_provider_call(self, request)
            receipt["status"] = "generated"
            receipt["generated_sha256"] = sha256(
                generated.content.encode("utf-8")
            ).hexdigest()
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
    principal = local_sparks_principal()
    label = "cobalt-otter-472"
    prompts = (
        f"For this temporary chat, please remember the label {label}. "
        "Acknowledge it briefly.",
        "What is the exact label I gave you in my preceding message?",
        "Switch topics: explain what a circuit breaker does in one sentence.",
        "Return to the temporary label from earlier. Repeat it exactly.",
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
            assert result.content.strip(), "Blank response was falsely accepted"
            assert result.content != "Test cognitive response."
            final_digest = sha256(result.content.encode("utf-8")).hexdigest()
            assert final_digest in {
                call.get("generated_sha256") for call in new_calls
                if call["status"] == "generated"
            }, (
                "Saved reply is not a directly observed generated candidate; "
                "post-generation canned repair is NOT an inference PASS"
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
            })

        # Conversation continuity evidence, not a fixed synthetic output.
        second = [m.content for m in app.conversation.messages()
                  if m.role is ConversationRole.ASSISTANT]
        assert len(turns) == 4
        assert label in second[-3].casefold(), "Short-term label was lost"
        assert label in second[-1].casefold(), "Topic switch lost label"
    finally:
        print("CORE002_LIVE_RECEIPT=" + json.dumps({
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
