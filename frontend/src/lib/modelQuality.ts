import type { QualityStatus } from '@/types/data'

type Tone = 'ok' | 'warn' | 'down' | 'idle'

/** Human labels for the Phase 12 quality gate. Only "validated" reads as trustworthy. */
export const qualityPresentation: Record<QualityStatus, { tone: Tone; label: string }> = {
  below_baseline: { tone: 'down', label: 'Below baseline' },
  experimental: { tone: 'warn', label: 'Experimental' },
  candidate: { tone: 'warn', label: 'Candidate (not validated)' },
  validated: { tone: 'ok', label: 'Validated' },
}

export const DEMO_MODEL_MESSAGE = 'Development model — trained on synthetic DEMO data.'
export const BELOW_BASELINE_MESSAGE = 'This model does not outperform the validation baseline.'

export function percentOrDash(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(1)}%`
}

export function dateOnly(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : '—'
}
