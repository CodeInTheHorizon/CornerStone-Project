# MarketPulse AI — Visual Direction

Reference: [nomu.store](https://nomu.store/) — used for **design language only**.
No content, copy, imagery, layout or branding is copied from it.

This note exists so Phase 2 (landing page) and Phase 3 (dashboard shell) share
one visual vocabulary. The tokens below are already implemented in
`frontend/src/index.css` under Tailwind v4's `@theme`.

## What we take from the reference

| Trait | Applied as |
|---|---|
| Dark, near-black ground | `--color-ink-950` `#08090a` as the page ground; surfaces step up through `ink-900`/`ink-850` rather than using shadows |
| High contrast, low chroma | Near-white `chalk-50` text on near-black; greys carry all structure |
| A single accent, used sparingly | `--color-accent-400` `#f0b429` — primary CTA and live signals only, never decoration |
| Separation by whitespace, not boxes | Hairline `ink-800` borders; generous vertical section padding |
| Geometric, not pill-shaped | `--radius-card` `10px`; avoid fully rounded containers |
| Tight display typography | `letter-spacing: -0.02em` on `h1`–`h3`, normal tracking for body |
| Restrained motion | Colour/opacity transitions and small translations only |
| Constrained content width | `--spacing-shell` `1200px` |

## What we deliberately do not take

- Product/e-commerce photography treatment — MarketPulse AI is data-led, so
  charts and numeric density carry the page instead of imagery.
- Any copy, section ordering, or navigation labels. Landing page structure comes
  from PROJECT_CONTEXT.md §7, not from the reference.

## Guardrails

- Section 5.2 of PROJECT_CONTEXT.md asks for subtle motion only. Hover-flip
  cards in Phase 2 should be a short transform + opacity change, nothing more.
- Every colour pairing used for text must clear WCAG AA (4.5:1). The accent is a
  mid-tone yellow: it is legible as **dark text on accent fill**, not as accent
  text on the dark ground at small sizes.
- Theme is committed dark. There is no light mode in the MVP.

## Accuracy note

The reference site was summarised programmatically; exact hex values and font
choices on nomu.store were not measured. The palette above is our own
interpretation of the *direction* (dark / minimal / high-contrast / one accent),
not a reproduction of their values.
