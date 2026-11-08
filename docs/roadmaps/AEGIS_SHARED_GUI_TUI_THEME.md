# AEGIS_SHARED_GUI_TUI_THEME

**Status:** OWNER-DESIRED, DETAILED DESIGN CAPTURED (2026-11-08).
**Target release:** Platform 1.0 expanded shakedown (owner directive 2026-11-08).

Created by the owner directive scheduling GUI/TUI management functionality
into the expanded Platform 1.0 shakedown. Visual tokens below extend the
already-normative design tokens in
[AG-D007 control center layout](AG_D007_CONTROL_CENTER_LAYOUT_AND_PATHS.md#5-visual-style),
preserving them verbatim and mapping them to a shared TUI/CLI-friendly token
set. Both interfaces must apply these tokens; shakedown row 38 verifies them.

## Shared token set

| Token | GUI (per AG-D007 layout spec) | TUI (terminal mapping) |
| --- | --- | --- |
| background | near-black surface on charcoal | near-black (ANSI 16 default bg) |
| surface/panel | charcoal panel layers | alternate black |
| interactive accent | restrained teal | teal (closest ANSI foreground) |
| secondary accent | violet, optional only | violet/magenta, optional only |
| verified healthy | green, always with a label | green + literal label |
| pending/degraded | amber, always with a label | yellow + literal label |
| STOP/revoked/danger | red, always with a label | red + literal label |
| unknown/unobserved | gray, always with a label | gray/white + literal label |
| spacing | 8 px rhythm; 12-16 px pane padding | aligned text blocks; airy separators |

Non-negotiable rules carried over verbatim:

* Light mode and system theme remain supported in the GUI; the TUI honors
  terminal defaults (no forced dark hijack) while emitting the same labels.
* Dangerous actions are separated from refresh/read-only actions and use
  semantic color plus text/icons, never color alone.
* No fake job progress and no claimed online status from stale cached
  observations; labels accompany every state color.
* No Core personality themes in global security screens; the theme is a
  neutral operator theme, not SofA-a expression.
* Per-user presentation settings (window geometry/theme, TUI layout) persist
  only in the operator-specified presentation locations; no secure
  credentials, approvals, canonical Fleet trust, personal memories or Core
  writer data belong in theme files.

## Evidence expectation

Row 38 requires the same token constants (one shared source of truth) used by
both interfaces, with screenshots of Windows GUI, Windows TUI, Debian TUI and
a diff review confirming no client invents its own semantic colors. Textual
labels appear in every captured state transition.
