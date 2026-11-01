# Sofía Run 2: Natural-language grounding and personality audit

Date: 2026-11-01 (America/Chicago)
Source baseline observed on Venus: `333e61fd7ac37c73486eedc7218aa164cdd85ade`
Development policy: **main only**. All production/canonical-state migration and service activation remain explicitly out of scope.

## Owner-observed live evidence

The owner reported: desktop startup PASS; canonical name/fox identity PASS;
natural conversation usable but off-character; natural disagreement FAIL;
clean exit PASS; memory and durable emotion untested.

Exact failing utterances included:
- "So what is your outfit rn?" → invented floral/denim/scarf ensemble rather than canonical wardrobe projection.
- "what time and date is it rn" → incorrect day/date/time assertion despite an existing runtime clock.
- "I see so tell me anything you see observe i mean" → unverified room, airflow, lighting and health claims.
- "what was your last runtime" → incorrect assertion that no usable clock/history existed.
- "Check weather again" → did not clearly perform a grounded provider refresh.
- "do you believe me" (after a user-reported clock correction) → long, needlessly adversarial epistemology speech.

This is a *live observed failure*, not proof that the underlying authority stores or environment model are absent. A successful source fix is not proof of model-behavior acceptance.

## Source audit

- `core/cognition/v2/matrix.py` plans domains and evidence needs from concepts and conversation focus, before the main LLM. Its original taxonomy did not treat generic first-person observation questions as ENVIRONMENT.
- `core/environment/query.py` has authoritative date/time/weather/indoor snapshots, but the direct question matcher relied on narrow forms. It was not resolving the owner's combined-date/time or weather-refresh phrasing.
- `modules/avatar/self_fact_query.py` uses authoritative wardrobe state but did not reliably recognize the owner's natural current-outfit phrasing.
- `platform/application/conversation_service.py` invokes the V2 answer handler **before** the more generic `runtime/response.py` factual resolvers. Modifying the resolvers alone would not reliably change desktop behavior.
- `platform/operational/model.py` already carries previous runtime timestamps and continuity evidence; the conversational status path did not use it for ordinary last-runtime questions.
- `core/cognition/repetition_guard.py` and `quality_repair.py` already handle some canned or insulting replies, but did not target short trust questions escalated into accusatory lectures.

## Changes implemented on main

1. Existing ENVIRONMENT resolver now recognizes bounded natural combined-clock questions and general observation requests. It reads trusted timestamps and reports only currently verified weather/indoor observations, clearly identifying absent visual evidence; no model-created physical readings are accepted as facts.
2. Existing Matrix V2 plans generic read-only observation questions as ENVIRONMENT without elevating the request to an action or granting authority. Runtime refreshes approved provider observations when explicitly requested.
3. Existing AVATAR resolver interprets natural *present* wardrobe questions from canonical current presentation while excluding hypothetical, future, action and multi-clause requests.
4. The normal `ConversationService` path now prioritizes narrowly identified canonical read-only clock/observation/outfit/previous-runtime queries before a general generative reply, preserving V2 coordination, stored conversation turns, audience projections and response validation.
5. Existing OPS status resolver now reports recorded previous runtime start/stop timestamps or accurately says that no verified previous record is present. It does not claim continuous awareness while offline.
6. Weather retries such as "Check weather again" use a read-only provider refresh and preserve stale/unavailable outcomes instead of claiming a new observation.
7. Provider-side response quality handling recognizes an accusatory or overlong reply to a short contextual trust question, requests one grounded text-only rewrite and uses a conservative fallback if neither draft is acceptable.
8. Tests now cover exact Run 2 utterances, additional everyday variants, inappropriate broad matching, mixed-question routing, absent evidence and deliberate uncertain cases.

## Acceptance and limitations

- **Changes are source-authored on main.** CI must be inspected against the final exact SHA; intermediate workflows may be cancelled by newer commits.
- Deterministic tests do not establish real `qwen3.5:9b` conversational behavior, Windows model residency, user-facing tone or memory continuity. A supervised Venus rerun is mandatory.
- No new secondary AI, parallel semantic coordinator, permissions bridge, auto-executing actions, canonical database migration, process/service startup or install workflow was introduced.
- This is bounded natural language support plus an authoritative answer-path repair, **not a claim to understand all paraphrases**. Full model-assisted semantic interpretation remains a separate, reviewed Cognition V2 integration goal; untrusted model interpretation cannot create evidence, consent, permission or execution.
- Other GO LIVE gates including signing, migration/fencing, G8 host shakedown and independent RC acceptance remain open.
- Link failures and verification to issue #120 (G4, G7-A) and V18 Phase 08 CA-501/506/1803/1804/3802; no boxes are marked accepted solely because code was pushed.

## Windows focused verification

```powershell
Set-Location 'H:\Users\Crazysodaman\Programing\SofiaAdaLyra'
git pull --ff-only origin main
git rev-parse HEAD
python -m pytest -q --durations=10 \
  test/test_environment_query.py \
  test/test_avatar_self_fact_query.py \
  test/test_operational_status_queries.py \
  test/test_cognition_v2_personality_domains.py \
  test/test_response_quality_hardening.py
```

PowerShell users must replace the shell-style line continuations above with backticks, use a single-line command, or run the test file names separately.

Do not start the previously disabled Windows service/watchdog or a second canonical writer for this verification. Use a verified disposable development state for supervised behavior testing.

## Owner Run 3 acceptance

Test conversationally, not by memorizing commands. Include: a time/date question in a new phrasing; current and hypothetical outfit questions; fresh vs stale weather retry; unverified "what do you see" and a genuine scoped source observation; previous-runtime history; a trust/correction follow-up; multi-topic conversation, memory and clean STOP. Record exact HEAD, active model, observed text and any source receipts. Fail if model prose claims unauthorized sensor data or current time without trusted clock evidence.
