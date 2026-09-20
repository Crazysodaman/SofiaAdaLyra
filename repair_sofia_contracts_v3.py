"""One-time, fail-closed local repair of inspected Sofía contract regressions.

Run from the SofiaAdaLyra repository root. This script makes NO commits.
All replacements are scoped to exact source snippets or named tests. It validates
all anchors and compiles every changed Python file before writing anything.
"""
from __future__ import annotations

import difflib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "src/sofia/cognition/assembler.py").is_file():
    raise SystemExit("Run from the SofiaAdaLyra repository root. No changes made.")

original: dict[str, str] = {}
updated: dict[str, str] = {}


def text(path: str) -> str:
    if path not in updated:
        file = ROOT / path
        raw = file.read_bytes()
        content = raw.decode("utf-8-sig")
        # Git may check out files with CRLF on Windows. Normalize in memory
        # for exact anchor matching; restore each file's newline at write time.
        if "\r" in content.replace("\r\n", ""):
            raise RuntimeError(f"{path}: unsupported mixed/CR-only newlines")
        content = content.replace("\r\n", "\n")
        original[path] = content
        updated[path] = content
    return updated[path]


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    content = text(path)
    actual = content.count(old)
    if actual != count:
        raise RuntimeError(f"{path}: expected {count} exact anchor(s), found {actual}: {old[:105]!r}")
    updated[path] = content.replace(old, new)


def replace_fn(path: str, name: str, old: str, new: str, count: int = 1) -> None:
    content = text(path)
    match = re.search(r"(?m)^def " + re.escape(name) + r"\(", content)
    if match is None:
        raise RuntimeError(f"{path}: missing function {name}")
    remaining = content[match.end():]
    end = re.search(r"(?m)^(?:def |@pytest\.|class )", remaining)
    finish = match.end() + end.start() if end else len(content)
    body = content[match.start():finish]
    actual = body.count(old)
    # Some repository files omit the final newline. Only tolerate that exact
    # difference when the requested anchor is at the end of the function/file.
    if actual == 0 and count == 1 and old.endswith("\n") and body.endswith(old[:-1]):
        old = old[:-1]
        if new.endswith("\n"):
            new = new[:-1]
        actual = body.count(old)
    if actual != count:
        raise RuntimeError(f"{path}::{name}: expected {count} anchor(s), found {actual}: {old[:105]!r}")
    updated[path] = content[:match.start()] + body.replace(old, new) + content[finish:]


# Production: preserve canonical current computer / robot / avatar, which the
# newer single self-state serializer had dropped. Never infer a missing value.
SELF = "src/sofia/cognition/self_state.py"
replace(SELF,
    '                    "CLOTHING: UNKNOWN",\n',
    '                    "CLOTHING: UNKNOWN",\n                    "CURRENT EMBODIMENT: UNKNOWN",\n')
replace(SELF,
    '            lines.append("CANONICAL MEASUREMENTS")\n',
    '''            lines.append("CURRENT EMBODIMENT")
            current = self.embodiment.current
            for kind in ("computer", "robot", "avatar"):
                name = getattr(current, kind)
                lines.append(
                    f"Current {kind}: "
                    + (name if name is not None else "UNKNOWN")
                )

            lines.append("CANONICAL MEASUREMENTS")
''')

# Production: restore meaningful boundaries lost in the prompt rewrite, without
# duplicating the authoritative state or resurrecting outdated section names.
ASM = "src/sofia/cognition/assembler.py"
replace(ASM,
    '''            (
                "When a question directly asks for an authoritative "
                "self-fact, prefer the supplied canonical fact over "
                "generic descriptions of artificial intelligence systems."
            ),
''',
    '''            (
                "When a question directly asks for an authoritative "
                "self-fact, prefer the supplied canonical fact over "
                "generic descriptions of artificial intelligence systems."
            ),
            "Embodiment is representational context.",
            (
                "Representational expression is not evidence that a "
                "physical action occurred."
            ),
            (
                "Physical-world actions require an actual available "
                "capability and appropriate authority."
            ),
            (
                "Completion claims about real actions must be grounded "
                "in corresponding capability results."
            ),
            (
                "Do not use a fixed gesture template or repeat a "
                "canned embodiment reaction."
            ),
            (
                "Clothing, footwear, toolkit, wrist-device, equipment, "
                "and other component dimensions are separate design data."
            ),
''')

