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

## Owner answers to the nine questions, confirmed 2026-10-12

| Task IDs | Confirmed decision | Current implementation boundary |
|---|---|---|
| CA-4906 | Successful summary: delete eligible temporary raw media 24h **after verified summary**. Failed summary: keep trying within 24h **of capture**, then purge raw media and log a non-content failure. Completed creative works require owner cleanup. Cap temporary captures at 2 GiB per host; deny new capture when full. | Summary-to-purge worker, failure quarantine and per-host quota not yet accepted. See `v18-owner-nine-policy-decisions-2026-10-12.md`. |
| CA-5108 | Do not automatically disclose, transfer or erase private memories due to absence/death; require separately authenticated explicit owner instructions. | No estate delegate has been nominated; no legacy trigger may run. |
| CA-404 / CA-410 | Owner approved 22:00–08:00 America/Chicago quiet, up to 15 ordinary social messages/day, at least 30min apart. | Source defaults for *new* OutreachSettings aligned. Existing saved owner overrides not mutated; channel/platform/live acknowledgment remains unverified. |
| CA-3203 / CA-3907 | Max 200,000 estimated optional tokens/day and 1 hour reserved GPU time/day, excluding foreground; at most 5 simultaneous research experiments and 15 unresolved hypotheses, owner revisable. | New optional budget defaults aligned; actual host measurements and research portfolio count enforcement still unverified/not fully implemented. |
| CA-3103 / CA-5207 / CA-6108 | Independently protected/offsite recovery copy; two owner-held **offline recovery-key copies**; exact location only during approved deployment planning. | Storage/keys/site and RPO/RTO actual rehearsal not provisioned or verified. Existing two encrypted snapshots/destination remain distinct. |
| CA-105 / CA-3507 | Self-directed bounded creative work and honest independently checkable outcome claims are already approved in principle, without arbitrary subjective quality scoring. | Further measurable appraisal research, proof and safe source work are engineering tasks rather than an open yes/no owner policy question. |

## Owner design queue: resolved for the current nine choices

All nine requested owner policy values were explicitly answered on 2026-10-12. Do not repeat the questionnaire. Full source of truth: `docs/development/v18-owner-nine-policy-decisions-2026-10-12.md`.

**Remaining engineering and future deployment decisions are not nine unanswered policy questions:** implement and verify timed media cleanup and quota; carry 5/15 research limits into a real scheduler; reconcile stored user settings under a supervised saved-settings change; select and verify offsite copy location, key custody and measured recovery; obtain hardware test evidence; choose any owner-specific subjective artwork rating rubric only if actually needed. Do not infer execution, safe erasure or live rollout from a GitHub document.

Global V18 task statuses remain Workstream 1's responsibility. Live hosts, canonical state and previously saved user options remain untouched.
