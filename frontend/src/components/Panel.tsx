/** Card surface used as the base container primitive. */

import { cn } from '@/lib/cn'

interface PanelProps {
  className?: string
  children: React.ReactNode
}

export function Panel({ className, children }: PanelProps) {
  return (
    <div className={cn('surface-card min-w-0 break-words p-5 sm:p-6', className)}>
      {children}
    </div>
  )
}
