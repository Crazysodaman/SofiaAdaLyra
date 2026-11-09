# AG-D028 | Artifact Library source integration checkpoint

**Status: substantial implementation in canonical `main`, not tested or accepted as a release.**
**Checkpoint source:** `b083263d9af103853d53853b81b5d4f8cf3cee1c` and earlier commits on `main`.
**Owner execution order:** consolidate usable branches into `main`; Artifact Library first, then Platform 1.0; full GitHub CI last; "production-ready" denotes entering owner-authorized live testing, NOT a claim that live tests already passed.

## Implementation delivered

| Requirement | Actual source | Current scope |
| --- | --- | --- |
| D028-00 independent signed catalog | `src/sofia/platform/ops/library_signed_index.py`; `library_signed_selection.py` | Signed Ed25519 index, audience/revision/freshness/offer binding; candidate contract remains UNFROZEN |
| D028-00 signed module manifest identity | `src/sofia/platform/modules/package.py`; `library_signed_manifest.py` | Exact canonical SHA of complete signed payload, independent key verification; preserves legacy unsigned policy digest separately |
| D028-04 authenticated peer chunks | `src/sofia/platform/ops/library_tls_chunk_transport.py`; `library_tls_resumable_fetch.py`; `src/sofia/platform/run/library_peer_gate.py` | mTLS, exact enrolled cert, scoped per-range SAFE checks, bounded resume; must still be bound to real installed service |
| D028-03 Hub | `src/sofia/platform/ops/library_tls_hub.py` | Private numeric LAN bind and bounded owner-gated mTLS serving; no self-enrollment, production activation or standalone service startup |
| D028-04 recipient bridge | `src/sofia/platform/ops/library_recipient_pipeline.py`; `library_verified_handoff.py` | Signed-selection-to-quarantine-to-independent B1 CAS bridge, distinct one-use peer cache approval; NOT automatic install |
| D028-05 large artifacts | `src/sofia/platform/ops/library_large_parent.py`; `library_large_fetch.py` | Independently signed 1MiB chunks, up to 8192 chunks/8GiB, per-chunk plus whole-object SHA; logical huge tests not physical host acceptance |
| D028-05 pins and GC | `src/sofia/platform/ops/library_retention_graph.py`; `library_retention_gc.py` | B1 full-history rollback pins plus live pins; single-blob SAFE approval, cache lock, B1 pin-revision lock and audit, no blind sweep |
| SAFE policy | `src/sofia/platform/safe/permissions.py` | Owner-authenticated scoped `library.peer.fetch`, distinct protected offline-media/peer CAS admission and one-use GC |
| D028-00 audience | `src/sofia/sdk/platform_library.py` | Optional explicit installed-service Platform audience for syntax-only request parser. Do not treat parser result as authentication |

## Mandatory remaining implementation

1. **Freeze D028-00**: publisher signed-manifest bytes, one authoritative index protocol, Rust/Python SDK parity, SAFE/STOP and installed-service broker signoff. Neither a Hub signature nor a typed DTO supplies owner authority.
2. **Real installed service**: bind source Hub and destination peer roles to current Platform enrollment, correct local generation, owner-activated Hub role, OS-managed key material, run/stop/revocation and network endpoint. No implicit LAN admission. No Core dependency.
3. **Package and lifecycle**: wire approved B1 signed Windows/Debian12 installer and receipt store, synthetic Core/module dependency closure, verify/stage/install/activate/rollback across distinct one-use approvals. Ensure signed module D028 manifest digest is NOT legacy unsigned policy identity.
4. **Retention**: supply real B1 revision lock and independently verified complete pin sources; test GC crash/outcome-unknown and installed rollback on disposable hosts. Do not expose `delete_one` as public RPC before canonical service proves pin-graph completeness and synchronization.
5. **Native management**: real source-bound Rust GUI/TUI/CLI library observations, truthful offline/stale/unknown states, source selection, progress, approval, storage and Hub role. UI never verifies trust or creates grants.
6. **Consolidation**: reconcile useful unique branches and conflicted historical source into `main`; preserve obsolete/unsafe historical refs without overwriting newer security fences.
7. **Release evidence**: real disposable Windows + Debian12 installed-host runs for LIB-01..LIB-16 and existing Platform 38-row matrix. Ledger currently 0/16 LIB accepted, 0/38 Platform PASS; don't count stubs or generated test keys as signed host certification.

## Focused validation commands (NOT claimed executed)

Run only from a full, clean repository checkout with its declared dependencies:

```bash
python -m compileall -q src/sofia/platform/ops src/sofia/platform/modules src/sofia/platform/run src/sofia/platform/safe test
python -m pytest -q test/test_library_tls_resumable_fetch.py test/test_library_signed_index.py test/test_library_signed_selection.py test/test_library_verified_handoff.py test/test_library_recipient_pipeline.py test/test_library_large_parent.py test/test_library_large_fetch.py test/test_library_retention_gc.py test/test_library_signed_module_manifest.py test/test_library_peer_policy.py test/test_library_current_peer_authorizer.py test/test_safe_platform_library_contract_preview.py
```

These commands may surface genuine problems. Fix source/tests rather than weakening SAFE or reclassifying mandatory red cases as green. Full GitHub workflows remain the last development gate, not disabled or asserted to pass here. Pushes may still trigger repository-configured automatic workflows.

## Release facts

- The existing Team E [16-case ledger](PLATFORM_1_0_TEAM_E_AG_D028_LIB_LEDGER_2026-11-08.md) remains authoritative. Current statuses MUST NOT be promoted from source reviews.
- The existing [D028-00 decision ledger](AEGIS_D028_00_CROSS_TEAM_SIGNOFF_LEDGER.md) remains UNFROZEN and requires real same-SHA A/B/C/D/E signoff.
- None of these helpers independently enrolls a peer, creates a production publisher signing key, stages or activates a Core, or touches protected personal state.
- No live Hub, signed release deployment, native systemd/SCM install or complete multi-host acceptance has occurred in this checkpoint.
