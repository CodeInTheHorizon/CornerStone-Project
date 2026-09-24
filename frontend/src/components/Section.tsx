/** Page section with consistent rhythm, shell width and heading treatment. */

import { Reveal } from '@/components/Reveal'
import { cn } from '@/lib/cn'

interface SectionProps {
  id: string
  eyebrow?: string
  heading: string
  description?: string
  /** Tints the band so adjacent sections read as separate. */
  tone?: 'base' | 'alt'
  className?: string
  children: React.ReactNode
}

export function Section({
  id,
  eyebrow,
  heading,
  description,
  tone = 'base',
  className,
  children,
}: SectionProps) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-heading`}
      className={cn(
        'py-20 sm:py-28',
        tone === 'alt' ? 'bg-surface/55' : 'bg-transparent',
        className,
      )}
    >
      <div className="mx-auto max-w-shell px-6">
        <Reveal className="max-w-2xl">
          {eyebrow && (
            <p className="inline-flex rounded-full bg-accent-soft px-3 py-1 text-xs font-semibold tracking-[0.14em] text-accent-text uppercase">
              {eyebrow}
            </p>
          )}
          <h2
            id={`${id}-heading`}
            className="mt-3 text-3xl font-semibold sm:text-4xl"
          >
            {heading}
          </h2>
          {description && (
            <p className="mt-4 text-base leading-relaxed text-muted">
              {description}
            </p>
          )}
        </Reveal>

        <div className="mt-14">{children}</div>
      </div>
    </section>
  )
}
