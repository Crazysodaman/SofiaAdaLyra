# Keyless release evidence — proposed default

Status: IMPLEMENTED FOR VERIFICATION; not certified until a real candidate
archive has an authentic attestation and successful cryptographic verification.
Unit-test ZIPs and mocked verifier output are explicitly not signing evidence.

## Audit and authority

The existing `.github/workflows/release-promotion.yml` describes a manually
dispatched Ed25519 promotion job in the `production-release-signing` environment.
It expects `SOFIA_RELEASE_SIGNING_KEY_PEM_B64` and an operator-supplied signer ID.
`sofia.platform.dev.release_signing` loads Ed25519 private keys;
`sofia.platform.safe.release_ed25519` verifies externally pinned public keys.
This establishes that an implementation exists, not that a configured key,
environment reviewer, owner permission or trust root has been approved. No
secret contents were inspected. The attached runtime reports no signing secret
or outbound signing identity. The owner explicitly confirmed that no existing
release-signing identity has been approved or verified.

The owner authorized GitHub OIDC/Sigstore keyless attestations as the proposed
default for release evidence. No long-lived private key is generated or stored.
The legacy promotion workflow and runtime activation guards are preserved.
Candidate provenance does not grant owner approval, production deployment,
trust enrollment, canonical-state access or writer-cutover authority. Production
activation still requires a separately approved trust policy compatible with its
existing verifier; this change does not silently replace that boundary.

## Implementation and trust chain

Both Windows and Debian RC workflows retain their complete installed-wheel,
provenance, reproducibility and release-content gates. Their build jobs retain
`contents: read`, without OIDC or attestation-write permission. Each successful
build exports the exact integrated/separated upload artifact IDs and SHA-256
digests. No name wildcard or external workflow run is used for attestation.

A separate Ubuntu-hosted `attest` job requires successful build completion,
the exact `Crazysodaman/SofiaAdaLyra` repository, and either main or the approved
development branch. It alone gets `id-token: write` and `attestations: write`,
plus read-only repository/actions access. It downloads those exact immutable
archives without extraction and requires digest-match errors to fail the job.
It installs no candidate package or dependency and executes only the reviewed
stdlib-only `src/sofia/platform/verify/keyless_release.py` policy script.

The script independently compares archive bytes to the build's upload digests,
rejects unsafe/duplicate ZIP paths, and requires the expected integrated and
separated formats, exact source SHA, manifest-bound verification evidence,
accepted clean full gates and successful executed commands. The existing build
job has already verified the complete manifest and wheel contents. The signed
subjects are the exact uploaded ZIP archives, which transitively bind every
wheel, lock, manifest and evidence byte in them; extracted files are not the
subjects of these attestations.

`actions/attest-build-provenance` exchanges GitHub's short-lived workflow OIDC
identity for Sigstore signing, binds SHA-256 subjects to SLSA v1 provenance and
publishes the bundle through GitHub's artifact attestation service. The action
and new checkout/download/upload steps are pinned to upstream commit SHAs.
No custom cryptographic verifier, synthetic certificate, private key secret or
long-lived signing credential is introduced.

`gh attestation verify` performs actual signature/certificate/transparency
verification. Policy constrains the certificate-backed source repository,
exact signer workflow, signer commit digest, source commit digest and source
ref, GitHub OIDC issuer, SLSA v1 predicate and hosted runner identity. JSON
parsing alone never counts as cryptographic verification. Online retrieval is
intentional: GitHub can resolve the repository's current identity; offline name
matching cannot detect repository renames/name reuse by itself.

Only after both archives verify and remain byte-identical does the job emit
`verified-attestations.json`, containing the full verifier results and
`production_authorized: false`. A failed/unavailable verifier removes any stale
success receipt. Bundles, original archives, subject hashes and diagnostics
are uploaded separately even on failure; the existence of that diagnostics
artifact is not acceptance. Require the `attest` job to succeed and inspect its
nonempty verification receipt.

## Independent verification

Use a current GitHub CLI supporting `gh attestation verify`, `--source-digest`,
`--signer-digest`, `--source-ref` and `--deny-self-hosted-runners`. The attached
local CLI does not implement `gh attestation`; it cannot certify a real artifact.
Hosted runners must support the command or verification fails closed.

Download `keyless-release-evidence-debian-FULL_REVIEWED_SHA` (or Windows) from
the exact successful RC run. Preserve its two inner original candidate ZIPs;
do not regenerate/recompress them. Independently obtain the expected full SHA,
source ref, artifact IDs/digests and workflow path from reviewed run evidence.
Replace the placeholders in this example:

```sh
gh attestation verify ORIGINAL_CANDIDATE.zip \
  --repo Crazysodaman/SofiaAdaLyra \
  --signer-workflow Crazysodaman/SofiaAdaLyra/.github/workflows/debian-release-candidate.yml \
  --signer-digest FULL_REVIEWED_SHA --source-digest FULL_REVIEWED_SHA \
  --source-ref refs/heads/chatgpt/go-live-release-env-version \
  --cert-oidc-issuer https://token.actions.githubusercontent.com \
  --predicate-type https://slsa.dev/provenance/v1 \
  --deny-self-hosted-runners --format json
```

Repeat for both inner archives. For Windows use `release-candidate.yml` as the
signer workflow. Main candidate verification must require `refs/heads/main`;
a valid development-branch attestation is never main release approval. Keep
the archives, digests, returned certificate/transparency/provenance results,
workflow run URL and verifier version in durable reviewed evidence storage.
The repository's current numeric ID is `1367299966`; independently check current
ownership if names or trust policy change. Never trust a copied receipt instead
of verifying the bytes and cryptographic attestation yourself.

## Failure and recovery

Missing OIDC/attestation permissions, unsupported CLI, identity mismatch,
digest change, unsuccessful/stale gate, unavailable issuer/transparency/GitHub
service, absent bundle or failed cryptographic verification blocks signing
acceptance. Do not use an unsigned archive as fallback. Preserve failure logs;
retry the reviewed workflow after transient service recovery, keeping each
run's IDs and evidence distinct. New source changes require their own full RC
gates and attestations. Do not edit old receipts or fabricate replacement bundles.

An expired short-lived signing certificate does not require retaining a private
key: verification uses the signed transparency/timestamp evidence. Keep bundles
and original archives beyond GitHub artifact retention. If offline verification
is necessary, use a trusted Sigstore root and `--bundle` under a separately
reviewed ownership/identity policy; do not disable cryptographic or identity
checks to make an old bundle pass.

If a workflow/repository identity is compromised, block affected source/workflow
digests in the release-acceptance policy, halt promotion, review repository
permissions and OIDC job grants, recover the trusted workflow and rerun complete
gates at a new reviewed SHA. A previously valid signature is not proof the code
is safe after compromise. No signing-key backup, escrow or long-lived key
rotation is needed for this keyless path. Production recovery, STOP and owner
approval remain separate controls.

## Required real acceptance evidence

Record exact source/workflow SHA/ref, successful RC and `attest` job URLs, original
artifact IDs/SHA-256 digests, attestation IDs/URLs, downloaded Sigstore bundle,
both successful `gh` verification results and an independent review. Until those
exist, status is CODE-READY / VERIFICATION PENDING, never signing complete,
release certified or SHAKEDOWN READY.
