/**
 * A primary dashboard action.
 *
 * When the action cannot run yet, `blockedReason` explains what is missing.
 * The button is disabled rather than hidden, so the workflow stays visible.
 */

import { Button } from '@/components/Button'
import { Icon, type IconName } from '@/components/Icon'

interface ActionCardProps {
  icon: IconName
  title: string
  description: string
  actionLabel: string
  /** Non-empty means the action is unavailable, and why. */
  blockedReason?: string
  onAction?: () => void
}

export function ActionCard({
  icon,
  title,
  description,
  actionLabel,
  blockedReason,
  onAction,
}: ActionCardProps) {
  const blocked = Boolean(blockedReason)

  return (
    <div className="flex h-full flex-col rounded-panel border border-border-hair bg-surface p-7">
      <span
        className="grid size-11 place-items-center rounded-card bg-accent-soft text-accent-text"
        aria-hidden="true"
      >
        <Icon name={icon} className="size-[22px]" />
      </span>

      <h3 className="mt-5 text-lg font-semibold">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted">{description}</p>

      <div className="mt-6 flex-1" />

      {blockedReason && (
        <p className="mb-4 flex items-start gap-2 text-xs leading-relaxed text-subtle">
          <Icon name="alert" className="mt-0.5 size-3.5 shrink-0" />
          <span>{blockedReason}</span>
        </p>
      )}

      {/* A dimmed accent fill still reads as the primary call to action. An
          unavailable action uses the outline variant so it looks inactive. */}
      <Button
        onClick={onAction}
        disabled={blocked}
        variant={blocked ? 'secondary' : 'primary'}
        className="w-full"
      >
        {actionLabel}
      </Button>
    </div>
  )
}
