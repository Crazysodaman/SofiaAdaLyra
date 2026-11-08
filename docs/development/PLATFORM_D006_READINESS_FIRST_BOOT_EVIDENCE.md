# D-006 | Debian first READY vs post-kill recovery | Team A/B/E handoff

Status: **diagnostic draft only**, not a root-cause certification, owner permission, production GO or acceptance. #255 stacks on #242. #249 is a separately successful two-boot control. No activation/merge permitted.

## 1. Source-only controlled delta

- Failing **#240** SDK HEAD `8f0a9f9a72bc2ec314ef7cc2b182cdb41f312bb1` and **#242** Fleet HEAD `43404546d6c8d012b701f2faf6e22f6e86cdd434` fail at `first=ready()`, before any forced-kill action.
- Failing **#236** lifecycle HEAD `33f7ba020cdd266284ac1803ebe79d2e9b33b3a9` fails at `third=ready(second['supervisor_pid'])` after the real `systemctl kill --kill-whom=main --signal=SIGKILL` action.
- **#249** HEAD `1ee89b8cf4fdb6c98a1a18ea694a081e5794901b` passes exact-head R1, Rust service, Platform and Debian VM workflows and independently inspected two-boot guest receipt/summary.
- **#255** initial HEAD `98503f8d65b94a3c38b3968f07d7b66f95df047b` copies EXACTLY the #249 two-file Rust and guest probe correction into #242. GitHub comparison from #242 to initial #255 changes only the two files below. No owner service, package, IPC, identity, STOP or Core authority is added.

| Source file | Successful #249 and initial #255 Git blob (same bytes) |
| --- | --- |
| `rust/crates/sofia-platform-lifecycle/src/bin/platform_service.rs` | `60ade556c4e77e68b1bcd9ff7d719673224281f3` |
| `test/fixtures/aegis_debian_vm/probe.py` | `a3c59eb3ea101ce006f15161d1a664be07337e63` |

The Rust change admits **12 seconds for initial Python worker READY**, bounded under systemd `TimeoutStartSec=15`. Steady-state health IPC **stays at 5 seconds**. The guest probe `ready()` **stays at 45 seconds**. Worker identity, service generation, single writer, two real boots, kill recovery, duplicate-instance refusal, release signatures, STOP/lease and denied operations do **not** get relaxed. The additive guest failure diagnostics retain bounded `ActiveState, SubState, Result, MainPID, NRestarts, ExecMainStatus, ExecMainCode`, unit/path assertion results, journal record counts and bounded error **class**, never full journal content, environment or private identity.

## 2. Independently downloaded GitHub guest archives

These are the original workflow ZIP SHA-256 values returned by Actions and recomputed locally, **not** the Rust binary checksum.

| PR / stage | Run | Artifact ID | ZIP SHA-256 | Guest result |
| --- | --- | --- | --- | --- |
| #240, first READY | 42491156343 | 13622651250 | `457261ee840247d2ae15f877fe6cdb24e19f813c89b58c1215a964082c6b2a1c` | FAIL, systemd activating/restarting; `ExecMainStatus=2`, `NRestarts=2`, no journal READY |
| #242, first READY | 42491245336 | 13622621383 | `0e4af3e06c64a2206fe68171eaaea1c9c7c044398fd5c5f64cc0cfa4a97293f3` | FAIL, identical first-ready evidence |
| #236, after SIGKILL | 42486942521 | 13620685576 | `cbc4b48e1d1602c042c91e9aad4293bf6615fc13dc4b30384dcd822372872bc1` | FAIL, `ExecMainStatus=2`, `NRestarts=2`, journal **has** prior READY, `previous_pid` non-null |
| #249, two-boot comparison | 42490998718 | 13621438983 | `343582b49848ce0f597915dc9f80aeb5d1ea693bb64d9008b2895554f6720bc3` | PASS: 2 separate boot IDs, 6 increasing generations, 2 crash recoveries, 2 duplicate denials, 4 graceful stops, 434 verified installed component files per boot |

The 3 failure archives contain no successful guest receipt. The passing archive includes `receipt-1.json`, `receipt-2.json` and `summary.json`; both boot receipts explicitly `production_authorized=false` and `release_accepted=false`. All four archives have passing ZIP CRC and the same independently pinned Debian source image.

