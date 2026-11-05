# Hybrid CA task register: conservative source-to-release reconciliation

This register is derived from the reviewed **700 original CA task records** in
`V18_700_TASK_OWNER_CROSSWALK_2026-11-02.csv`. Run:

```bash
python tools/hybrid_task_register.py --audit
python tools/hybrid_task_register.py
python -m pytest -q test/test_hybrid_task_register.py
```

The JSON output preserves all original IDs, primary ownership, historical
coding classification, source anchors, and a **proposed** hybrid destination.
The register deliberately maps no G or R gate without task-level evidence.
Every task has `acceptance: NOT_VERIFIED` and no implementing SHA until
independent provenance and tests establish otherwise.

The 40 ML and 40 GA supplemental items are tracked **separately**. The
`supplemental_ml_ga_task_count: 80` is a scope reminder, **not** 80 claimed
completed or individually reconciled task records.

Do not use this source-coding inventory as proof of installed-artifact
correctness, owner approval, physical G8 acceptance, Rust migration
completion, or GO LIVE authorization. Future evidence updates must preserve
all historical fields, record exact SHAs, and be reviewed separately.
