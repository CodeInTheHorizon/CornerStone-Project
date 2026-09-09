/** Inline form-level error or notice, styled from the shared signal tokens. */

import { Icon } from '@/components/Icon'

type Tone = 'error' | 'info'

const tones: Record<Tone, string> = {
  error: 'border-signal-down/30 bg-signal-down/10 text-signal-down',
  info: 'border-signal-warn/30 bg-signal-warn/10 text-signal-warn',
}

interface FormAlertProps {
  tone?: Tone
  children: React.ReactNode
}

export function FormAlert({ tone = 'error', children }: FormAlertProps) {
  return (
    <p
      role="alert"
      className={`flex items-start gap-2.5 rounded-card border px-4 py-3 text-sm ${tones[tone]}`}
    >
      <Icon name="alert" className="mt-0.5 size-4 shrink-0" />
      <span>{children}</span>
    </p>
  )
}
