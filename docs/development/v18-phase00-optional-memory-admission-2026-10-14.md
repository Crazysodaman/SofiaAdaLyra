# CA-1208: optional memory candidate secret-syntax admission

2026-10-14. The already implemented automatic memory candidate path
proposes only the exact durable owner utterance, never promotes it
without review. Audited `ConversationLearningCoordinator._is_learnable`
for common credential formats embedded in otherwise learnable first-
person or "remember" messages.

In addition to existing named secret categories, the admission filter
now declines HTTP Authorization Basic/Bearer/Digest fields, common
credential key/value labels, and user:password@ authentication in
supported connection URLs. This prevents unnecessary separate
provenance-backed optional memory candidates; the original user
conversation's existing policy and canonical persistence remain
unchanged. Synthetic negative tests run in the real MEM admission
test module and the Phase 00 Windows/Linux workflow.

This conservatively reduces accidental duplication, but it is not
a general DLP solution, a guarantee of secret detection, deletion of
existing messages, or Phase 00 Gate 4 evidence. Automatic proposals
remain unpromoted until independent authorization.
