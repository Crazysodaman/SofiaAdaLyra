# Core file migration map

Branch: `aegis/forensic-layout`, based on `main` at `93d61a3f`.

This map records every Core-specific path moved or replaced during the Phase C
layout normalization.  No runtime database, personal memory, protected Sofía
UUID or twin #4/#5 package was moved.

## Canonical module moves

| Old path | New path | Reason |
| --- | --- | --- |
| `src/sofia/core/multicore/vera.py` | `src/sofia/core/vera/identity.py` | Vera's behavior belongs to her own package, not the shared multicore engine. |
| `src/sofia/core/multicore/vera.py` | `src/sofia/core/multicore/vera.py` (thin shim) | Backward-compatible re-export of every former public name. |
| `src/sofia/core/multicore/unwritten.py` | `src/sofia/core/unwritten/identity.py` | Core #7's blank identity implementation belongs to its own package. |
| `src/sofia/core/multicore/unwritten.py` | `src/sofia/core/multicore/unwritten.py` (thin shim) | Backward-compatible re-export of every former public name. |

## Asset moves

| Old path | New path | Reason |
| --- | --- | --- |
| `src/sofia/core/cores/mack/__init__.py` | `src/sofia/core/mack/__init__.py` | Mack owns his package entrypoint. |
| `src/sofia/core/cores/mack/constitution.md` | `src/sofia/core/mack/constitution.md` | Personal asset moves with its Core. |
| `src/sofia/core/cores/mack/personality.json` | `src/sofia/core/mack/personality.json` | Personal asset moves with its Core. |
| `src/sofia/core/cores/mack/avatar.json` | `src/sofia/core/mack/avatar.json` | Personal asset moves with its Core. |
| `src/sofia/core/cores/mack/voice.json` | `src/sofia/core/mack/voice.json` | Deferred voice metadata moves with its Core. |
| `src/sofia/core/cores/nova/__init__.py` | `src/sofia/core/nova/__init__.py` | Nova owns her package entrypoint. |
| `src/sofia/core/cores/nova/constitution.md` | `src/sofia/core/nova/constitution.md` | Personal asset moves with its Core. |
| `src/sofia/core/cores/nova/personality.json` | `src/sofia/core/nova/personality.json` | Personal asset moves with its Core. |
| `src/sofia/core/cores/nova/avatar.json` | `src/sofia/core/nova/avatar.json` | Personal asset moves with its Core. |
| `src/sofia/core/cores/nova/voice.json` | `src/sofia/core/nova/voice.json` | Deferred voice metadata moves with its Core. |
| `src/sofia/core/cores/vera/__init__.py` | `src/sofia/core/vera/__init__.py` | Vera owns her package entrypoint. |
| `src/sofia/core/cores/vera/constitution.md` | `src/sofia/core/vera/constitution.md` | Personal asset moves with its Core. |
| `src/sofia/core/cores/vera/personality.json` | `src/sofia/core/vera/personality.json` | Personal asset moves with its Core. |
| `src/sofia/core/cores/vera/avatar.json` | `src/sofia/core/vera/avatar.json` | Personal asset moves with its Core. |
| `src/sofia/core/cores/vera/voice.json` | `src/sofia/core/vera/voice.json` | Deferred voice metadata moves with its Core. |
| `src/sofia/core/cores/unwritten/__init__.py` | `src/sofia/core/unwritten/__init__.py` | Core #7 owns its neutral bootstrap package. |
| `src/sofia/core/cores/unwritten/constitution.md` | `src/sofia/core/unwritten/constitution.md` | Neutral bootstrap asset moves with its Core. |
| `src/sofia/core/cores/__init__.py` | removed | The shared `cores` asset namespace is retired; no duplicate asset root remains. |

## Constant moves

| Old location | New location | Reason |
| --- | --- | --- |
| `sofia.core.multicore.profiles.MACK_PROFILE` | `sofia.core.mack.profile.MACK_PROFILE` | Mack owns his inert profile metadata. |
| `sofia.core.multicore.profiles.NOVA_PROFILE` | `sofia.core.nova.profile.NOVA_PROFILE` | Nova owns her inert profile metadata. |
| `sofia.core.multicore.profiles.VERA_PROFILE` | `sofia.core.vera.profile.VERA_PROFILE` | Vera owns her inert profile metadata. |
| `sofia.core.multicore.personality.MACK_FULLER_PROFILE` | `sofia.core.mack.personality.MACK_FULLER_PROFILE` | Baseline traits are Core-owned data, not engine logic. |
| `sofia.core.multicore.personality.NOVA_ARDEN_PROFILE` | `sofia.core.nova.personality.NOVA_ARDEN_PROFILE` | Baseline traits are Core-owned data, not engine logic. |
| `sofia.core.multicore.emotion.MACK_EMOTION_PROFILE` | `sofia.core.mack.emotion.MACK_EMOTION_PROFILE` | Simulated-emotion baseline is Core-owned data. |
| `sofia.core.multicore.emotion.NOVA_EMOTION_PROFILE` | `sofia.core.nova.emotion.NOVA_EMOTION_PROFILE` | Simulated-emotion baseline is Core-owned data. |

Legacy imports remain valid through lazy `__getattr__` re-exports in
`sofia.core.multicore.profiles`, `sofia.core.multicore.personality`,
`sofia.core.multicore.emotion` and `sofia.core.multicore`.

## New packages

| Path | Reason |
| --- | --- |
| `src/sofia/core/sofia/__init__.py` | Canonical Core #1 package surface. |
| `src/sofia/core/sofia/identity.py` | Immutable Sofía name/number/slug; no UUID fabricated. |
| `src/sofia/core/sofia/factory.py` | References to existing protected assets and inert definition factory. |
| `src/sofia/core/mack/profile.py` | Mack profile constant. |
| `src/sofia/core/nova/profile.py` | Nova profile constant. |
| `src/sofia/core/vera/profile.py` | Vera profile constant. |
| `src/sofia/core/mack/personality.py` | Mack baseline personality data. |
| `src/sofia/core/nova/personality.py` | Nova baseline personality data. |
| `src/sofia/core/mack/emotion.py` | Mack simulated-emotion data. |
| `src/sofia/core/nova/emotion.py` | Nova simulated-emotion data. |

## Path and packaging changes

| Old reference | New reference | Reason |
| --- | --- | --- |
| `CoreProfileSpec.constitution_path == "cores/<slug>/constitution.md"` | `"<slug>/constitution.md"` | Resolve from `sofia.core`, the owning Core's parent package. |
| `CoreProfileSpec.personality_path == "cores/<slug>/personality.json"` | `"<slug>/personality.json"` | Same. |
| `files("sofia.core.cores")` | `files("sofia.core")` | No shared asset namespace remains. |
| `files("sofia.core.cores.unwritten")` | `files("sofia.core.unwritten")` | Core #7 owns its constitution. |
| `pyproject.toml` / `packaging/components.toml` keys `sofia.core.cores.*` | `sofia.core.<slug>` plus generic `sofia.core` globs | Package data follows the owning package. |
| `component_artifacts.CORE_ASSET_FILES` `sofia/core/cores/<slug>/...` | `sofia/core/<slug>/...` | Component artifact evidence matches the new source layout. |

## Unchanged by design

- `src/sofia/core/identity/identity.json` and the protected runtime UUID.
- `src/sofia/core/constitution/*`, `src/sofia/core/personality/*`,
  `src/sofia/core/embodiment/avatar.json`.
- Runtime databases and personal memories (they remain outside source).
- No Core #4/#5 package or twin asset directory is introduced.
