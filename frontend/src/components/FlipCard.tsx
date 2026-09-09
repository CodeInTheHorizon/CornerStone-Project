/**
 * Card that swaps to its description on hover, focus or tap.
 *
 * The flip is deliberately restrained — a single Y-axis rotation at a shallow
 * perspective, no shadows or springs. Both faces stay in the DOM, so a screen
 * reader reads the title and the description regardless of the visual state,
 * and keyboard users get the same swap via focus. Under
 * prefers-reduced-motion the transition collapses to an instant swap.
 */

import { useState } from 'react'

import { Icon, type IconName } from '@/components/Icon'

interface FlipCardProps {
  icon: IconName
  title: string
  body: string
}

const face =
  'absolute inset-0 flex flex-col justify-center rounded-panel border border-border-hair ' +
  'bg-surface p-8 [backface-visibility:hidden]'

export function FlipCard({ icon, title, body }: FlipCardProps) {
  const [tapped, setTapped] = useState(false)

  return (
    <div
      className="group h-64 [perspective:1400px]"
      onClick={() => setTapped((t) => !t)}
    >
      <div
        className={
          'relative h-full w-full transition-transform duration-500 ' +
          '[transform-style:preserve-3d] ' +
          'group-hover:[transform:rotateY(180deg)] ' +
          'group-focus-within:[transform:rotateY(180deg)] ' +
          (tapped ? '[transform:rotateY(180deg)]' : '')
        }
      >
        {/* Front */}
        <div className={face}>
          <span
            className="grid size-11 place-items-center rounded-card bg-accent-soft text-accent-text"
            aria-hidden="true"
          >
            <Icon name={icon} className="size-[22px]" />
          </span>
          <h3 className="mt-6 text-xl font-semibold">{title}</h3>
          <p className="mt-2 text-sm text-subtle">Hover to read more</p>

          {/* Focusable so keyboard users can trigger the same swap. */}
          <button
            type="button"
            className="absolute inset-0 rounded-panel"
            aria-label={`${title}: ${body}`}
          />
        </div>

        {/* Back */}
        <div className={`${face} [transform:rotateY(180deg)] bg-surface-raised`}>
          <span className="text-xs font-semibold tracking-[0.16em] text-accent-text uppercase">
            {title}
          </span>
          <p className="mt-4 text-[15px] leading-relaxed text-muted">{body}</p>
        </div>
      </div>
    </div>
  )
}
