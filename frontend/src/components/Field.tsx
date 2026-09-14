/** Labelled form control with inline error messaging. */

import { useId } from 'react'

import { cn } from '@/lib/cn'

interface FieldProps {
  label: string
  name: string
  value: string
  onChange: (value: string) => void
  error?: string
  type?: string
  placeholder?: string
  autoComplete?: string
  /** Renders a textarea instead of an input. */
  multiline?: boolean
  rows?: number
}

const control =
  'w-full rounded-card border bg-background px-3.5 py-2.5 text-sm text-foreground ' +
  'placeholder:text-subtle transition-colors ' +
  'focus:border-accent'

export function Field({
  label,
  name,
  value,
  onChange,
  error,
  type = 'text',
  placeholder,
  autoComplete,
  multiline = false,
  rows = 5,
}: FieldProps) {
  const id = useId()
  const errorId = `${id}-error`
  const classes = cn(control, error ? 'border-signal-down' : 'border-border-hair')

  const shared = {
    id,
    name,
    value,
    placeholder,
    autoComplete,
    'aria-invalid': error ? (true as const) : undefined,
    'aria-describedby': error ? errorId : undefined,
    className: classes,
  }

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-muted">
        {label}
      </label>

      <div className="mt-2">
        {multiline ? (
          <textarea
            {...shared}
            rows={rows}
            onChange={(e) => onChange(e.target.value)}
          />
        ) : (
          <input
            {...shared}
            type={type}
            onChange={(e) => onChange(e.target.value)}
          />
        )}
      </div>

      {error && (
        <p id={errorId} role="alert" className="mt-2 text-xs text-signal-down">
          {error}
        </p>
      )}
    </div>
  )
}
