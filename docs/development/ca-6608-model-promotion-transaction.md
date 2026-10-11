# CA-6608: operator-fenced model role promotion and recovery transaction

The previous `prepare_model_role_change` module validated independent
model evaluations and produced an immutable plan, but did not have any
persistent model-promotion execution receipts. A restart at any point between
role settings storage and runtime/provider activation could lead to
untraceable state or a repeated model swap.

The production `promote_prepared_model_role` path now requires all four
independent host-broker functions: verify current owner approval, writer
fencing and installed candidate; drain in-flight turns for the role;
apply the real runtime settings; independently test provider health and
conversation continuity. The LLM cannot authorize those callbacks.

After approval and drain, the existing canonical `RuntimeUserSettingsStore`
writes the reviewed model role **with** a durable `applying` receipt in
one SQLite `BEGIN IMMEDIATE` transaction. The transaction compares the
original exact settings bytes to the review's SHA-256, preventing stale
model proposals from overwriting another operator's settings. A uniquely
bound approval reference cannot be reused for another role/candidate.
After the broker activates and checks the candidate, the canonical receipt
is recorded as `accepted`.

On failed health or provider transition, the original role mapping is
restored **only if** the candidate settings still match the proposal's
exact digest. The host broker must independently restore the previous
provider state too. Only when BOTH recoveries succeed does the receipt
become `rolled_back`. Otherwise it stays `uncertain`, blocks any replay,
and requires host operator reconciliation. Interrupted `applying` receipts
also block automatic re-execution after a crash.

The previous model is retained as the explicit rollback target. Neither
constitution, identity, memory, conversation audience, SAFE grants nor the
writer location can be changed by this transaction. The function does not
install software or self-authorize a model; production invocation depends on
a separate privileged host approval and runtime reload hook.

Regression cases were written for successful source commit, rollback,
missing approval, compare-and-swap conflict, and interrupted promotion.
**Tests were not run, no Ollama models were loaded or switched, and no
live host configuration was changed.** CA-6608 remains partially wired
pending actual host callback integration and supervised acceptance.
