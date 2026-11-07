# Disposable Debian12 signed code acceptance

The offline VM harness now assembles a test release from the actual SDK/Platform
wheels, Debian12-built Rust service, bundled CPython runtime and mandatory
binary dependency wheels. It records observed package names, versions, hashes,
input source and pinned base-image reference. The dependency index, basic SBOM
and assembly provenance are explicitly lab metadata; they claim neither
standards compliance nor production release attestation.

A disposable Ed25519 software signing key is generated in memory. Only its
public key and signature are persisted. This key is neither an owner principal
nor a production trust root. It cannot authorize a production installation.
The harness invokes the production Platform release verifier and code stager;
the guest environment and service use the staged assets and runtime.

Each actual offline kernel/systemd boot must establish:

- The signed release matches the exact reviewed source and Debian12 target.
- The runtime archive and every materialized runtime file match the inventory;
  a real relocated runtime process succeeds without Core or Ollama packages.
- The installed service binary matches its signed digest.
- Every wheel-owned SDK/Platform file matches its signed wheel, except pip's
  legitimately rewritten RECORD. Dependency consistency passes offline pip check.
- The supervised worker executes the staged runtime binary; ordinary stop,
  restart, crash recovery and duplicate denial retain the previous checks.
- Both boots retain Platform UUID/key, increasing generations, identical release
  manifest digest and identical installed component file count.

Receipts use `aegis.disposable.debian12-vm.v3` and summary v2. Older receipt
versions are not silently adopted as this stronger acceptance. All receipts
retain `production_authorized=false` and `release_accepted=false`. The guest
probe requires an explicit disposable kernel marker and disposable-only input
scope before service or power operations. Failures expose bounded tails from
owned test logs; redirected diagnostic paths are rejected.

The harness still assembles a disposable test image. It does not supply the
production owner approval ceremony, OS installer backend, Windows reboot
acceptance, release selection, upgrade/rollback or backup/recovery policy.
Both Platform-only and full-project readiness remain NO until those independent
mandatory gates are complete. Production services, Fleet state and G8 are not
part of this test.
