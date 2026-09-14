import { useId } from 'react'
import type { TrendPoint } from '@/types/analytics'

export function ObservedLineChart({ points, field, label, unit }: { points: TrendPoint[]; field: 'price' | 'discount' | 'rating' | 'reviews'; label: string; unit: string }) {
  const id = useId()
  const values = points.map((point) => point[field]).filter((value): value is number => value !== null)
  if (values.length === 0) return <div className="rounded-card border border-border-hair p-4"><h3 className="text-sm font-medium tracking-normal">{label}</h3><p className="mt-3 text-sm text-muted">No valid observations.</p></div>
  const low = Math.min(...values)
  const high = Math.max(...values)
  const span = high - low || Math.max(Math.abs(high) * 0.1, 1)
  const min = Math.max(0, low - span * 0.1)
  const max = high + span * 0.1
  const start = Date.parse(points[0].timestamp)
  const end = Date.parse(points[points.length - 1].timestamp)
  const x = (stamp: string) => 65 + (end === start ? 0.5 : (Date.parse(stamp) - start) / (end - start)) * 525
  const y = (value: number) => 165 - (value - min) / (max - min) * 140
  const paths: string[] = []
  let segment = ''
  for (const point of points) {
    const value = point[field]
    if (value === null) { if (segment) paths.push(segment); segment = ''; continue }
    segment += `${segment ? ' L' : 'M'}${x(point.timestamp)},${y(value)}`
  }
  if (segment) paths.push(segment)
  return (
    <div className="min-w-0 rounded-card border border-border-hair p-4">
      <h3 className="text-sm font-medium tracking-normal">{label} <span className="text-xs text-subtle">({unit})</span></h3>
      {values.length < 2 && <p className="mt-2 text-xs text-muted">One valid observation; no trend inferred.</p>}
      <div className="overflow-x-auto" role="region" aria-label={`${label} chart, scroll horizontally on small screens`} tabIndex={0}>
      <svg viewBox="0 0 640 205" role="img" aria-labelledby={id} className="mt-3 min-w-[520px] w-full text-muted">
        <title id={id}>{label}: {values.length} recorded values from {points[0].timestamp} to {points[points.length - 1].timestamp}. Missing readings break the line.</title>
        {[min, (min + max) / 2, max].map((value, index) => <g key={index}><line x1="65" x2="590" y1={y(value)} y2={y(value)} stroke="currentColor" opacity="0.15" /><text x="58" y={y(value) + 4} textAnchor="end" fill="currentColor" fontSize="11">{value.toLocaleString(undefined, { maximumFractionDigits: 1 })}</text></g>)}
        {paths.map((path, index) => <path key={index} d={path} fill="none" stroke="currentColor" strokeWidth="2" className="text-accent-text" />)}
        {points.map((point, index) => point[field] === null ? null : <circle key={index} cx={x(point.timestamp)} cy={y(point[field])} r="3.5" fill="currentColor" className="text-accent-text"><title>{point.timestamp}: {point[field]} {unit}</title></circle>)}
        <text x="65" y="193" fill="currentColor" fontSize="11">{points[0].timestamp.slice(0, 10)}</text>
        <text x="590" y="193" textAnchor="end" fill="currentColor" fontSize="11">{points[points.length - 1].timestamp.slice(0, 10)}</text>
      </svg>
      </div>
      <p className="text-xs text-subtle">UTC observation time · missing readings are not interpolated</p>
    </div>
  )
}
