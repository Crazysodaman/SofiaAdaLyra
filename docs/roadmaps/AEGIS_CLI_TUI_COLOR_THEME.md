# Aegis CLI / TUI | Canonical Terminal Color Theme

**Status:** OWNER-DESIRED / CANONICAL DESIGN TOKENS (2026-11-07). This file records the owner's exact hexadecimal color choices; it is not evidence that the theme is implemented or tested in every command.
**Shared GUI + terminal palette (owner decision 2026-11-07):** The exact RGB values are also the default Aegis GUI colors. [AEGIS_SHARED_GUI_TUI_THEME.md](AEGIS_SHARED_GUI_TUI_THEME.md) is now the **cross-surface canonical token source**; this file retains terminal-specific ANSI/monochrome fallback and the same exact historical palette table. Where the two documents overlap, keep values identical and treat the shared token specification as authoritative. The separate Sofía personal Workbench/adaptive theme remains independent.

**Scope:** **ALL Aegis CLI UI surfaces**, not only AG-D022: the AG-D011 PowerShell/Bash ASCII installer, interactive TUI, line-mode fallback, Platform/Core/Fleet/Module/Model/Security/Jobs/Backups/Updates/Diagnostics settings menus, wizard prompts, approval screens, terminal status and future terminal tools. Applies on Windows consoles, Linux shells and SSH sessions when color capability supports it.
**Not automatically changing:** AG-D007 graphical desktop theme, unrelated third-party application output, JSON/API formats, personal Core avatar styling, underlying trust/permission decisions or the current #201 acceptance gates.
**Implementation ownership:** Future installers, Rust/native TUI clients and CLI frontends reuse one shared theme token specification. Do not create independent inconsistent screen palettes.

## 1. Owner-provided exact palette

The hex values below are canonical 24-bit sRGB tokens, preserving the owner's exact capitalization and byte values (all hex values are case-insensitive for rendering).

### Core interface colors

| Token | Purpose | Hex |
| --- | --- | --- |
| `main_primary` | Main / Primary; title and selected control | `#9400D3` |
| `secondary_accent` | Secondary / Accent | `#00C2FF` |
| `tertiary` | Tertiary; vivid positive/energy accent | `#39FF14` |
| `background` | Background | `#000000` |
| `text_on_background_primary` | Primary-colored text on black, for headings/key prompts | `#9400D3` |
| `text_on_primary` | Text on purple filled elements | `#000000` |
| `danger` | Error / Danger | `#9F0202` |

### Surfaces, buttons, text

| Token | Purpose | Hex |
| --- | --- | --- |
| `card_surface` | Cards / inset panels | `#0B1020` |
| `primary_button` | Primary buttons or selected entry background | `#9400D3` |
| `hover_focus` | Hover state, terminal keyboard focus/active selection | `#AA1DFF` |
| `accent_indicator` | Accents/indicators | `#00C2FF` |
| `text_main` | Main body text; tables, settings values and descriptive text | `#E5E7EB` |
| `text_muted` | Muted metadata, context and inactive details | `#94A3B8` |

### Green and HUD palette

| Token | Purpose | Hex |
| --- | --- | --- |
| `tertiary_dark` | Secondary, less intense green status | `#4CAF50` |
| `hud_primary` | Primary HUD / operational attention | `#FFB000` |
| `hud_secondary` | Secondary HUD | `#FF8C00` |
| `visr_highlight` | VISR highlight / emphasized diagnostic focus | `#FFB000` |
| `highlight_bright` | Bright highlight | `#FFC83D` |
| `glow` | Glow highlight where terminal rendering can express one | `#FFD54F` |

### Semantic states

| Token | Purpose | Hex |
| --- | --- | --- |
| `success` | SUCCESS / VERIFIED OK | `#39FF14` |
| `warning` | WARNING / degraded / caution | `#FFB000` |
| `error` | ERROR / DANGER | `#9F0202` |

The owner also specified `#000000` as both Background and Text on Primary, and `#9400D3` as both Main / Primary and Text on Background. These are deliberate repeat tokens, not conflicting palettes.

## 2. Semantic hierarchy and readability

The owner's `Text on Background = #9400D3` means **main-brand copy** (page titles, commands/prompts, emphasized labels). Their `Main Text = #E5E7EB` means **ordinary body copy**, including documentation and small label text. Respect both:
- Top-level AEGIS header: `main_primary` on `background`; decorative line/border may use `secondary_accent`.
- Heading/title or selected menu marker: `main_primary` on black, preferably bold/large or with sufficient framing. Regular small text uses `text_main` instead.
- Body, fields, actionable descriptions: `text_main` on black or card; contextual timestamps and disabled metadata: `text_muted`.
- Cards: `card_surface` behind content; focus/selection: `hover_focus` or `primary_button` fill, with `text_on_primary` where sufficient.
- Cyan: selected field borders, progress/step indicators, verified connections **only when actually verified**, and navigation highlights. Lime: success **only when supported by actual successful receipt**, not assumed Core cognition health.
- Amber: actual warnings, pending or degraded states, review/approval emphasis; orange: secondary HUD data/operational attention; golden highlight/glow for headings/callouts, not all menu text.
- Dark green `tertiary_dark`: subtle positive indicator, not a synonym for final acceptance.

