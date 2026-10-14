# V18 Phase 00: filesystem inspection data outside SYSTEM context

Date 2026-10-14. The production `CognitiveContextAssembler` previously
placed `FilesystemResult.message`, file paths, directory entries and
optional file contents inside the same SYSTEM role as canonical identity,
constitution and host authority policy. File content, remote/mounted path
strings and tool messages are not instructions, even when the inspected
operation is authorized by the host.

The existing `format_filesystem_result` output now remains available in
a structured USER-role JSON source quotation. Only the host's inspection
policy and interpretation constraints remain SYSTEM. The project does not
add an extra capability, change what SAFE authorizes, or re-run the tool.
The focused assembler regression checks original source data, role safety,
and response-message ordering on Linux/Windows.

Unaddressed CA-003/CA-1208 scope: other contextual source projections,
real-host hostile path injection, approved-memory deletion/revocation,
final source-to-effect audit, and independent Gate 4 review. No Gate 4
status or production host setting was changed.
