# Aegis | Shared GUI + CLI/TUI Visual Theme

**Status:** OWNER-APPROVED FOR EXPANDED PLATFORM 1.0 SHAKEDOWN (2026-11-08); implementation and evidence pending. The owner chose the same exact default palette for ALL first-party Aegis graphical and terminal management interfaces.
**Authoritative palette:** This document is the **single cross-surface token source**. The earlier [CLI/TUI color specification](AEGIS_CLI_TUI_COLOR_THEME.md) remains the terminal-specific rendering, ANSI, fallback and accessibility companion; avoid drifting copies of token definitions.
**Applies to:** AG-D007 GUI Control Center, AG-D011 interactive installer, AG-D022 headless Terminal Control Center, AG-D023 Core self-settings, Core/Fleet/Model/Module/Jobs/Security/Backup/Diagnostics/Update managers and future first-party `aegis` terminal commands.
**Does not automatically recolor:** Sofía's separate personal Workbench/avatar/emotional theme or arbitrary third-party apps. Personal Sofía theme changes must not silently alter neutral Aegis security or operator views.
**Release fence:** Owner authorization on 2026-11-08 promotes GUI/TUI integration into Platform-only acceptance rows 31–38. This does not prove implementation or authorize live service changes, production Core activation or G8 cutover. All original design tokens remain authoritative.

## 1. Exact palette: owner-supplied hex

All values are sRGB hex; repeated values are intentional aliases.

| Shared role | Canonical token | Hex | Intended use |
| --- | --- | --- | --- |
| Primary / Main | `primary` | `#9400D3` | Brand, headings, active navigation and primary actions |
| Secondary / Accent | `accent` | `#00C2FF` | Focus outlines, selection indicators, link accents and verified detail cues |
| Tertiary | `tertiary` | `#39FF14` | Vivid green accents |
| Background | `background` | `#000000` | Main desktop/terminal dark backdrop |
| Text on Background | `text_on_background_brand` | `#9400D3` | Brand/title copy on black, not all small body text |
| Text on Primary | `text_on_primary` | `#000000` | High-emphasis large labels/icons where contrast permits |
| Error / Danger | `danger` | `#9F0202` | Danger border/badge surface/accent, accompanied by a readable ERROR label |
| Cards | `surface_card` | `#0B1020` | Inset panels, cards, dialogs, terminal boxes |
| Primary Buttons | `button_primary` | `#9400D3` | Primary/action button background |
| Hover State | `hover` | `#AA1DFF` | GUI pointer hover; TUI active keyboard focus |
| Accent Indicators | `indicator` | `#00C2FF` | Selected row/active tab outline and trust/progress cue |
| Main Text | `text_main` | `#E5E7EB` | Normal labels, settings, tables, help, button text when small |
| Muted Text | `text_muted` | `#94A3B8` | Metadata, hints, nonessential labels and unavailable text |
| Dark Tertiary | `tertiary_dark` | `#4CAF50` | Quiet positive status accent |
| Primary HUD | `hud_primary` | `#FFB000` | Warning/operational attention |
| Secondary HUD | `hud_secondary` | `#FF8C00` | Secondary live-resource/attention indicators |
| VISR Highlight | `visr` | `#FFB000` | Named HUD/diagnostic highlight |
| Bright Highlight | `highlight_bright` | `#FFC83D` | Strong highlight and attention |
| Glow | `glow` | `#FFD54F` | Optional graphic glow/glancing emphasis; solid border/text replacement in terminal |
| Success | `success` | `#39FF14` | Verified success state, not merely process-alive |
| Warning | `warning` | `#FFB000` | Warnings, degraded and caution |
| Error | `error` | `#9F0202` | Red accent + legible text status |

**Precedence:** These are shared **design** tokens. Different GUI and TUI renderers may choose a contrast-safe content foreground or plain-text fallback while retaining the same palette. The owner's requested `text_on_primary=#000000` remains a token, but it is **not** automatically valid for every size of label on `#9400D3`. Normal-size critical text on purple should use `#E5E7EB` (or another already-defined contrast-safe token) rather than low-contrast black. Similarly `#9F0202` is never the only small-text error foreground on black.

## 2. The same visual vocabulary across input modes

| Meaning | GUI treatment | TUI / plain CLI treatment |
| --- | --- | --- |
| Aegis title/header | Purple brand text on black, optional cyan rule | Purple heading (or plain `AEGIS` in monochrome) |
| Navigation selected | Purple or hover-purple fill, cyan focus border | Purple selection bar, cyan focus marker; ASCII `>` / `[selected]` |
| Standard content | Light `#E5E7EB` on black/cards | Light `#E5E7EB` on black/card where truecolor; normal terminal text in fallback |
| Card/group | `#0B1020` inset region | `#0B1020` cell background if supported; ASCII `+---+` box otherwise |
| Success | Lime indicator + `VERIFIED` text | `[OK: VERIFIED]` and lime marker if available |
| Warning/pending | Amber indicator + exact pending/degraded text | `[WARNING]`, `[PENDING]` + amber if available |
| Error/STOP | Red accent paired with readable large label and warning consequences | `[ERROR]` / `[STOP]` in legible main text, with red badge/border if color supported |
| Unknown/stale | Muted gray and last observed timestamp | `[UNKNOWN]` / `[STALE since <time>]` |
| Keyboard focus | Cyan visible focus outline, no hover dependence | Cyan or ASCII focus marker, full keyboard-only control |
| Protected action | Purple action may be gated by exact independent owner approval; red danger cue on destructive | Same exact action preview and approval, with typed scope/identity and SAFE/STOP checks |
| Glow/animation | Optional subtle amber decorative shadow for HUD where accessible | Solid `#FFD54F` highlight only, no simulated flashing/glow |

