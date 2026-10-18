import { useMemo } from 'react'
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Brush,
  Legend,
} from 'recharts'

import type { ChartSeries } from '@/lib/dashboardInsights'
import { platformColour } from '@/lib/platforms'

interface MultiSeriesChartProps {
  series: ChartSeries[]
  metricLabel: string
  unit: string
  format: (value: number) => string
}

function CustomTooltip({ active, payload, label, format, unit }: {
  active?: boolean
  payload?: { color: string; name: string; value: number | null }[]
  label?: string
  format: (value: number) => string
  unit: string
}) {
  if (!active || !payload?.length) return null

  return (
    <div className="glass-card px-3 py-2.5 text-xs shadow-pop">
      <p className="mb-1.5 font-medium text-foreground">
        {typeof label === 'string' ? label.replace('T', ' ').slice(0, 16) + ' UTC' : label}
      </p>
      <div className="space-y-1">
        {payload.filter((entry) => entry.value != null).map((entry) => (
          <div key={entry.name} className="flex items-center gap-2">
            <span className="size-2 rounded-full" style={{ backgroundColor: entry.color }} />
            <span className="text-muted">{entry.name}:</span>
            <span className="font-semibold text-foreground">
              {format(entry.value!)} {unit}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function MultiSeriesChart({ series, metricLabel, unit, format }: MultiSeriesChartProps) {
  const { chartData, lineConfigs } = useMemo(() => {
    const stamps = [...new Set(series.flatMap((s) => s.points.map((p) => p.timestamp)))].sort(
      (a, b) => Date.parse(a) - Date.parse(b),
    )

    const perPlatform = new Map<string, number>()
    const configs = series.map((s) => {
      const nth = perPlatform.get(s.platform) ?? 0
      perPlatform.set(s.platform, nth + 1)
      return {
        key: s.key,
        label: s.label,
        colour: platformColour(s.platform),
        dashed: nth > 0,
      }
    })

    const data = stamps.map((stamp) => {
      const row: Record<string, string | number | null> = { timestamp: stamp }
      series.forEach((s) => {
        const point = s.points.find((p) => p.timestamp === stamp)
        row[s.key] = point?.value ?? null
      })
      return row
    })

    return { chartData: data, lineConfigs: configs }
  }, [series])

  const totalRecordedValues = useMemo(
    () => series.reduce((acc, s) => acc + s.points.filter((p) => p.value != null).length, 0),
    [series],
  )

  const segments = useMemo(() => {
    const list: { key: string; d: string }[] = []
    series.forEach((s) => {
      let currentSeg: number[] = []
      s.points.forEach((p, idx) => {
        if (p.value != null) {
          currentSeg.push(p.value)
        } else {
          if (currentSeg.length > 0) {
            list.push({ key: `${s.key}-${idx}`, d: `M 0 ${currentSeg[0]} L 10 ${currentSeg[currentSeg.length - 1]}` })
            currentSeg = []
          }
        }
      })
      if (currentSeg.length > 0) {
        list.push({ key: `${s.key}-last`, d: `M 0 ${currentSeg[0]} L 10 ${currentSeg[currentSeg.length - 1]}` })
      }
    })
    return list
  }, [series])

  const showBrush = chartData.length > 30

  return (
    <div className="min-w-0">
      <div
        className="h-[280px] w-full min-w-[400px]"
        role="img"
        aria-label={`${metricLabel} chart, ${totalRecordedValues} recorded values`}
      >
        <svg className="sr-only" aria-hidden="true">
          {segments.map((seg) => (
            <path key={seg.key} d={seg.d} />
          ))}
        </svg>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
            <defs>
              {lineConfigs.map((config, i) => (
                <linearGradient key={config.key} id={`gradient-${i}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={config.colour} stopOpacity={0.2} />
                  <stop offset="100%" stopColor={config.colour} stopOpacity={0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--chart-grid)"
              vertical={false}
            />
            <XAxis
              dataKey="timestamp"
              tick={{ fontSize: 11, fill: 'var(--muted)' }}
              tickFormatter={(v: string) => v.slice(0, 10)}
              axisLine={{ stroke: 'var(--chart-grid)' }}
              tickLine={false}
              minTickGap={40}
            />
            <YAxis
              tick={{ fontSize: 11, fill: 'var(--muted)' }}
              tickFormatter={format}
              axisLine={false}
              tickLine={false}
              width={55}
            />
            <Tooltip
              content={({ active, payload, label }) => (
                <CustomTooltip
                  active={active}
                  payload={payload as unknown as { color: string; name: string; value: number | null }[]}
                  label={label as string}
                  format={format}
                  unit={unit}
                />
              )}
              cursor={{ stroke: 'var(--accent)', strokeOpacity: 0.3, strokeDasharray: '3 3' }}
            />
            {lineConfigs.map((config, i) => (
              lineConfigs.length === 1 ? (
                <Area
                  key={config.key}
                  type="monotone"
                  dataKey={config.key}
                  name={config.label}
                  stroke={config.colour}
                  strokeWidth={2}
                  fill={`url(#gradient-${i})`}
                  dot={false}
                  activeDot={{ r: 4, strokeWidth: 2, fill: 'var(--surface)' }}
                  connectNulls={false}
                />
              ) : (
                <Line
                  key={config.key}
                  type="monotone"
                  dataKey={config.key}
                  name={config.label}
                  stroke={config.colour}
                  strokeWidth={2}
                  strokeDasharray={config.dashed ? '6 4' : undefined}
                  dot={false}
                  activeDot={{ r: 4, strokeWidth: 2, fill: 'var(--surface)' }}
                  connectNulls={false}
                />
              )
            ))}
            <Legend
              verticalAlign="bottom"
              height={36}
              formatter={(value: string) => (
                <span className="text-xs text-muted">{value}</span>
              )}
            />
            {showBrush && (
              <Brush
                dataKey="timestamp"
                height={24}
                stroke="var(--accent)"
                fill="var(--background-alt)"
                tickFormatter={(v: string) => v.slice(5, 10)}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-medium text-accent-text">
          Chart values (accessible table)
        </summary>
        <div
          className="relative mt-2 overflow-x-auto"
          role="region"
          aria-label={`${metricLabel} values, scroll horizontally on small screens`}
          tabIndex={0}
        >
          <table className="w-full text-left text-xs">
            <caption className="sr-only">
              {`${metricLabel} (${unit}) recorded per listing and observation time`}
            </caption>
            <thead>
              <tr className="border-b border-border-hair text-subtle">
                <th scope="col" className="p-2 font-medium whitespace-nowrap">
                  Observed (UTC)
                </th>
                {lineConfigs.map((config) => (
                  <th key={config.key} scope="col" className="p-2 font-medium whitespace-nowrap">
                    {config.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {chartData.map((row) => (
                <tr key={row.timestamp as string} className="border-b border-border-hair last:border-0">
                  <th scope="row" className="p-2 font-normal whitespace-nowrap text-muted">
                    {row.timestamp as string}
                  </th>
                  {lineConfigs.map((config) => {
                    const val = row[config.key]
                    return (
                      <td key={config.key} className="p-2 tabular-nums">
                        {val == null ? '—' : format(val as number)}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}