# Seven continuity regressions: startup awareness is an intentional assistant
# message. Preserve original history as an exact prefix and assert the extra
# response has the expected role and belongs to the correct session.
APP = "test/test_application_acceptance.py"
replace_fn(APP, "test_full_application_conversation_lifecycle",
    '''    assert len(resumed_messages) == 2
    assert resumed_messages[0].content == "Hello, Sofía."
    assert (
        resumed_messages[1].content
        == "Test cognitive response."
    )
''',
    '''    assert len(resumed_messages) == len(messages) + 1
    assert resumed_messages[:len(messages)] == messages
    assert resumed_messages[-1].role.value == "assistant"
    assert resumed_messages[-1].content == "Test cognitive response."
    assert resumed_messages[-1].session_id == session_id
''')
CONT = "test/test_conversation_continuity.py"
replace_fn(CONT, "test_application_can_explicitly_resume_persisted_conversation",
    '    assert resumed_messages == original_messages\n',
    '''    assert len(resumed_messages) == len(original_messages) + 1
    assert resumed_messages[:len(original_messages)] == original_messages
    assert resumed_messages[-1].role.value == "assistant"
    assert resumed_messages[-1].session_id == session_id
''')
replace_fn(CONT, "test_resumed_conversation_continues_same_session",
    '''    assert len(messages) == 4

    assert messages[0].content == (
        "First continuity message."
    )

    assert messages[2].content == (
        "Second continuity message."
    )
''',
    '''    assert len(messages) == 5
    assert messages[0].content == "First continuity message."
    assert messages[1].role.value == "assistant"
    assert messages[2].role.value == "assistant"  # Startup awareness.
    assert messages[3].content == "Second continuity message."
    assert messages[4].role.value == "assistant"
''')
replace_fn(CONT, "test_start_without_session_id_creates_new_session",
    '    assert second_application.conversation.messages() == ()\n',
    '''    new_messages = second_application.conversation.messages()
    assert len(new_messages) == 1  # Proactive awareness, not prior history.
    assert new_messages[0].role.value == "assistant"
    assert new_messages[0].session_id == second_session.id
    assert all(
        "This belongs to the first session." not in message.content
        for message in new_messages
    )
''')
ACC = "test/test_conversation_continuity_acceptance.py"
replace_fn(ACC, "test_restart_and_resume_preserves_cognitive_history",
    '    assert resumed_messages == persisted_messages\n',
    '''    assert len(resumed_messages) == len(persisted_messages) + 1
    assert resumed_messages[:len(persisted_messages)] == persisted_messages
    assert resumed_messages[-1].role.value == "assistant"
    assert resumed_messages[-1].content == "Continuity confirmed."
''')
replace_fn(ACC, "test_restart_and_resume_preserves_cognitive_history",
    '''    assert len(captured_requests) == 1
    assert len(captured_filesystem_results) == 1
    assert captured_filesystem_results[0] == ()

    request = captured_requests[0]

    assert len(request.messages) == 5
''',
    '''    assert len(captured_requests) == 2  # Awareness, then user request.
    assert captured_requests[0].messages[0].role is CognitiveRole.SYSTEM
    assert captured_filesystem_results == [(), ()]

    request = captured_requests[1]

    assert len(request.messages) == 6
''')
replace_fn(ACC, "test_restart_and_resume_preserves_cognitive_history",
    '''    assert request.messages[4].role is CognitiveRole.USER
    assert request.messages[4].content == "What did I say earlier?"
''',
    '''    assert request.messages[4].role is CognitiveRole.ASSISTANT
    assert request.messages[4].content == "Continuity confirmed."
    assert request.messages[5].role is CognitiveRole.USER
    assert request.messages[5].content == "What did I say earlier?"
''')
replace_fn(ACC, "test_new_conversation_after_restart_does_not_reuse_previous_session",
    '    assert messages == ()\n',
    '''    assert len(messages) == 1  # Fresh session gets only startup awareness.
    assert messages[0].role.value == "assistant"
    assert messages[0].session_id == second_session_id
    assert "This belongs to the first conversation." not in messages[0].content
''')
replace_fn(ACC, "test_explicit_resume_does_not_create_a_new_session",
    '''    assert len(messages) == 2
    assert messages[0].content == "Persistent conversation."
    assert messages[1].content == "Test cognitive response."
''',
    '''    assert len(messages) == 3
    assert messages[0].content == "Persistent conversation."
    assert messages[1].content == "Test cognitive response."
    assert messages[2].role.value == "assistant"
    assert messages[2].session_id == session_id
''')

