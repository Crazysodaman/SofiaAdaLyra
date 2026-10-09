# KNOW v2 hybrid retrieval

KNOW v2 uses the canonical `sofia.db`; it does not introduce a second
authority database. `knowledge_document`, lifecycle, access policy, structured
sections, FTS5, optional embedding vectors, graph edges, and cognition-v2
evidence references all retain document/section provenance.

The ingestion path hashes the source bytes and each section, preserves headings
and metadata, records page/line locators, and indexes bounded sections. An exact
source/hash/version is idempotent. A changed source creates a new document
revision and marks the prior revision superseded rather than deleting history.

Retrieval combines FTS5/BM25, exact phrase/identifier matching, deterministic
token overlap, and an optional host-provided embedding score. Candidates are
deduplicated by section ID, reranked, bounded, checked against active document
revisions, and filtered by the requesting principal/audience before any content
is returned. Embeddings influence ranking only; they do not grant access or
establish a fact.

The small knowledge graph contains only traceable edges extracted from section
headings and explicit document links. Every edge names its source document and
section. It is a retrieval aid, not an independent truth store.

Matrix v2 maps KNOW turns to a scoped `knowledge.retrieval` need. The production
`KnowledgeEvidenceCoordinator` invokes the existing read-only
`knowledge.search` capability with current principal metadata and records the
eligible results through `EvidenceAcquisitionCoordinator`. This preserves the
invariants that retrieval is not permission, model output is not evidence, and
private sources cannot cross audience boundaries.
