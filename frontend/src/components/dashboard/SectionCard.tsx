/** A titled workspace card: heading, optional description and actions, then content. */

import { useId } from 'react'

import { cn } from '@/lib/cn'

interface SectionCardProps {
  title: string
  description?: React.ReactNode
  actions?: React.ReactNode
  className?: string
  bodyClassName?: string
  /** Heading level; page sections default to h2. */
  level?: 2 | 3
  children: React.ReactNode
}

export function SectionCard({ title, description, actions, className, bodyClassName, level = 2, children }: SectionCardProps) {
  const id = useId()
  const Heading = level === 2 ? 'h2' : 'h3'
  return (
    <section aria-labelledby={id} className={cn('surface-card flex min-w-0 flex-col break-words', className)}>
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5 sm:px-6">
        <div className="min-w-0 flex-1">
          <Heading id={id} className="text-base font-semibold tracking-tight">{title}</Heading>
          {description && <p className="mt-1 text-sm leading-relaxed text-muted">{description}</p>}
        </div>
        {actions && <div className="flex min-w-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
      <div className={cn('min-w-0 flex-1 px-5 pt-4 pb-5 sm:px-6 sm:pb-6', bodyClassName)}>{children}</div>
    </section>
  )
}