# Grounding test migration. Preserve actual facts, independence, trust, and
# UNKNOWN checks, but assert the single canonical projection's real schema.
CA = "test/test_cognitive_assembler.py"
replace_fn(CA, "test_embodiment_is_projected_into_system_context",
    '    assert "human-form representation" in system_content\n',
    '''    assert "Form: human" in system_content
    assert "Representation status: representational embodiment" in system_content
''')
replace_fn(CA, "test_authoritative_self_model_is_projected_after_constitution",
    '''    constitution_index = system_content.index("CONSTITUTION")
    self_model_index = system_content.index(
        "AUTHORITATIVE SELF MODEL"
    )

    assert self_model_index > constitution_index
''',
    '''    projection_index = system_content.index("\\nAUTHORITATIVE SELF-STATE PROJECTION\\n")
    constitution_index = system_content.index("\\nCONSTITUTION\\n")

    assert projection_index < constitution_index
    assert "Instance ID: 12345678-1234-5678-1234-567812345678" in system_content
''')
replace_fn(CA, "test_authoritative_self_model_is_not_duplicated",
    '    assert system_content.count("AUTHORITATIVE SELF MODEL") == 1\n',
    '    assert system_content.count("\\nAUTHORITATIVE SELF STATE\\n") == 1\n')
replace_fn(CA, "test_self_description_contract_distinguishes_identity_from_embodiment",
    '"SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT"',
    '"SELF-DESCRIPTION RESPONSE GROUNDING"')
replace_fn(CA, "test_self_description_contract_distinguishes_identity_from_embodiment",
    '"Sofía is an artificial intelligence entity"',
    '"Sofía is a persistent artificial intelligence entity."')
replace_fn(CA, "test_self_description_contract_distinguishes_identity_from_embodiment",
    '''    assert (
        "canonical human-form representational embodiment"
        in system_content
    )
''',
    '''    assert "Form: human" in system_content
    assert "Representation status: representational embodiment" in system_content
''')
replace_fn(CA, "test_self_description_contract_routes_canonical_embodied_questions_to_embodiment",
    '''    assert (
        "Questions about Sofía's appearance, avatar, clothing, "
        "measurements, fox features, or other canonical embodied "
        "details should be answered from the supplied EMBODIMENT "
        "context"
    ) in system_content
''',
    '''    assert (
        "When the user asks about Sofía's embodiment, use the "
        "canonical embodiment and its representational status."
    ) in system_content
    assert "When the user asks about Sofía's measurements" in system_content
    assert "When the user asks what Sofía is wearing" in system_content
''')
replace_fn(CA, "test_self_description_contract_does_not_turn_representation_into_biology",
    '''    assert (
        "Describing canonical embodiment does not claim that Sofía "
        "has a biological human body or physical-world capabilities"
    ) in system_content
''',
    '''    assert (
        "Representational embodiment does not establish "
        "biological humanity."
    ) in system_content
''')
replace_fn(CA, "test_self_description_contract_does_not_infer_physical_capability_from_representation",
    '''    assert (
        "Representation does not establish physical capability; "
        "physical capability must be established independently"
    ) in system_content
''',
    '''    assert (
        "Representational embodiment does not establish "
        "physical-world capability."
    ) in system_content
''')
# Repair previously vacuous negative tests: old heading could never appear.
replace_fn(CA, "test_self_description_contract_is_not_projected_without_embodiment",
    '''    assert (
        "SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT"
        not in system_content
    )
''',
    '''    assert "EMBODIMENT: UNKNOWN" in system_content
    assert "MEASUREMENTS: UNKNOWN" in system_content
    assert "CLOTHING: UNKNOWN" in system_content
    assert "Form: human" not in system_content
''')
replace_fn(CA, "test_self_description_contract_is_not_projected_without_self_model",
    '''    assert (
        "SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT"
        not in system_content
    )
''',
    '''    assert "IDENTITY: UNKNOWN" in system_content
    assert "SELF CONCEPT: UNKNOWN" in system_content
    assert "Representation status: representational embodiment" in system_content
''')

