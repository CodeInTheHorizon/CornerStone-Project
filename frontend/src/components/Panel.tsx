/** Hairline-bordered surface used as the base container primitive. */

interface PanelProps {
  className?: string
  children: React.ReactNode
}

export function Panel({ className = '', children }: PanelProps) {
  return (
    <div
      className={`rounded-card border border-ink-800 bg-ink-900 p-6 ${className}`}
    >
      {children}
    </div>
  )
}
