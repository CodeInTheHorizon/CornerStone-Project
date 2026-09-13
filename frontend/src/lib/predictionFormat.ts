export const percent = (value: number | null | undefined) => value == null ? 'Unavailable' : `${(value * 100).toFixed(1)}%`
export const title = (value: string) => value.replaceAll('_', ' ').replace(/^./, (c) => c.toUpperCase())
export const timestamp = (value: string | null) => value ? new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`).toLocaleString() : 'Unknown observation time'
