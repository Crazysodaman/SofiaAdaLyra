# V18 CA-003 / CA-1208: owner-directed tool output remains data

Date: 2026-10-14. The real `ConversationService` owner-direct
desktop tool path previously combined host-owned action and audience
policy with arbitrary `formatted_result` text in a SYSTEM message.
An authorized read-only tool may return an attacker-controlled log,
remote process listing, filename, HTML document, or error. The user's
permission to run the tool is not permission for that output to grant
instructions.

The production caller now emits host-only SYSTEM policy plus a
separate USER-role structured JSON quotation containing the exact
original tool output. The canonical tool-selection/SAFE permissions,
session persistence and `allow_tools=False`/empty capability
allowlist remain unchanged. No new tool can be requested on the
resulting model turn. A negative test confirms a spoofed SYSTEM
instruction stays within untrusted quoted data. This patch does not
create a second result database or assert that returned content is
independently verified.

Remaining Gate 4: task-specific installed-wheel Windows/Linux proofs,
hostile remote tool payload audit, size/resource-budget tests, exact
approval/receipt lineage, full original Phase 00 acceptance and
independent source/security review.
