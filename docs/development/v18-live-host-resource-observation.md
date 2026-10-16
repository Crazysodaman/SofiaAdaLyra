# V18 supervised resource sampling for CA-002, CA-007, CA-906, CA-911

Status: host-observation tool implemented; **task-specific Gate 4 not earned**.

`sofia.verify.v18_live_resource_probe` is a read-only tool that an operator can
execute on an existing Git checkout on Venus or Artemis. It stores only
resource percentages, byte counts, timestamps and the exact Git revision.
It never captures a screen/audio stream, dumps process arguments or contents,
opens sofia.db, changes services or loads a model.

Requires optional `psutil` for **global host** CPU/RAM and optional
`nvidia-smi` for one GPU's utilization, VRAM and power. Unavailable sensors
remain `null`. A machine label (`venus`/`artemis`) or scenario label
(`gaming`/`idle`/`conversation`) is declared by the operator and
**not independently authenticated**. It does NOT measure Sofía-specific
process CPU/RAM, model reply latency, model wakeups, memory recall correctness
or avatar/voice output. It cannot self-issue a Gate 4 receipt.

From the real machine's approved repository checkout, after selecting one
fixed Git SHA:

```powershell
$sha = (git rev-parse HEAD).Trim()
python -m sofia.verify.v18_live_resource_probe --repo . --expected-revision $sha --host-role venus --scenario idle --samples 20 --interval-seconds 5 --output venus-idle-resource.json
```

For independent evidence, additionally verify host identity and scenario
using authorized operator observations and approved capture tooling.
Repeat explicitly for gaming and conversation; use real response timing,
owner-approved voice/avatar/Discord traces, longer idle windows and the
multi-day restart protocol where the original tasks demand them. Do not
misrepresent these resource snapshots as CI-host or application-specific
performance proof. Review samples and privacy before sharing.

Tests: `test/test_v18_live_resource_probe.py` on both Linux and Windows,
including unmeasured sensors, revision mismatch, changed checkout,
GPU absence, malformed telemetry, scenario spoofing and bounded sampling.

## Optional process-level performance attribution

The operator can now explicitly supply `--process-pid 1234` to record the
selected process's resident memory and CPU utilization in addition to the
global measurements. The tool never searches for processes, inspects process
arguments, stores a process name, or independently claims the PID belongs to
Sofía. It uses the process's original creation time to reject PID reuse,
records cumulative CPU-time differences over a monotonic sampling interval,
and permits more than 100% CPU where the process uses multiple cores. The
initial process CPU sample is `null`, not a fabricated zero. Missing psutil,
a terminated process, invalid counters or PID reuse fail closed.

The operator must supervise the actual process identity and collect the
explicit CPU/RAM, model, and scenario evidence required by CA-002/911. This
is instrumentation, **not** independently authenticated host acceptance.
