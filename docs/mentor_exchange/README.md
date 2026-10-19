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
