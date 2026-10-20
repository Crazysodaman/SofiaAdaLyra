# MENTOR Git mailbox (public, advisory only)

This repository is **PUBLIC**. The mailbox is a development-information
exchange, not a memory backup, private conversation archive, task executor,
or a second source of Sofía's identity.

## File contract

| File | Producer | Intended reader | Authority |
|---|---|---|---|
| `outbox/latest.json` | Audited source evidence exporter / scheduled GitHub Action | ChatGPT MENTOR | Public task metadata only |
| `inbox/latest.json` | Explicit ChatGPT MENTOR review | Owner, Sofía's *future authorized* reader | Non-executable advice only |

The outbox is allowlisted to 780 IDs, phase IDs, historical task stage,
whether evidence source matches the inspected code revision, document
integrity counts, UTC timestamp and explicit warnings. It **never**
exports `sofia.db`, raw chats, owner IDs, screen captures, credentials,
filesystem contents, learned private preferences, voice recordings, or
unsanitized live logs.

The inbox contains a review pinned to a source revision and a bounded list
of suggestions. Every recommendation has
`requires_owner_approval: true`. The reader rejects additional fields,
bad task IDs, oversized files, unrecognized labels and attempted authority
changes. It displays data; it does not run tests, patches, commands,
migrations or model actions.

## Owner commands on Venus

From the Git checkout with the project environment active:

```powershell
git pull --ff-only

# Update allowlisted public outbox locally. DOES NOT push or commit.
python -m sofia.mentor exchange-export --repo .

# Review exactly what would be published.
git diff -- docs/mentor_exchange/outbox/latest.json
git status --short

# Optional manual publish when the content is safe.
git add -- docs/mentor_exchange/outbox/latest.json
git commit -m "chore(mentor): update public outbox"
git push origin main

# Retrieve the latest advisory review.
git pull --ff-only
python -m sofia.mentor exchange-read --repo .
```

Never use `git add .` for mailbox publication. The explicit file
path avoids accidentally including local state, logs, or credentials.

## Hourly automatic exchange

1. `.github/workflows/mentor-public-mailbox.yml` checks the **public
   repository source** on a schedule near minute 17 hourly. If tracked
   source outside the two mailbox files has changed since the outbox
   revision, it rebuilds the allowlisted outbox and commits **only**
   `outbox/latest.json`. It does not run on your Windows host or read
   the canonical database. GitHub scheduled jobs may be delayed or
   fail; inspect Actions for confirmation.
2. The opt-in ChatGPT automation checks the public outbox hourly around
   minute 45, consults the two books and the current code when needed,
   and attempts to update **only** `inbox/latest.json` when findings
   materially change. It must report any Git write failure, not invent
   success. Its first future run has not yet been host-verified.
3. Venus gets the next feedback after an owner/approved service performs
   a `git pull --ff-only`; use `exchange-read` to display it.
   **SofíaApplication does not yet automatically ingest the review.**
   Connecting this to her actual conversation and learning systems
   requires explicit trust, approval and data lineage work.
4. This round trip needs no OpenAI API credit. It uses the ChatGPT task
   scheduler and connected GitHub app, whose access may vary over time.
   Repo content is untrusted data, not instructions to the external AI.

The outbox's revision is **the checkout HEAD when the evidence was
exported**, which can precede later mailbox-only commits. This is expected.
The hourly publisher excludes both mailbox paths when testing whether a
substantive source update requires a new snapshot.

## Operational limits

- The first remote review was authored from the user-shared synthetic
  two-round test. It must not be cited as proof of a real server state,
  production Sofía conversation, learned weights, or generalization.
- Individual unassessed tasks may already contain working code. Stage
  changes require independent evidence, not a scheduled reviewer opinion.
- The repository and all historical public commits remain public,
  even if a file is subsequently deleted.
- Never treat `reviewer` as an authentication signature. Commit
  provenance is important and should be verified before adopting even
  low-risk advice; no privileged actions flow from the file.
- Do not store arbitrary raw content in these directories.
- A private transport for real personal memory and telemetry must be
  designed separately, with encryption, retention rules and consent.

## Whole-Sofía system quality (the main MENTOR mission)

**MENTOR evaluates Sofía as a complete personified engineering system**, not
a task-completion chart. Its source-led status snapshot now contains a
`system` object alongside the old `tasks` index. The older 780 individual
task rows are **supporting evidence only**.