**Evidence interpretation:** Different current binaries and one green control do not PROVE cold start was the only root cause. Guest QEMU scheduling, dependency wheel reproducibility and the systemd 15-second boundary remain possible contributors. Do not promote installed-host acceptance.

## 3. Executable, disposable-only Team E commands

On an **authorized disposable Ubuntu 24.04 runner** with local Docker and QEMU TCG, Python 3.12, Rust **1.88.0**, supported Debian image and a clean exact-SHA checkout:

```bash
set -euo pipefail
git rev-parse HEAD                  # MUST equal the exact tested draft SHA
test -z "$(git status --porcelain --untracked-files=no)" # CLEAN tracked source
python -m pip install -e . pytest
python -m pytest -q \
  test/test_aegis_debian_vm_runner.py \
  test/test_ops_signed_vm_release.py \
  test/test_package_grouping.py
out="/tmp/aegis-guest-d006-$(git rev-parse --short HEAD)"
test ! -e "$out"                    # runner refuses reused output
python -m tools.aegis_debian_vm \
  --checkout "$PWD" --output "$out" \
  --toolchain "$(rustc --print sysroot)" --disposable-vm
export AEGIS_D006_EVIDENCE_OUT="$out"
python - <<'PY'
from pathlib import Path
import json
import os
p=Path(os.environ["AEGIS_D006_EVIDENCE_OUT"])
first=json.loads((p/"receipt-1.json").read_text())
second=json.loads((p/"receipt-2.json").read_text())
summary=json.loads((p/"summary.json").read_text())
assert summary["result"]=="VERIFIED_DISPOSABLE_VM_CONTRACT"
assert summary["generations"]==first["generations"]+second["generations"]
assert summary["generations"]==sorted(set(summary["generations"]))
assert first["boot_id"]!=second["boot_id"]
assert first["platform_id"]==second["platform_id"]
assert all(x["production_authorized"] is False and x["release_accepted"] is False
           for x in (first,second,summary))
print("D006 guest receipts: verified disposable comparison only")
PY
```

The final Python snippet reads only the exact disposable runner output from the exported `AEGIS_D006_EVIDENCE_OUT` path; never run or inspect arbitrary production state. **Do not run** this runner against a real Sofía VM, production Portainer, owner Core or non-disposable Docker socket. The lab guest itself refuses missing `aegis.disposable_vm=1` kernel marker.

For GitHub Actions workflows the pinned exact-head commands are `gh run view 42497808698` and `gh run view 42497808689`; queued or missing is not PASS. Re-run milestone CI only on the finalized integration SHA, not after every development commit.

## 4. Required signed host and service contract review

**Team A**: adopt exactly ONE canonical 12s-initial/5s-health Rust service path (or a better tested bounded correction), preserving the 15s native systemd and 45s guest gates; do not duplicate Team D's supervisor or lease authority. Preserve per-service READY/STOP, stale generation and current safety negative tests. Check why late Python READY, early worker exit or state lease failure is actually occurring using *bounded classified* journal evidence, not speculation.

**Team B**: install only through the existing B1 governed signed installer; provide exact signer/root and current revocation, service executable and bundled Python runtime digest, systemd/Windows SCM service lifecycle, STOP/no-auto-Core proof and actual installed receipt. Do not convert a synthetic guest's source artifact into a production authorization.

**Team E**: independently confirm guest source SHA, base image, Rust executable, release manifest, two-boot signed identity/monotonic generation, STOP/revocation/duplicate denied, successful forced kill and clean stop. Audit failures with their earlier READY marker; first-ready and post-kill are different negatives. Keep original rows 15,17,18,22,23,24 and LIB-01..16 unaccepted.

### D-006 team-local verifier status

In the local ChatGPT Debian13/Python3.13 container (no Rust toolchain, QEMU, local Docker, GitHub DNS or full repository checkout), Team D independently computed all four archive SHA-256 and ZIP CRCs and exercised a read-only stdlib Python comparator with `python -m pytest -q test_aegis_d006_compare.py`: **8 passed in 0.04s**. Tests include forged ZIP hash, swapped first/post evidence, fabricated receipt, repeated generation, forged production flag and unsafe ZIP path. These are **artifact-only** checks, not Rust/service, module or signed installed-host test passes.

**No exact-head #255 CI PASS claimed until the actual queued workflows return success. D-006 remains draft / NO-GO.**
