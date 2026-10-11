# Phase 03 / 00: protected seed file atomic publish

Source audit: `RuntimeStorageLayout._seed_file` at GitHub `main`.
The original implementation checked `target.exists()`, copied source
into a same-directory temp file, then used `os.replace(temp,target)`.
If another valid Sofia process created a protected identity, Constitution,
personality or avatar between that first check and the replacement,
`os.replace` silently overwrote it. This violated the module's own
"existing runtime files are never overwritten" contract and could
replace the canonical protected identity in concurrent startup.

**Production change:** Source bytes are fully copied and `fsync`ed before
publication using the same-filesystem `os.link(staged,target)` exclusive
create-if-absent primitive. The source is closed before making the link.
An existing regular file wins unchanged; unexpected or symlinked winners
fail closed. Temporary files are always removed. Unsupported filesystems
do not fall back to a non-atomic replacement, preserving authority safety.

**Scope:** This is a targeted startup file publication repair, not writer
fencing or canonical database migration. The exact-SHA tests, Windows
NTFS validation and Venus/Artemis startup are deferred by the user's
code-first rule. Real promotion of a signed state-home pointer remains
disabled until an operator-authorized broker and independent single-writer
fence are available.