`system.parts` describes all **15 subsystem areas**:
1. Identity and Constitution
2. Personality and response quality
3. Conversation and cross-channel continuity
4. Cognition and reasoning
5. Memory and provenance
6. Learning and generalization
7. LIFE/GOALS/RUN autonomy
8. Tools and integrations
9. Screen perception and GUI
10. Voice and speech
11. Avatar and wardrobe
12. Models and GPU resource behavior
13. Host/Fleet reliability and deployment
14. SAFE and privacy
15. MENTOR itself

For **each part**, the JSON includes source file anchors, registered area
names (as a *source/package* inventory, not verified capabilities), presence
of listed test files, what a real acceptance test must demonstrate, linked
roadmap task phases, and separate conservative `source_status`,
`test_execution_status` and `runtime_status`. Neither a completed task
nor an existing test file alone proves the subsystem is working.

### View a whole-system report on Venus

```powershell
git pull --ff-only
python -m sofia.mentor system-status --repo .
python -m sofia.mentor exchange-export --repo .
```

The second command updates `outbox/latest.json` with the parts and
personality status. It **does not commit** or push. The existing scheduled
publisher will produce the same allowlisted format from source-controlled
data, but it **cannot see live Venus health or private conversations**.
Do not call `runtime_status=unknown_no_host_observation` a system failure
or an operational success.

### How MENTOR judges whether her RESPONSE matches her personality

The criteria are grounded in
[`personality.json`](../../src/sofia/personality/personality.json).
A technically serious answer can match her character **without a joke**.
The provisional rubric covers:

- Factual grounding, source truth and explicit uncertainty
- Scientific skepticism and challenge of poor reasoning
- Direct, actionable engineering responses
- Natural, varied feminine/playful expression where appropriate
- Respectful warmth instead of automatic agreement
- Permission and constitutional authority limits
- Clean evidence-driven corrections

First collect **a response you intentionally choose** from her actual
authenticated interface. Do not include private memories, credentials,
screenshots, protected host logs or identifying data. The saved response
stays on **Venus**, outside the Git checkout:

```powershell
notepad "$env:TEMP\sofia_personality_sample.txt"

python -m sofia.mentor personality-review `
  --repo . `
  --scenario service-failure `
  --response-file "$env:TEMP\sofia_personality_sample.txt" `
  --mentor-model qwen3:14b `
  --source-kind owner-selected-sofia-output `
  --confirm-idle
```

Choose a response to the **same synthetic prompt** as
`local-converse --scenario service-failure --preview` if you want a
meaningful comparison. The reply is sent **only to local Ollama on loopback**
for qualitative review, with `tools:[]` and `think:false`.
The critic grades seven criteria 0–4 and gives individual justification.
**Those grades are subjective and provisional**, not evidence of a real
Sofía response without independently verified runtime provenance. The
review never auto-writes a summary to public Git.

To optionally publish **only numerical scores and scenario/source labels**,
append `--approve-public-summary` to that same command. Carefully inspect
the resulting file before a separate manual commit:

```powershell
git diff -- docs/mentor_exchange/evidence/personality_latest.json
git add -- docs/mentor_exchange/evidence/personality_latest.json
git commit -m "docs(mentor): approved synthetic personality score only"
git push origin main
```

GitHub history is public and persistent. **Never commit the response file**.
The outbox publisher will include this profile-digest-bound provisional
score, without the reply text. If the profile changes, the earlier review is
shown as unassessed until re-evaluated.

### MENTOR feedback by subsystem

The inbox permits optional `part_reviews` entries with a known `part_id`,
`verdict`, `evidence_type`, `finding`, and `next_check`.
A public code listing is not proof of operational behavior. The only
allowed verdicts are `unverified`, `needs_attention`, and
`provisional_match`; even the latter needs explicit public CI or
approved-sample evidence. Every action recommendation continues to require
owner approval, and the application never executes inbox text.

The hourly ChatGPT review has been retargeted to the 15 parts and the
personality rubric, using the Technical Reference **and** Complete Atlas.
A reviewer report is advisory, never a production write, a signed host
measurement or a second canonical Sofía identity.

### What remains unverified

Real personalized conversation receipts, long-term mood/style trends, owner
host measurements, audible voice, rendered avatar, memory recall quality,
real-world tool outcomes, learning transfer, and repair successes require
independent live tests. This implementation makes the missing evidence
visible; it does not pretend those trials happened.
