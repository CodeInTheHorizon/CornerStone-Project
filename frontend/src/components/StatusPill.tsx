/** Small labelled status indicator. The dot is decorative; the label carries the meaning. */

type Tone = 'ok' | 'warn' | 'down' | 'idle'

const toneClasses: Record<Tone, string> = {
  ok: 'text-signal-ok border-signal-ok/30 bg-signal-ok/10',
  warn: 'text-signal-warn border-signal-warn/30 bg-signal-warn/10',
  down: 'text-signal-down border-signal-down/30 bg-signal-down/10',
  idle: 'text-muted border-border-hair bg-background-alt',
}

interface StatusPillProps {
  tone: Tone
  children: React.ReactNode
}

export function StatusPill({ tone, children }: StatusPillProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${toneClasses[tone]}`}
    >
      <span className="size-1.5 shrink-0 rounded-full bg-current" aria-hidden="true" />
      {children}
    </span>
  )
}
