import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { AreaChart, Area, ResponsiveContainer } from 'recharts'
import { cn } from '@/lib/cn'
import type { LucideIcon } from 'lucide-react'
import { Database, Brain, Target, AlertTriangle, Compass } from 'lucide-react'

type Tone = 'accent' | 'ok' | 'warn' | 'down' | 'idle'

const iconTones: Record<Tone, { bg: string; text: string; gradient: string }> = {
  accent: { bg: 'bg-accent-soft', text: 'text-accent-text', gradient: 'from-accent/20 to-accent-secondary/10' },
  ok: { bg: 'bg-signal-ok/10', text: 'text-signal-ok', gradient: 'from-signal-ok/15 to-signal-ok/5' },
  warn: { bg: 'bg-signal-warn/10', text: 'text-signal-warn', gradient: 'from-signal-warn/15 to-signal-warn/5' },
  down: { bg: 'bg-signal-down/10', text: 'text-signal-down', gradient: 'from-signal-down/15 to-signal-down/5' },
  idle: { bg: 'bg-background-alt', text: 'text-muted', gradient: 'from-background-alt to-background' },
}

const sparkColors: Record<Tone, string> = {
  accent: 'var(--accent)',
  ok: 'var(--signal-ok)',
  warn: 'var(--signal-warn)',
  down: 'var(--signal-down)',
  idle: 'var(--muted)',
}

const defaultIcons: Record<string, LucideIcon> = {
  database: Database,
  brain: Brain,
  target: Target,
  alert: AlertTriangle,
  compass: Compass,
}

interface TrendInfo {
  direction: 'up' | 'down' | 'flat'
  percentage: number
  label: string
}

interface SummaryCardProps {
  label: string
  icon: string
  lucideIcon?: LucideIcon
  value?: string | number
  unavailable?: string
  hint?: React.ReactNode
  loading?: boolean
  tone?: Tone
  footer?: React.ReactNode
  trend?: TrendInfo
  sparkline?: number[]
}

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0)
  const ref = useRef<number | null>(null)

  useEffect(() => {
    const start = performance.now()
    const duration = 800
    const from = 0
    const to = value

    function tick(now: number) {
      const elapsed = now - start
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplay(Math.round(from + (to - from) * eased))
      if (progress < 1) ref.current = requestAnimationFrame(tick)
    }

    ref.current = requestAnimationFrame(tick)
    return () => { if (ref.current) cancelAnimationFrame(ref.current) }
  }, [value])

  return <>{display.toLocaleString()}</>
}

function TrendBadge({ trend }: { trend: TrendInfo }) {
  const colors = {
    up: 'text-signal-ok bg-signal-ok/10',
    down: 'text-signal-down bg-signal-down/10',
    flat: 'text-muted bg-background-alt',
  }
  const arrows = { up: '↑', down: '↓', flat: '→' }

  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums', colors[trend.direction])}>
      {arrows[trend.direction]} {Math.abs(trend.percentage).toFixed(1)}%
      <span className="font-normal text-muted">{trend.label}</span>
    </span>
  )
}

function Sparkline({ data, tone }: { data: number[]; tone: Tone }) {
  const chartData = data.map((v, i) => ({ i, v }))
  const color = sparkColors[tone]

  return (
    <div className="h-10 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`spark-${tone}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#spark-${tone})`}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

export function SummaryCard({
  label,
  icon,
  lucideIcon,
  value,
  unavailable,
  hint,
  loading = false,
  tone = 'accent',
  footer,
  trend,
  sparkline,
}: SummaryCardProps) {
  const toneConfig = iconTones[tone]
  const IconComponent = lucideIcon ?? defaultIcons[icon]

  return (
    <motion.div
      className="surface-card flex h-full min-w-0 flex-col overflow-hidden p-5 transition-colors duration-200 ease-standard hover:border-accent/30 hover:shadow-pop"
      whileHover={{ y: -2, transition: { duration: 0.2 } }}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.2, 0, 0, 1] }}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-[13px] font-medium text-muted">{label}</p>
        <span
          className={cn(
            'grid size-10 shrink-0 place-items-center rounded-xl bg-linear-to-br',
            toneConfig.gradient,
            toneConfig.text,
          )}
          aria-hidden="true"
        >
          {IconComponent ? (
            <IconComponent className="size-[18px]" />
          ) : (
            <span className="text-sm font-bold">{icon.charAt(0).toUpperCase()}</span>
          )}
        </span>
      </div>

      {loading ? (
        <div className="mt-2 h-9 py-1" role="status" aria-label={`Loading ${label}`}>
          <div className="skeleton h-7 w-24" />
        </div>
      ) : unavailable ? (
        <p className="mt-2 text-lg font-semibold text-subtle">{unavailable}</p>
      ) : (
        <div className="mt-1 flex items-end gap-3">
          <p
            className={
              typeof value === 'number'
                ? 'text-[28px] leading-9 font-semibold tracking-tight tabular-nums'
                : 'text-base leading-snug font-semibold'
            }
          >
            {typeof value === 'number' ? <AnimatedNumber value={value} /> : value}
          </p>
          {trend && <TrendBadge trend={trend} />}
        </div>
      )}

      {sparkline && sparkline.length > 1 && (
        <div className="mt-2">
          <Sparkline data={sparkline} tone={tone} />
        </div>
      )}

      {footer && <div className="mt-2 flex flex-wrap items-center gap-1.5">{footer}</div>}
      {hint && <p className="mt-auto pt-3 text-xs leading-relaxed text-subtle">{hint}</p>}
    </motion.div>
  )
}