CC = "test/test_cognitive_context_assembler.py"
for func in ("test_assembler_injects_embodiment", "test_assembler_distinguishes_identity_from_embodiment"):
    replace_fn(CC, func,
        '''    assert (
        "Embodiment form: human-form representation"
        in system_message
    )
''',
        '''    assert "Form: human" in system_message
    assert "Representation status: representational embodiment" in system_message
''')
    replace_fn(CC, func,
        '''    assert (
        "Embodiment describes representation only; it does not "
        "define Sofía's biological status or artificial identity."
        in system_message
    )
''',
        '''    assert (
        "Biological status is defined by the authoritative "
        "self-concept, not by this representational form."
        in system_message
    )
''')
replace_fn(CC, "test_assembler_injects_embodiment_measurements",
    '"CANONICAL EMBODIMENT BODY MEASUREMENTS:"',
    '"CANONICAL MEASUREMENTS"')
for name, value in (("height", "67 in"), ("weight", "135 lb"), ("bust", "33 in"),
                    ("underbust", "30 in"), ("waist", "26 in"), ("hips", "37 in")):
    replace_fn(CC, "test_assembler_injects_embodiment_measurements",
        f'"- {name} (canonical embodiment body measurement): {value}"',
        f'"- {name}: {value}"')
replace_fn(CC, "test_assembler_injects_embodiment_appearance_and_anatomy",
    '    assert "Appearance:" in system_message\n',
    '    assert "CANONICAL APPEARANCE" in system_message\n')
replace_fn(CC, "test_assembler_injects_embodiment_appearance_and_anatomy",
    '    assert "Anatomy:" in system_message\n',
    '    assert "CANONICAL ANATOMY" in system_message\n')
for func in ("test_assembler_injects_authoritative_self_model", "test_assembler_distinguishes_identity_from_embodiment"):
    replace_fn(CC, func, '"AUTHORITATIVE SELF MODEL"', '"AUTHORITATIVE SELF STATE"')

MC = "test/test_embodiment_measurement_cognition.py"
for func in ("test_assembler_projects_authoritative_measurement_facts", "test_unrecognized_measurement_query_does_not_project_facts"):
    replace_fn(MC, func,
        '"AUTHORITATIVE EMBODIMENT MEASUREMENT QUERY RESULT"',
        '"DETERMINISTIC MEASUREMENT QUERY RESULT"')

RP = "test/test_embodiment_runtime_projection.py"
replace_fn(RP, "test_runtime_projects_canonical_embodiment_to_provider_boundary",
    '    assert "Measurements:" in system_content\n',
    '    assert "CANONICAL MEASUREMENTS" in system_content\n')
replace_fn(RP, "test_runtime_projects_canonical_embodiment_to_provider_boundary",
    '"Canonical status: CANON: "',
    '"Status: CANON: "')

SC = "test/test_embodiment_semantic_contract.py"
replace_fn(SC, "test_self_description_contract_distinguishes_identity_from_embodiment",
    '"SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT"',
    '"SELF-DESCRIPTION RESPONSE GROUNDING"')
replace_fn(SC, "test_self_description_contract_distinguishes_identity_from_embodiment",
    '"Sofía is an artificial intelligence entity"',
    '"Sofía is a persistent artificial intelligence entity."')
replace_fn(SC, "test_self_description_contract_distinguishes_identity_from_embodiment",
    '''    assert (
        "canonical human-form representational embodiment"
        in content
    )
''',
    '''    assert "Form: human" in content
    assert "Representation status: representational embodiment" in content
''')
replace_fn(SC, "test_self_description_contract_routes_canonical_embodied_questions_to_embodiment",
    '''    assert (
        "Questions about Sofía's appearance, avatar, clothing, "
        "measurements, fox features, or other canonical embodied "
        "details should be answered from the supplied EMBODIMENT "
        "context"
    ) in content
''',
    '''    assert (
        "When the user asks about Sofía's embodiment, use the "
        "canonical embodiment and its representational status."
    ) in content
    assert "When the user asks about Sofía's measurements" in content
    assert "When the user asks what Sofía is wearing" in content
''')
replace_fn(SC, "test_self_description_contract_does_not_turn_representation_into_biology",
    '''    assert (
        "Describing canonical embodiment does not claim that Sofía "
        "has a biological human body or physical-world capabilities"
    ) in content
''',
    '''    assert (
        "Representational embodiment does not establish "
        "biological humanity."
    ) in content
''')
replace_fn(SC, "test_self_description_contract_does_not_infer_physical_capability_from_representation",
    '''    assert (
        "Representation does not establish physical capability; "
        "physical capability must be established independently"
    ) in content
''',
    '''    assert (
        "Representational embodiment does not establish "
        "physical-world capability."
    ) in content
''')

