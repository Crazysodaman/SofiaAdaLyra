# CORE-005 | IG-001 source integration contract (DRAFT / NO-GO)
Coordinator C-003-T5 approved **test design only**. No real-host, protected-state, production, or merge approval. Nothing here is an accepted IG-001 proof.

## Exact-source integration manifest
- Base main: `668e403d91b98a9cc467c6fc2caa554063aedeb9`, base tree `c19b85100edbcacf5ed085c946b5054a238bbe0c`.
- CORE-001 PR #256: `b8eff19933bc8a6d889a00f311f9972858babf96`.
- CORE-002 PR #253: `9011b1acc64b9af7e31c787a6532185a0daa6b7c`.
- CORE-003 PR #252: `daca6999bc648fcccd7452d8f17324c410063c56`.
- CORE-004 PR #254: `197f3ea33a55804aa997f323a35d0db7b3ee8e64`.
- Method: new draft-branch commit with exact existing Git blob SHAs from these PR heads, **one parent = pinned main**. No team PR merged, no rewrite of main. 28 changed source/test/docs/workflow paths; overlap count 0. Full file-mode and blob-identity verification required after commit.
- Team 3's *newer* legacy-memory quarantine V1 code postdates the coordinator-pinned `daca6999` and is NOT integrated in this first frozen snapshot. Its policy negatives are a dependency for the next reviewable candidate revision. The old historical recall exception remains an explicit blocker.
- Team 1's *newer* authoritative runtime-generation edits also postdate `b8eff199`; must be separately reviewed. These source snapshots may be semantically incompatible despite disjoint filenames.
- The direct Core Link status claim `ready` is not independently verified INFERENCE_READY. The client request (~30s), Ollama per-I/O (45s), worker response (120s), worker lease (180s) require an explicit bounded end-to-end cancellation/late-reply contract before host certification.

## IG-001 acceptance sequence (strictly one combined signed candidate)
1. On disposable Windows + Debian 12 hosts only, verify approved publisher-signed Platform/SDK/Core artifact exact digests, trust roots, OS peer identity, version/ABI and protected-directory ACL. Install via approved Platform path. Record exact host IDs, timestamps, signer identity, source tree, package hashes, canonical identity UUID, OS service PID, writer lease/generation and signed receipts.
2. Start one authorized Core with **new synthetic** state; distinguish PROCESS_READY, CORE_READY, INFERENCE_READY. Refuse missing/stale READY, absent generation, revoked lease, STOP and duplicate writer. State owner is never inferred from service presence.
3. With an already-running, approved model endpoint, obtain at least four genuine generated Ollama turns, including topic switch, user label recall and persisted model-origin hashes. Never count a deterministic fixture, canned fallback, skipped integration, `/api/version` or mock as real inference.
4. Authenticate private owner test principal and review a synthetic memory; promote and correct it, proving old source ineligible, corrected current-source eligible and wrong-audience/revoked/erased exclusion. Once approved, run V1 opt-in legacy quarantine and old-backup downgrade negatives on disposable state only.
5. Stop and restart Core. Prove unchanged canonical UUID, Constitution/hash pin, personality, saved conversation IDs and reviewed-memory correction, with a *single* writer and valid fresh generation. Run separate forced kill/recovery and full consistent signed backup/restore/erasure journal precedence.
6. Reconnect a separately authenticated pinned-mTLS client; re-enroll/rebind **synthetic** credentials only as authorized. Recover uncertain turns by idempotency lookup without duplication, show same conversation, obtain another genuine model answer. Reject wrong identity, certificate/CA, expired enrollment, revoked scopes and stale generation.
7. Simulate network partition; STOP and revocation before admission and while the real model is computing; ensure no unauthorized new admissions, no unauthorized late publication or duplicate persisted assistant reply. Capture bounded timeouts, cancellation, worker fencing, failure and recovery. Failure at any stage = IG-001 FAIL; missing required host proof = BLOCKED.

## Negatives N01–N15
N01 dead child + stale READY; N02 wrong/missing generation; N03 duplicate writer; N04 wrong signer/package digest; N05 blank/thinking-only provider; N06 timeout/late reply; N07 changed original/audience and correction rollback; N08 unattested legacy recall / policy downgrade; N09 erased-memory resurrection on restore; N10 duplicate/nonfinite JSON; N11 wrong CA/cert/identity/audience; N12 STOP/revocation in turn-admission/inference; N13 disconnected client and idempotent reconnect; N14 corrupt/incomplete signed backup; N15 healthy OS service without valid Core/inference readiness.

## Evidence fields (all pending)
`scenario_id, revision, parent_sha, team_source_shas, test_command, test_start/end_utc, host_os_build, host_id, interpreter_version, signer_trust_root, core_artifact_sha256, platform_artifact_sha256, config_schema_version, core_identity_uuid, writer_host_generation, actual_pid, model_digest, network_tls_fingerprint, source_state_digest, pre/post_memory_ids, negative_receipts, status(PASS/FAIL/BLOCKED/UNTESTED/SKIP/CANCELLED), reviewer, log_reference`.
Do not publish raw secrets, private memory or response text in public CI.

### Preflight is NOT IG-001
`.github/workflows/core005-ig001-preflight.yml` runs real pytest against synthetic disposable data on Windows/Linux using checkout of the exact branch head. Its results are not genuine inference or installed service evidence. Full IG-001 needs all stages on a single combined installed artifact and independent Team 5 review.

### Cross-reference and stop boundary
Core 16-scenario ledger is separate from G8 issue #129's 16 primary real-host GO checks and 118 supplemental entries; all G8 primary rows remain 0/16. No waiver, release signing claim, production service activation, protected state, Venus migration, or merge is authorized.
