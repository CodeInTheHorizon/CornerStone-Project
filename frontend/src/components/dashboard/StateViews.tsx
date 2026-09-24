import { motion, AnimatePresence } from 'framer-motion'
import { BarChart3, Compass, Database, AlertTriangle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/Button'
import { cn } from '@/lib/cn'

const contextIcons: Record<string, React.ElementType> = {
  chart: BarChart3,
  compass: Compass,
  database: Database,
  alert: AlertTriangle,
  default: Database,
}

export function SkeletonBlock({ label, lines = 3, className }: { label: string; lines?: number; className?: string }) {
  return (
    <div role="status" aria-label={label} className={cn('space-y-3', className)}>
      {Array.from({ length: lines }, (_, index) => (
        <div key={index} className="skeleton h-4" style={{ width: `${100 - index * 12}%` }} />
      ))}
    </div>
  )
}

export function EmptyState({
  icon = 'database',
  title,
  children,
  action,
  className,
}: {
  icon?: string
  title: string
  children?: React.ReactNode
  action?: { label: string; onClick: () => void }
  className?: string
}) {
  const IconComponent = contextIcons[icon] ?? contextIcons.default

  return (
    <AnimatePresence>
      <motion.div
        className={cn(
          'flex flex-col items-center rounded-card border border-dashed border-border-strong/60 px-6 py-10 text-center',
          className,
        )}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.2, 0, 0, 1] }}
      >
        <div className="relative">
          <div className="absolute inset-0 rounded-full bg-accent/10 blur-xl" />
          <span className="relative grid size-14 place-items-center rounded-2xl bg-linear-to-br from-accent-soft to-accent/5 text-accent-text">
            <IconComponent className="size-6" />
          </span>
        </div>
        <p className="mt-4 text-sm font-semibold">{title}</p>
        {children && (
          <div className="mt-2 max-w-sm text-sm leading-relaxed text-muted">{children}</div>
        )}
        {action && (
          <Button size="sm" variant="secondary" onClick={action.onClick} className="mt-4">
            {action.label}
          </Button>
        )}
      </motion.div>
    </AnimatePresence>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <motion.div
      className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-signal-down/30 bg-signal-down/5 px-4 py-3"
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
    >
      <p role="alert" className="flex min-w-0 flex-1 items-start gap-2 text-sm text-signal-down">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" />
        <span className="min-w-0 break-words">{message}</span>
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-full bg-signal-down/10 px-3 py-1.5 text-xs font-medium text-signal-down transition-colors hover:bg-signal-down/20"
        >
          <RefreshCw className="size-3" />
          Retry
        </button>
      )}
    </motion.div>
  )
}
