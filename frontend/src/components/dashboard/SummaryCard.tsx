/**
 * Dashboard metric tile.
 *
 * `value` is for figures that are genuinely known. When a number does not
 * exist yet, pass `unavailable` instead — the tile then says so plainly rather
 * than showing a placeholder digit that could be mistaken for a real metric.
 */

import { Icon, type IconName } from '@/components/Icon'

interface SummaryCardProps {
  label: string
  icon: IconName
  value?: string | number
  /** Shown in place of a value, e.g. "Not trained yet". */
  unavailable?: string
  hint?: string
}

export function SummaryCard({
  label,
  icon,
  value,
  unavailable,
  hint,
}: SummaryCardProps) {
  return (
    <div className="rounded-panel border border-border-hair bg-surface p-5 transition-colors duration-300 hover:border-accent/50">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium tracking-[0.14em] text-subtle uppercase">
          {label}
        </p>
        <span
          className="grid size-8 shrink-0 place-items-center rounded-card bg-accent-soft text-accent-text"
          aria-hidden="true"
        >
          <Icon name={icon} className="size-4" />
        </span>
      </div>

      {unavailable ? (
        <p className="mt-4 text-lg font-medium text-subtle">{unavailable}</p>
      ) : (
        // Numbers get display size; text (a timestamp, say) would overflow at
        // that scale, so it renders one step down.
        <p
          className={
            typeof value === 'number'
              ? 'mt-4 text-3xl font-semibold tabular-nums'
              : 'mt-4 text-base font-medium'
          }
        >
          {value}
        </p>
      )}

      {hint && <p className="mt-2 text-xs leading-relaxed text-subtle">{hint}</p>}
    </div>
  )
}
