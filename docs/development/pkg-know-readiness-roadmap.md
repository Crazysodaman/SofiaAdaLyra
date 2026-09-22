# PKG-KNOW | documents, reference knowledge, and provenance

**Planning date:** 2026-09-22. **Status:** documentation contract only. No new ingestion/indexing deployment is created by this document.

## Outcome

Give Sofía a source-grounded reference layer for manuals, PDFs, code/documentation, project notes, schematics, API references, repository docs and later approved web research. KNOW answers "what do trusted sources say?" while MEM answers "what happened in Sofía's/user relationship and durable experience?"

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

## Tool-building support

KNOW exposes versioned documentation evidence to DEV/INTEGRATE. A tool candidate should point back to the exact documentation that justified its inputs, outputs, protocol assumptions and constraints.

If the docs later change, KNOW marks dependent tool contracts potentially stale so INTEGRATE/DEV/VERIFY can re-evaluate them.

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
10. update/withdraw derived knowledge when the source is corrected, revoked or deleted.