PE = "test/test_personality_embodiment_contract.py"
replace_fn(PE, "test_embodiment_projects_canonical_clothing",
    '    assert "Clothing specification:" in content\n',
    '    assert "CANONICAL CLOTHING" in content\n')

# Prompt ablation tests must remove sections that actually exist. Keep the
# meaning of both ablations, and give the live probe the verified context.
PR = "test/test_embodiment_prompt_regression.py"
replace_fn(PR, "build_variant_request",
    '"AUTHORITATIVE SELF MODEL",\n            "SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT",',
    '"AUTHORITATIVE SELF-STATE PROJECTION",\n            "SELF-DESCRIPTION RESPONSE GROUNDING",')
replace_fn(PR, "build_variant_request",
    '"SELF-DESCRIPTION AND EMBODIMENT SEMANTIC CONTRACT",\n            "OPERATIONAL STATE",',
    '"SELF-DESCRIPTION RESPONSE GROUNDING",\n            "IDENTITY RECORD METADATA",')
replace_fn(PR, "create_configuration",
    '            model=OLLAMA_MODEL,\n',
    '            model=OLLAMA_MODEL,\n            context_size=32768,\n')
replace_fn(PR, "create_ollama_provider",
    '            model=OLLAMA_MODEL,\n',
    '            model=OLLAMA_MODEL,\n            context_size=32768,\n')

# Correct names for tests whose original section/order premise no longer exists.
replace(CA,
    "def test_authoritative_self_model_is_projected_after_constitution() -> None:",
    "def test_authoritative_self_state_projection_precedes_constitution_text() -> None:")
replace(CA,
    "def test_self_description_contract_is_not_projected_without_embodiment() -> None:",
    "def test_missing_embodiment_is_marked_unknown_in_self_state() -> None:")
replace(CA,
    "def test_self_description_contract_is_not_projected_without_self_model() -> None:",
    "def test_missing_self_model_is_marked_unknown_in_self_state() -> None:")
replace_fn(PR, "test_embodiment_prompt_regression_variants",
    '"WITHOUT_AUTHORITATIVE_SELF_MODEL",',
    '"WITHOUT_AUTHORITATIVE_SELF_STATE_PROJECTION",')
replace_fn(PR, "test_embodiment_prompt_regression_variants",
    '"WITHOUT_SEMANTIC_CONTRACT",',
    '"WITHOUT_RESPONSE_GROUNDING",')

# Compile all prospective Python sources before writing anything to disk.
for path, value in updated.items():
    compile(value, path, "exec")

changes = [path for path in updated if updated[path] != original[path]]
if not changes:
    raise SystemExit("No changes prepared. Refusing to claim a repair.")

# A dirty tracked target is user work, not ours to overwrite. Ignore unrelated
# state/sofia.db changes and refuse to touch modified source/test targets.
for mode in ([], ["--cached"]):
    check = subprocess.run(
        ["git", "diff", *mode, "--name-only", "--", *changes],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    if check.stdout.strip():
        raise RuntimeError(
            "Refusing to touch locally modified/staged target files: "
            + check.stdout.strip()
        )

print("Preflight passed: all anchors found and all edited Python files compiled.")
print("Proposed changes:")
for path in changes:
    before = original[path].splitlines(keepends=True)
    after = updated[path].splitlines(keepends=True)
    diff = list(difflib.unified_diff(before, after, fromfile=path, tofile=path))
    adds = sum(line.startswith("+") and not line.startswith("+++") for line in diff)
    dels = sum(line.startswith("-") and not line.startswith("---") for line in diff)
    print(f"  {path}: +{adds} / -{dels}")

if "--check" in sys.argv:
    print("Check-only mode: no files written.")
    raise SystemExit(0)

for path in changes:
    target = ROOT / path
    # Preserve original UTF-8 BOM if present, and native Windows line endings.
    raw = target.read_bytes()
    encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    newline = "\r\n" if b"\r\n" in raw else "\n"
    content = updated[path].replace("\n", newline)
    target.write_bytes(content.encode(encoding))

print("Changes applied locally; NO tests run and NO Git commit made.")
print("Inspect git diff, run targeted tests, then the full suite before committing.")
