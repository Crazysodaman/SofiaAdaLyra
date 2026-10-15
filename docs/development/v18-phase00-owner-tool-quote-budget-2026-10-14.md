# CA-1203/CA-1208: owner-selected tool response model context budget

Date 2026-10-14. A tool selected by the owner is executed at the SAFE
gateway and its result formatter can already produce up to 32,000 text
characters. Even when credentials and tool authority are correctly
separated, allowing that entire formatted diagnostic/log body into a
small model route crowds out the owner's question and authoritative
state. A tool's successful transport is not proof that the model saw
all of its result.

The application conversation's real owner-direct tool reply caller
now caps the USER-role quoted tool result JSON at 4096 UTF-8 bytes.
The full result remains in its canonical tool execution/result owner;
model context gets either the complete tool-output field or a typed
excerpt with `complete:false`, `omitted_characters` and a reason.
No new status or action receipt is invented, no capability is
re-invoked and `allow_tools=False` remains enforced for this reply.
The JSON escaping handles malformed Unicode and adversarial backslash
inflation. Original format headers at the beginning are retained but
do not establish a verified success claim.

This is a narrow source budget, not complete end-to-end provider
token accounting, not an assertion that a model can handle malicious
text safely, and not a Gate 4 acceptance receipt.
