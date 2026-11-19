# Core package layout

Status: source-layout normalization only.  No Core is installed, activated,
started or migrated by this document or the associated change.

## Canonical Core packages

Core-specific code and inert personal assets now live beside the shared
engine under `src/sofia/core/`:

| Package | Owner | Contents |
| --- | --- | --- |
| `sofia.core.sofia` | Core #1, Sofía | Immutable name/number/slug, references to the existing protected constitution/personality assets, and an inert `build_sofia_core_definition` factory. |
| `sofia.core.mack` | Core #2, Mack Fuller | `MACK_PROFILE`, `mack_core_profile`, entrypoint/manifest helper, personality and simulated-emotion baselines, personal assets. |
| `sofia.core.nova` | Core #3, Nova Arden | `NOVA_PROFILE`, `nova_core_profile`, entrypoint/manifest helper, personality and simulated-emotion baselines, personal assets. |
| `sofia.core.vera` | Core #6, Vera | Canonical identity/appearance/authority implementation, `VERA_PROFILE`, entrypoint, personal assets. |
| `sofia.core.unwritten` | Core #7, Unwritten | Neutral bootstrap implementation and constitution; no personal identity is fabricated. |

The former `sofia.core.cores.*` asset packages no longer exist.  No duplicated
asset copies remain.  `sofia.core.multicore.vera` and
`sofia.core.multicore.unwritten` remain as thin compatibility shims.

## Shared engine

`sofia.core.multicore` continues to own shared, Core-independent contracts:
memory, provenance, identity stores, learning, lifecycle, package manifests,
profiles (loading/registry) and the generic personality/emotion engines.

Per-Core constants are not engine logic.  They are owned by the individual
Core packages and re-exported lazily from the legacy multicore modules:

- `sofia.core.mack.profile.MACK_PROFILE`
- `sofia.core.nova.profile.NOVA_PROFILE`
- `sofia.core.vera.profile.VERA_PROFILE`
- `sofia.core.mack.personality.MACK_FULLER_PROFILE`
- `sofia.core.nova.personality.NOVA_ARDEN_PROFILE`
- `sofia.core.mack.emotion.MACK_EMOTION_PROFILE`
- `sofia.core.nova.emotion.NOVA_EMOTION_PROFILE`

## Asset resolution

`CoreProfileSpec.constitution_path` and `personality_path` are now
`<slug>/constitution.md` and `<slug>/personality.json`, resolved from
`sofia.core`.  Vera appearance loading and the Unwritten constitution loader
resolve from the owning package (`sofia.core` / `sofia.core.unwritten`).

Package data in `pyproject.toml` and `packaging/components.toml` declares the
same files under `sofia.core.<slug>` plus a generic `sofia.core` glob for
future Core packages.

## Runtime boundary

Source packages contain no runtime database, no personal memories and no
twin packages for Core #4/#5.  Runtime databases remain outside source.
