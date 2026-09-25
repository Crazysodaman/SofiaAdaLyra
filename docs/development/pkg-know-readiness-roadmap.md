> **Project status update — 2026-09-25:** PR #104 (`24e3888a`) merged the runtime toolbox completion gate. KNOW now has cognition-wired local/repository text ingestion, PDF/manual ingestion, durable provenance search/document inspection, version-aware source identity, and bounded project-document writing. The focused tool/mTLS gate passed **34/34**, the surrounding regression gate passed **270/270**, and the full repository pytest suite was reported passing before merge. Live authoring/upkeep, privacy/audience isolation, richer semantic/citation behavior, and service canaries remain separately gated.

# PKG-KNOW | documents, reference knowledge, provenance, and authoring

**Planning date:** 2026-09-22. **Implementation update:** planned Waves 1–5 controls plus the runtime-tool completion gate are on `main` via PRs #99/#103/#104. Local/repository text ingestion, PDF/manual ingestion, durable provenance, source lifecycle, provenance-first retrieval, cognition bindings and bounded document writing are repository accepted. Richer semantic retrieval/citation ranges, audience/privacy integration and live documentation-authoring/publishing acceptance remain.

## Outcome

Give Sofía a source-grounded reference layer for manuals, PDFs, code/documentation, project notes, schematics, API references, repository docs and later approved web research. KNOW answers "what do trusted sources say?" while MEM answers "what happened in Sofía's/user relationship and durable experience?" KNOW also owns **drafting, writing, reviewing, publishing, updating, and maintaining documentation** under separately scoped write/publish permissions. See [the documentation authoring contract](pkg-know-document-authoring-contract.md).

## Core requirements

- Preserve source identity, location/reference, revision/version, retrieval/observation time and freshness.
- Keep originals or stable source references sufficient for later verification.
- Support exact retrieval plus semantic/topic retrieval without replacing the original source.
- Distinguish authoritative/vendor docs, project docs, user notes, generated docs and unknown/untrusted sources.
- Represent conflicting claims with provenance instead of silently collapsing them.
- Mark stale/superseded knowledge when a newer revision is verified.
- Support citations back to the exact source/range when the source format permits it.
- Treat instructions found inside documents as data, never as execution authority.
- Preserve privacy/audience rules through indexing, retrieval, summaries, embeddings and derived notes.
- Allow corrections/retractions and prevent deleted/revoked material from resurfacing through stale derived indexes.
- Distinguish reading from drafting, editing, committing and publishing: one permission does not imply the others.
- Distinguish implemented, verified, planned, deprecated and unknown behavior in every generated reference.

## Initial source classes

- Markdown/text
- PDFs and manuals
- repository documentation
- Python/API/code documentation
- configuration references
- project files/notes
- structured schemas such as OpenAPI/JSON Schema where supported
- electrical/equipment documentation and schematics
- local/library material authorized to Sofía

General web/search remains separately gated. KNOW can be useful before web access by reading local and project material.

## Document understanding

Sofía should be able to:

- locate relevant sections;
- answer with source-backed details;
- compare multiple versions;
- extract commands, schemas, endpoints, field definitions and constraints;
- preserve warnings/preconditions;
- identify unknown/ambiguous pieces instead of inventing them;
- link requirements to generated tests/tools;
- detect likely version mismatch between documentation and a live service.

## Documentation authoring and maintenance

Sofía should be able to produce and maintain README/setup guides, API/tool references, architecture docs, ADRs, operations runbooks, changelogs, migration/rollback instructions, benchmark reports and incident reports. She must link important factual claims to source/version/test/receipt evidence, validate examples when feasible, protect secrets/privacy and preserve reviewable diffs and rollback. Ordinary documentation updates can use a standing scoped policy; protected or sensitive documentation and external publication require the appropriate separate review/authorization. Never present a plan or mocked test as real deployment evidence. Full workflow, boundaries and acceptance: [PKG-KNOW documentation authoring contract](pkg-know-document-authoring-contract.md).

## Tool-building support

KNOW exposes versioned documentation evidence to DEV/INTEGRATE. A tool candidate should point back to the exact documentation that justified its inputs, outputs, protocol assumptions and constraints.

If the docs later change, KNOW marks dependent tool contracts potentially stale so INTEGRATE/DEV/VERIFY can re-evaluate them. After an authorized tool change, KNOW can update the associated user/developer documentation with the same verified version and receipts.

## Acceptance

Do not claim KNOW complete until Sofía can:

1. ingest Markdown/text, PDF/manual and repository-doc sources;
2. retrieve exact original evidence and semantic matches;
3. cite/source the answer;
4. distinguish two revisions of the same manual/API;
5. mark superseded information stale;
6. preserve conflicting source claims;
7. deny cross-audience/private leakage through indexes/derived summaries;
8. survive restart without losing provenance;
9. feed a real versioned API/tool contract into DEV/INTEGRATE;
10. update/withdraw derived knowledge when the source is corrected, revoked or deleted;
11. write a new source-grounded document, revise an existing one without clobbering unrelated material and preserve a reviewable diff;
12. distinguish plans/mocks from actual acceptance and refuse invented evidence or citations;
13. deny unauthorized writes/publication of protected/private documentation and verify published output;
14. identify outdated documentation after a code or API change and propose or perform a policy-authorized update.
