# Batch G9 + Engineering 22I: conversational voice and durable remote safety state

**Status:** proposed code for a reviewed feature-branch checkpoint. Offline tests cover local contracts only. This is **not** a completed live integration or production remote deployment.

## G9: natural, grounded personality expression

`sofia.personality.expression.personality_expression_guidance` instructs the cognitive engine to answer identity questions naturally instead of reciting the Constitution or runtime IDs; fox-ear and tail narrative cues are optional, varied, and explicitly representational. It forbids turning a planned remote capability into a claim of working access and requires evidence for action outcomes. Guidance does not rewrite model outputs and cannot guarantee compliance from Ollama. Existing identity, constitution and embodiment records remain authoritative. Full-runtime Ollama review at 20,000 context, `think=False`, is **not run** by this batch.

## 22I: persistent grants, one-shot replay ledger, durable audit records

`DurableRemoteAuthorization` implements the existing `RemoteAuthorization` interface, but stores explicit `RemoteGrant`s in an on-disk SQLite database. Matching requires the exact grant ID, node ID, capability, operation and an unexpired timestamp. Revocation survives restarts; revoked/expired IDs cannot be silently renewed or reused. Grant creation must occur through a trusted human-administered approval path, not via model-generated text. This batch does **not** provide that approval UI.

`DurableRemoteLedger` records denial and commits a reservation *before* external authentication or execution. A duplicate UUID is denied across process restarts and separate SQLite connections. A stranded `reserved` row indicates an unknown outcome after interruption and is **never** automatically retried. Results are recorded as **remote-reported** outcomes, not proof that the remote host performed the operation. Do not prune ledger rows unless the replay policy is explicitly redesigned and reviewed. Back up and protect the database with OS access controls; an administrator with write access to the database can modify security state.

`DurableDistributedGateway` is an opt-in wrapper around the existing `DistributedGateway`; it is **not** automatically wired into the CLI or default runtime. Callers must supply an independently authenticated `RemoteTransport`, an explicit enrolled node, persistent authority, and ledger. Simply returning `True` from a fake transport is not authentication. There is still **no** concrete WinRM transport, restricted Artemis endpoint, credential provisioning, enrolled-node persistence, actual remote file reader, automatic local file investigation, live connection, or network scan. Do not expose a listener or provision an unrestricted PowerShell endpoint on the strength of these tests.

A running WinRM service on Artemis (Windows Server 2022 Datacenter) does not establish authenticated remote connectivity. Domain versus workgroup enrollment and the constrained PowerShell endpoint must be configured and verified before the live read-only gate.

## Verification and integration gate

1. Run `python -m pytest -q test/test_personality_expression_g9.py test/test_distributed_durable.py test/test_distributed_operations.py test/test_distributed_authorization.py` in the **actual** repository. Existing test contracts must continue to pass.
2. Run `python -m pytest -q` and inspect exact changed files, `git diff --check`, and the reviewed feature-branch diff.
3. Supervise a real complete-runtime Ollama scenario set and record raw answers privately. In a separate live gate, enroll Artemis and prove actual authenticated read-only inspection, revocation, replay rejection, audit persistence, and no permission escalation.
4. Report each gate as passed, failed, or **not run**. Do not merge into `main` until reviewed, and do not infer Windows or network verification from offline mocks.
