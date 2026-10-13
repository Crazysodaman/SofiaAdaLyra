# V18: Owner-question reconciliation, 2026-10-12

Checked against docs/Sofia_V18_700_Tasks_Brief_Table.md, the original V18 master, available GitHub main source/reports and prior owner decisions. **Owner policy resolution is separate from production wiring, tests, CI and live acceptance.** Workstream 1 owns the canonical docs/development/v18-task-evidence.json; do not alter its statuses from design approvals.

## Already answered: do not re-ask

| Original CA requirements | Owner decision and boundary |
|---|---|
| CA-3102, CA-3701, CA-3103, CA-5207 | Venus sole canonical writer now; future Sofia Debian guest writer only after supervised independent fence; CA-3103 Option B **RPO <= 300 seconds, RTO <= 3600 seconds**, as *targets*, not proven replication. See v18-ca-3103-recovery-objectives-decision-2026-10-12.md. |
| CA-3106, CA-3107, CA-2918 | Existing owner-created Hephaestus VM, dedicated Internal host-to-guest isolated link, no NAT/LAN; independent Artemis host recovery controller; live changes remain separately approved. See docs/ops/HEPHAESTUS_OWNER_CREATED_HYPERV.md. |
| CA-6501, CA-6505, CA-4608 | Sofía may learn and act safely without auto-expanding authority. CA-6505 Option B: 10 independently verified original same-scope Level 3 successes to **propose** at most a seven-day grant; owner FIDO2 still required. See v18-ca-6505-owner-approved-autonomy-graduation-2026-10-12.md. |
| CA-5305, CA-403 | **B: Hybrid** Main plus separately linked activity stream; Sofía can voluntarily share meaningful verified LIFE discoveries without asking for each ordinary update, or remain silent. See v18-ca-5305-hybrid-main-activity-decision-2026-10-12.md. No completed UI asserted. |
| CA-3407, CA-5607 (scoped deletion/backup portion) | Owner selected specific memory-candidate deletion Option B, and two encrypted backup snapshots per destination; no blanket asset/provider deletion. See memory-deletion-retention-policy.md. |
| CA-3203 (model residency portion) | Gaming takes priority; independently verified desktop idle for 30 minutes before capacity-aware on-demand/preload. No automatic model downloads/fallbacks. This does not answer daily inference/research budgets. |
| CA-105 (independent creative choice), CA-3507 (objective evidence) | Independent LIFE goal/artifact critique, bounded revision and verified success principles are approved, without automatic permission grants. Their full coding/CI evaluation matrix remains unfinished; no need to re-ask whether Sofía can work creatively on her own. |

## Owner-policy parameters still not established

| Tasks | Narrow unanswered parameter | Existing implementation or conservative default |
|---|---|---|
| CA-4906 | **Owner preferred direction (2026-10-12):** after an authorized, accurately grounded, durable memory summary, delete eligible temporary raw media. Exact grace period, quota, ineligible/sensitive-capture behavior and separate completed creative-original preservation are *not yet numerically settled*. | See `v18-ca-4906-media-summary-then-delete-preference-2026-10-12.md`. Capture consent remains independent, candidate erasure is not media deletion, and two backup snapshots do not prove raw-media purge. |
| CA-5108 | Optional digital legacy trustee, destruction or post-mortem/death/absence delegation. | **No third-party disclosure or automatic destruction** without exact independent future owner instructions. Not a blocker for ordinary private operation. |
| CA-404, CA-410 | Owner has approved discretionary outreach but not separately confirmed the numeric quiet-time and notification frequency settings. | Source OutreachSettings defaults: quiet 22:00–08:00 America/Chicago; max 1 ordinary/social outreach per day, 360-minute social interval; separately governed critical operational alerts may bypass quiet. These are CODE DEFAULTS, not newly approved personal preferences. |
| CA-105, CA-3507 | Any owner-specific subjective artistic quality thresholds or custom cost overrides. | Source-based objective validation and bounded projects; use engineering-configured safe caps, avoid inventing owner ratings. |
| CA-3203, CA-3907 | Daily background inference tokens/CPU/GPU caps, concurrent research experiments and maximum unanswered hypotheses. | Existing optional admission credits are estimates; 30-minute idle policy does not settle these limits. Request only if preparing major autonomous workload and no safe measured default suffices. |
| CA-3103 remaining implementation | Independent failure domain, backup key custody, incremental replication method, measured RPO/RTO and storage caps. | Design targets are approved but no operator-approved deployment location or measured live drill. |

## Rationalized remaining question sequence

1. CA-4906: record the **already expressed summary-then-delete preference**, ask only grace period, per-format quota and creative-original exception; separate capture consent.
2. CA-404/410: whether to keep the existing quiet-hour/once-per-day defaults or select custom behavior; do not re-ask about voluntary LIFE messages.
3. CA-3203/3907: numerical optional LLM/research ceilings before enabling substantial new background compute.
4. CA-5108: optional digital-legacy directive later. Remain private and non-disclosing until explicitly authorized.

All entries are owner-decision inventory only; retain conservative source/test/production classifications. No live host, credentials, runtime, model, VM, database writer or user settings changed.

## 2026-10-12 one-batch response format

The owner explicitly requested the **whole remaining owner-decision queue together**, not one question at a time. Group the distinct open policy numbers (media cleanup, allowed captures, outreach numeric limits, inference/research budget, recovery-domain/key custody, optional project subjective rubric, digital-legacy directions) in a single table with existing defaults/recommended options. Do not convert a recommendation to an owner-approved value without a reply. The previously confirmed CA-5305 Hybrid option is not open.
