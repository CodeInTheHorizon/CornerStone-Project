# MarketPulse AI — Visual Direction

Reference: [nomu.store](https://nomu.store/) — used for **design language only**.
No content, copy, imagery, branding, layout or proprietary asset is copied from it.

This note is the shared visual vocabulary for the landing page (Phase 2) and the
dashboard shell (Phase 3). The tokens are implemented in
`frontend/src/index.css`.

## What we take from the reference

| Trait | Applied as |
|---|---|
| Minimal, high contrast | Near-white or near-black ground; greys carry all structure |
| A single accent, used sparingly | `--accent` `#f0b429` — primary CTA, active states and live signals only, never decoration |
| Separation by whitespace, not boxes | Hairline borders, `py-20`/`py-28` section rhythm, alternating band tone instead of dividers |
| Airy, constrained shell | `--spacing-shell` `1180px`, generous internal card padding |
| Sticky, low-weight navbar | Transparent over the hero; gains a hairline border and backdrop blur only once scrolled |
| Geometric, not pill-shaped | `--radius-card` `12px`, `--radius-panel` `16px` |
| Tight display typography | `letter-spacing: -0.022em` on `h1`–`h3`; body copy at normal tracking |
| Restrained hover | Colour shifts, a 1px lift on feature cards, one shallow flip on the "why" cards. No springs, no parallax, no 3D beyond a single Y-axis rotation |

## What we deliberately do not take

- Product photography treatment. MarketPulse AI is data-led, so numbers,
  labels and (from Phase 8) charts carry the page rather than imagery.
- Any copy, section ordering or navigation labels. The landing page structure
  comes from PROJECT_CONTEXT.md §7.

## Theming

Both themes are first-class. Light is the `:root` default; `.dark` on the
`<html>` element overrides the same semantic variables, and `@theme inline`
exposes them to Tailwind so `bg-surface`, `text-muted` and friends follow the
active theme with no per-component branching.

Theme preference has three states — `light`, `dark`, or `system` (default,
which keeps following the OS while the page is open). The choice persists in
`localStorage` under `marketpulse-theme`, and a small inline script in
`index.html` applies the class before first paint so dark-mode visitors never
see a light flash.

| Token | Light | Dark |
|---|---|---|
| `--background` | `#fbfbfa` | `#08090a` |
| `--background-alt` | `#f4f4f2` | `#0c0e0f` |
| `--surface` | `#ffffff` | `#0f1113` |
| `--border` | `#e4e4e0` | `#23282c` |
| `--foreground` | `#111213` | `#f6f7f8` |
| `--muted` | `#56595d` | `#b2b8bd` |
| `--subtle` | `#6b6f75` | `#7c848a` |
| `--accent` (fill) | `#f0b429` | `#f0b429` |
| `--accent-text` | `#8a6206` | `#f0b429` |

The accent fill is identical in both themes so the brand holds, but accent
**text** differs: mid-tone yellow on a white ground fails AA, so light mode uses
a darker amber for text while keeping the bright fill for buttons.

## Guardrails

- **Contrast.** Every text/ground pairing in both themes clears WCAG AA (4.5:1).
  This was measured, not eyeballed — `--subtle` was darkened from `#83878c` to
  `#6b6f75` in light mode because it only reached 3.28:1 on `--background-alt`.
  Re-check whenever a colour changes.
- **Motion.** PROJECT_CONTEXT.md §5.2 asks for subtle motion only. Scroll
  reveals are a 14px rise with a fade; the flip is a single 500ms rotation.
  Everything collapses under `prefers-reduced-motion: reduce`.
- **Keyboard and screen readers.** The flip cards swap on focus as well as
  hover, and both faces stay in the DOM so the description is always readable
  without a hover. Interactive elements keep a visible focus ring.
- **Tailwind display conflicts.** Do not pass `hidden md:inline-flex` to
  `Button` — its base already sets `inline-flex`, and which wins depends on
  stylesheet order, not class order. Put responsive display classes on a
  wrapper element instead.

## Accuracy note

The reference site was summarised programmatically; its exact hex values, fonts
and measurements were **not** read from its stylesheets, and the summary itself
was hedged. Everything above is our own interpretation of the *direction*
(minimal / airy / high-contrast / one accent), not a reproduction of their
values.
