/** Hairline-bordered surface used as the base container primitive. */

import { cn } from '@/lib/cn'

interface PanelProps {
  className?: string
  children: React.ReactNode
}

export function Panel({ className, children }: PanelProps) {
  return (
    <div
      className={cn(
        'min-w-0 break-words rounded-panel border border-border-hair bg-surface p-6',
        className,
      )}
    >
      {children}
    </div>
  )
}
