/**
 * Provenance badge: LIVE / IMPORTED / DEMO / UNAVAILABLE.
 *
 * The whole point is that a viewer can tell at a glance whether a row was
 * observed from the marketplace, supplied by the operator, or synthesised for
 * development. The colours are deliberately distinct: DEMO and IMPORTED must
 * never read as LIVE.
 */

import { cn } from '@/lib/cn'
import type { SourceType } from '@/types/data'

export type BadgeKind = SourceType | 'unavailable'

const styles: Record<BadgeKind, string> = {
  // Green: genuinely observed from the marketplace.
  live: 'border-signal-ok/40 bg-signal-ok/10 text-signal-ok',
  // Accent: real data, but supplied by the operator rather than observed here.
  imported: 'border-accent/40 bg-accent-soft text-accent-text',
  // Neutral outline: synthetic. Must not look authoritative.
  demo: 'border-border-strong bg-background-alt text-muted',
  unavailable: 'border-border-hair bg-transparent text-subtle',
}

const labels: Record<BadgeKind, string> = {
  live: 'LIVE',
  imported: 'IMPORTED',
  demo: 'DEMO',
  unavailable: 'UNAVAILABLE',
}

const titles: Record<BadgeKind, string> = {
  live: 'Observed directly from the marketplace.',
  imported: 'Supplied as a CSV/JSON upload. Not observed by this system.',
  demo: 'Synthetic development fixture. Not real market data.',
  unavailable: 'No permitted route to collect from this platform.',
}

interface SourceBadgeProps {
  kind: BadgeKind
  className?: string
}

export function SourceBadge({ kind, className }: SourceBadgeProps) {
  return (
    <span
      title={titles[kind]}
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold tracking-wider',
        styles[kind],
        className,
      )}
    >
      {labels[kind]}
    </span>
  )
}
