# PKG-SAFE | Independent authority, privacy, stop and recovery

**Branch:** `feature/pkg-safe-foundation` from `main` SHA `2141879`. **Status:** a fail-closed *pure* preflight prototype, not a deployed authorization server, identity provider or E-stop. This package is a gate for every other package; no release can bypass it.

## Security outcome
Authenticate the caller, verify a domain-specific scoped/expiring grant and enforce revocation, stop, audit, privacy and recovery **outside the language model**. A model's text, a source file instruction, a Discord message, a synthetic lab event or an administrator's root access is not permission to rewrite protected identity or Constitution. Existing runtime authority and integrity foundations are inputs for audit.

## Slices
1. **S0 threat model:** enumerate actors (Sparks, Sofía, bot, peer, helper, simulated actor), trust roots, data categories, disclosure surfaces, secrets and existing code paths that bypass checks. Pin exact existing main and feature SHAs.
2. **S1 identities and grants:** bind authenticated client and machine identities to issued scope/domain/action/target/expiry, issuer proof and nonce; fail closed on missing, stale or mismatched claims. New `src/sofia/package_foundations/safe.py` checks only caller-supplied preconditions; it cannot authenticate a caller or authorize an action.
3. **S2 stop and revocation:** atomic revocation checked at execution and replay, consistent across CLI, future Discord and UI, with independent kill for helpers/NET and independent hardware E-stop for BODY. Per-session text stop is not a global stop.
4. **S3 privacy:** retention and deletion policy for originals, emotion/relationship/intimate records, Discord DMs, voice and logs; safe redaction and minimal diagnostic capture; secret rotation and secure storage outside Git/model prompts.
5. **S4 recovery:** backup inventory, checksummed snapshots, restoration tests on disposable copies, migration downgrade/failure modes, damaged state isolation and signed/verified canonical Constitution integrity. Never run destructive restoration on `state/sofia.db` during exploration.
6. **S5 adversarial E2E:** forged client IDs, replay, cross-session confusion, prompt injection, background delivery after opt-out, tool output poisoning, timeout/race and unexpected shutdown. Measure how denial is enforced even when the model misbehaves.

## Acceptance
Run `python -m pytest -q -x test/test_pkg_safe_foundation.py`; then independent issuer authentication, concurrent stop-versus-send, replay persistence, cross-client revocation, wrong-account private data, SQL corruption and backup restoration on copies. Report the authority boundary's **real observed outcome**, not only an agreeable assistant message. Coordinate CORE/INTERACT/MEM/NET/ACT/DEV/UI/BODY/EVOLVE and VERIFY security gates. No user credentials, production secrets or state files are touched by this branch. Full tests, audited deployment and separate merge approval remain pending.
