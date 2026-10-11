# V18 CA-5603: exact source retrieval with bounded memory

Source audit: `ConversationOriginalRetriever.retrieve()` previously
called `ConversationStore.list_messages(session_id)`, which materialized
the **entire original session** into Python, even when the request needed
only one or two exact IDs. This became unbounded as transcripts grew, and
unnecessarily transported other message content into a memory component.

The canonical `ConversationStore.exact_originals` now uses one indexed,
session-scoped SQL query with a bounded list of at most 128 exact message IDs.
The source-position subquery preserves the actual zero-based position in
`ORDER BY created_at,id`, including tied timestamps. The original IDs,
roles, contents, timestamps, and absence behavior remain unchanged.
`ConversationOriginalRetriever` assembles only the requested messages,
preserving caller-specified ID order, duplicate-ID elision, missing-ID
non-disclosure, and a strict character budget that never truncates
an original. The existing application/session owner remains responsible
for authenticating a session; this optimization creates no parallel
memory authority and never builds a hidden cache or alternate database.

The ConversationStore already has indexed keyset pagination for incremental
hot history. This closes the concrete full-materialization problem for exact
original retrieval; archive time-range pagination, all backend integrations,
and full end-to-end acceptance under CA-5603 remain separate work.

Regression cases were authored for 160-original sessions with the old
full-list method forbidden, timestamp ties, and bounded source IDs.
**No test suite, CI, host process or filesystem migration was run.**
