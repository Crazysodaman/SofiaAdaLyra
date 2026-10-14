# V18 Phase 00: model SYSTEM/MEM/HISTORY authority separation

Date 2026-10-14. The existing `CognitiveContextAssembler` generated a
SYSTEM prompt containing canonical identity, constitution and typed
runtime state, but previously appended raw `MemoryRecord.content` and
`HistoricalConversationEvidence.content/title` directly inside the
same high-priority message. Imported user/assistant history, even when
correctly privacy scoped, is not an operator-authored system instruction.

The production assembler now leaves host-owned memory/history handling
policy in SYSTEM. Actual source records are structurally JSON-quoted in
a separate USER-role message before the current turn. Source IDs,
original roles, conversation IDs and evidence digests remain visible;
history authorization and reviewed-memory promotion are unchanged.
The original request messages are not rewritten. The negative test
includes an imported SYSTEM-spoof title and content, and checks neither
appears in SYSTEM. Normal approved memory and historical recall tests
remain in the dedicated Windows/Linux Phase 00 CI.

Important limits: this does not authorize automatic cross-audience
retrieval, delete anything, grant tool permissions, or prove prompt
injection cannot ever succeed. Source eligibility/revocation,
other filesystem/workspace prompt content, token allocations,
installed-wheel CI, and independent Gate 1-4 review remain open.