**State never derives from color**; statuses come from authenticated source/receipt/freshness and remain textual in monochrome, screen readers, logs and JSON. No Core response changes Platform brand, owner permissions or SAFE/STOP appearance as a source of authority.

## 3. Color contrast and accessibility guardrails

- `#9400D3` on `#000000` (and black text on solid `#9400D3`) has approximately **3.2:1** contrast: suitable for large/bold display text and decorative emphasis, not as the sole small normal-text color where 4.5:1 is needed.
- `#9F0202` on black is approximately **2.5:1**: use as an accent, background segment or border, not sole small danger label. Put readable `#E5E7EB` text and `ERROR`/STOP icon-label alongside.
- For normal-size buttons filled purple, small foreground labels should use `#E5E7EB` when that combination meets contrast; reserve the exact black `text_on_primary` token for adequately sized bold content or noncritical decorative icons. WCAG-style checks at actual font weight/size still required.
- GUI must support keyboard-only, visible focus, screen readers, 200% text zoom and responsive spacing; TUI supports numeric navigation, 40/80 columns, `NO_COLOR` and line-mode fallback.
- Reduced motion and **no animated glow** by default. In GUI an optional decorative glow must never obscure text, performance or status; TUI has no true glow shader.
- High-contrast OS override and true monochrome terminal are accessibility **fallbacks**, not a competing Aegis identity. Default remains this owner's unified dark theme on all Aegis GUI and TUI surfaces.
- Unknown, denied, offline and unverified must not be colored success. UI color may not claim signatures, installed artifact health or remote trust.

## 4. Scope, settings ownership and safety

- **Platform UI default:** `aegis-dark` shared token preset across GUI/TUI/installer. GUI theme switch is user **presentation preference** only, not a Platform security setting; optional system/accessible alternatives must be explicitly indicated as overrides.
- A normal GUI view and the exact same resource in TUI show matching semantic labels and action scope, even if one uses buttons and the other numeric menus.
- Per-user theme and layout choices may be stored in respective UI preference stores and can differ by interface if explicitly selected; no direct write to canonical Platform identity, Core protected memory, SAFE grants or trusted host registry.
- GUI and terminal clients both consume common data contracts. Color themes do not require a Core, model, GPU, desktop service, new privileged API, admin credentials or OS elevation.
- Sofía's separate personal adaptive appearance implementation (`src/sofia/modules/ui/theme.py`) already has purple/cyan/lime foundation but also Core/emotion/season-dependent colors and nonmatching panel/text shades. Preserve that personal system for Workbench; **do not use it as the neutral Aegis settings authority or let Core emotion recolor protected controls**.
- One future shared presentation token definition should be packaged for native GUI and TUI to consume, with stable semantic field names; avoid a second independent color registry. No code implementation or migration occurs by documenting the target.

## 5. Screens covered

- AG-D007 Overview, Fleet, Cores, Models, Modules, Signed Catalog, Jobs, Hardware/Compute, Updates, Security/Approvals, Backups/Recovery, Diagnostics, Lab, Developer Workshop and Settings.
- AG-D011 setup, installation review, verified release, permissions, repairs, rollback, update and uninstall prompts.
- AG-D022 terminal equivalent screens and AG-D023 Core self-settings, policy, proposal, audit, approval and lock.
- Native GUI tray notifications and manager pop-outs, where they are *Aegis Platform* neutral surfaces. A separate personal Sofía tray/Workbench may intentionally remain personal.

## 6. Review/acceptance before marking implemented

1. Validate every hex token against a central manifest and ensure all first-party Aegis GUI/TUI/CLI clients import it; snapshot selected and high-contrast/error states. Existing old colors in legacy Sofía UI are not evidence of new GUI adoption.
2. Ensure purple-selected buttons meet label contrast for small text; verify dark red warnings remain intelligible with no color and with assistive readers.
3. Verify visual and action parity in native Windows GUI + PowerShell TUI and Debian GUI + SSH TUI; Core absent, disconnected Fleet, stale data, owner denied and multi-Core.
4. Test truecolor/256/16/monochrome transitions, terminal redirection/JSON safety, GUI scaling/OS high-contrast, user theme persistence and no theme-induced service/state writes.
5. No `VERIFIED` or `APPLIED` visual unless the service returns real exact outcome evidence; statuses are always distinguishable from intent and pending approval.

**Release truth:** this file is a canonical design source, not proof of a published GUI, shipped TUI or satisfied #201 release gates.