**Accessibility qualification:** On `#000000`, purple `#9400D3` has ~3.20:1 contrast and red `#9F0202` ~2.48:1, below a common 4.5:1 normal-text target. Preserve the owner's exact colors, but:
1. Do not render small purple or dark-red body/error messages alone on black.
2. Use `text_main` for small critical text and show `[ERROR]`, `[DANGER]`, `[STOP]` etc. in explicit ASCII alongside the exact red accent/border.
3. Display warnings with text `[WARNING]` and associated data, not amber alone.
4. Violet is permitted for visibly emphasized branding/large headers; normal content must remain readable.
5. No logic may depend on the displayed color. Unknown is printed `[UNKNOWN]`, not colored as healthy.
6. Avoid blinking, flashing, simulated brightness/glow on plain terminals, excessive ANSI effects or reliance on mouse hover.

## 3. Universal rendering and fallbacks

- Preferred mode: **24-bit truecolor ANSI** with the exact sRGB hex values when terminal capability is positively detected.
- Fallback: 256-color ANSI approximate mapping, then 16-color ANSI semantic equivalents (magenta/cyan/bright green/yellow/red/black/white), then **plain monochrome ASCII**. The 256-/16-color mode cannot reproduce exact hex and must not claim to.
- Support Windows Terminal, PowerShell/console variants, Debian terminal/SSH, `tmux`/`screen` where advertised capability matches reality, and serial/headless environments. Detect capability rather than assuming an OS supports truecolor.
- `NO_COLOR`, `TERM=dumb`, redirected stdout/stderr, test logs, pipelines, `--no-color`, machine-readable `--json`, and non-TTY output must suppress escape sequences by default. An explicit interactive `--color=always` may opt in where suitable, but never for JSON.
- `--color=auto|always|never` and `--theme=aegis` are **proposed common CLI switches**, not commands currently certified as implemented.
- ANSI style/color must always be restored on exit, exception, CTRL-C, TUI termination or subprocess failure. No ANSI codes in error logs/receipts; render plain text or structured semantic fields and style only at the last display boundary.
- In TUI, card fills/screen background may use `background` and `card_surface`. In ordinary CLI stdout/stderr, do not forcibly recolor the entire terminal background if doing so disrupts the user's shell; foreground colors and isolated spans are enough.
- Avoid control sequences from untrusted hostnames, paths, module names, model output or logs. Escape/strip untrusted ANSI and terminal control characters before rendering.

## 4. Shared screen vocabulary and ASCII examples

```text
+-----------------------------------------------------------+
| AEGIS PLATFORM                       [STATUS: VERIFIED]   |
+-----------------------------------------------------------+
| [1] Platform Settings                                   |
| [2] Core Manager                                        |
| [3] Fleet Manager                                       |
| [4] Security and Permissions                            |
| [5] Diagnostics                                         |
| [0] Exit                                                |
+-----------------------------------------------------------+
| [OK]       Authenticated local Platform                 |
| [WARNING]  Restart required for pending setting        |
| [ERROR]    Verification failed; no change applied      |
| [UNKNOWN]  Remote host health could not be confirmed   |
+-----------------------------------------------------------+
```

In a color-capable terminal:
- Outer screen/background `#000000`, panels `#0B1020`.
- AEGIS title `#9400D3`; option values `#E5E7EB`; muted help `#94A3B8`.
- Currently selected option `#9400D3` fill and `#000000` contrasting text; keyboard focus may use `#AA1DFF`.
- `[OK]` accent `#39FF14`, `[WARNING]` accent `#FFB000`, `[ERROR]` accent/border `#9F0202` plus readable `#E5E7EB` label, and `[UNKNOWN]` muted `#94A3B8`.
- Progress / identity and trusted transport indicator `#00C2FF` only when evidence actually supports the corresponding state.
- Installer and settings review confirmation uses `#FFB000` HUD emphasis; refusal, STOP and protected actions have text labels and real permission checks regardless of palette.

## 5. Coverage and source-of-truth rule

**One theme source for every Aegis-owned terminal renderer:** AG-D011 bootstrap scripts and installer, AG-D022 terminal Control Center, AG-D023 Core settings views, and CLI commands for all managers. Future code should centralize the semantic palette in a shared presentation-only theme module/data contract rather than repeating literal hex in every screen. It must not influence SAFE permission policy, service identity, secrets, logs, audit or API responses.

**Owner has now explicitly requested a common GUI theme.** AG-D007 GUI and all Aegis TUI/CLI use the same default [shared GUI/TUI colors](AEGIS_SHARED_GUI_TUI_THEME.md). Independent presentation/accessibility overrides can exist, but not a divergent default color specification. Aegis TUI, line-mode and installer inherit this terminal palette by default, with monochrome fallback always supported.

## 6. Validation criteria before declaring theme implemented

1. Snapshot-test every terminal screen against semantic token roles (not merely colored examples); ensure no hard-coded divergent palette in first-party CLI/TUI/installer surfaces.
2. Verify truecolor exact RGB, 256-color fallback, 16-color fallback, monochrome and 40-/80-column layouts on supported Windows and Debian terminals, including SSH.
3. Verify all statuses and buttons remain distinguishable with `NO_COLOR`, no Unicode or cursor control, and with low-contrast purple/red reserved for accents rather than tiny critical text.
4. Verify redirects, pipes, logs, CI, `--json`, exceptions and crash recovery never emit raw ANSI control bytes or corrupt output, and any ANSI from untrusted content is escaped.
5. Verify service/back-end state remains identical regardless of theme and no extra permissions, model/GPU, GUI or Core are required.
6. Do not mark theme integration VERIFIED until actual source, tests, installed-artifact and terminal observations support it.

**Status truth:** These are approved owner-specified design tokens, not a released implementation, release acceptance, or a new priority for OpenCode/Codex.
