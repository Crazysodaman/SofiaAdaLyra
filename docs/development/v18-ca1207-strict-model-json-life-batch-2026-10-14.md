# V18 CA-1207 / CA-2307: shared strict model JSON parsing

Date: 2026-10-14. On main only. No live Venus/Artemis mutations.

## Scope and production wiring

Before this change, Ollama tool arguments checked duplicate keys, non-finite
numbers and resource limits, while LIFE `ProjectIdeaAgent`,
`ProjectDraftAgent` and `ProjectOutreachChoiceAgent` independently used
permissive standard JSON decoding. A model response containing duplicate
`pursue`, `share_now`, `content` or other keys could be interpreted with
last-wins semantics. These are untrusted choices, not authoritative truth.

The shared pure parser `sofia.cognition.strict_json.loads_strict_model_json`
is now used by the existing production provider and the three real LIFE
model-entry callers. Each caller retains its original UTF-8-size bounds,
tool-free policy, typed schema, errors, and downstream authorization.
The parser does not execute instructions or authorize a project or outreach.
It rejects duplicate keys at every nesting level and NaN/Infinity, and
preserves ordinary nested JSON without loss. The actual safety gate for
externally consequential actions remains SAFE/ACT.

## Regression coverage

`test/test_life_strict_model_json.py` exercises valid UTF-8 JSON,
duplicate/conflicting keys, nonstandard floats, real project-idea evidence,
a real LIFE draft and opt-in private outreach. The earlier
`test/test_ollama_malformed_response_boundary.py` covers the provider's
identical parser and bounded tool argument contract.

## Open gates

These changes are source-coded only. They require exact-commit regression
execution on Linux/Windows, installed-wheel provider and LIFE regressions,
and separate supervisor-approved live acceptance where the original tasks
demand it. This batch does **not** change CA evidence to accepted and does
not assume that adding tests alone completes CA-1207 or CA-2307. Recovery
needs no schema change or persistent migration; rollback is a Git revert.
