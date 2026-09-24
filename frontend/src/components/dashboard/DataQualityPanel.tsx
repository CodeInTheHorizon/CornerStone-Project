import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, AlertTriangle, Info, CheckCircle2 } from 'lucide-react'

import { SectionCard } from '@/components/dashboard/SectionCard'
import { SkeletonBlock } from '@/components/dashboard/StateViews'
import type { AttentionItem, AttentionTone } from '@/lib/dashboardInsights'
import { cn } from '@/lib/cn'

const tones: Record<AttentionTone, { label: string; badge: string; icon: typeof AlertTriangle; rank: number }> = {
  down: { label: 'Critical', badge: 'border-signal-down/30 bg-signal-down/10 text-signal-down', icon: AlertTriangle, rank: 0 },
  warn: { label: 'Warning', badge: 'border-signal-warn/30 bg-signal-warn/10 text-signal-warn', icon: AlertTriangle, rank: 1 },
  idle: { label: 'Note', badge: 'border-border-hair bg-background-alt text-muted', icon: Info, rank: 2 },
}

function healthScore(items: AttentionItem[]): number {
  if (items.length === 0) return 100
  let penalty = 0
  for (const item of items) {
    if (item.tone === 'down') penalty += 25
    else if (item.tone === 'warn') penalty += 10
    else penalty += 3
  }
  return Math.max(0, 100 - penalty)
}

function SeverityGroup({ tone, items }: { tone: AttentionTone; items: AttentionItem[] }) {
  const [open, setOpen] = useState(tone === 'down')
  const config = tones[tone]
  const ToneIcon = config.icon

  return (
    <div className="rounded-xl border border-border-hair">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left text-sm transition-colors hover:bg-background-alt/50"
      >
        <ToneIcon className={cn('size-4 shrink-0', tone === 'down' ? 'text-signal-down' : tone === 'warn' ? 'text-signal-warn' : 'text-muted')} />
        <span className="flex-1 font-medium">{config.label}</span>
        <span className={cn('rounded-full border px-1.5 py-px text-[10px] font-semibold tabular-nums', config.badge)}>
          {items.length}
        </span>
        <ChevronDown className={cn('size-3.5 text-muted transition-transform duration-200', open && 'rotate-180')} />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <ul className="divide-y divide-border-hair border-t border-border-hair px-3.5">
              {items.map((item) => (
                <li key={item.id} className="py-2.5">
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="mt-0.5 text-xs leading-relaxed text-muted">{item.detail}</p>
                  {item.link && (
                    <Link to={item.link.to} className="mt-1 inline-block text-xs font-medium text-accent-text hover:underline">
                      {item.link.label}
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export function DataQualityPanel({ items, loading }: { items: AttentionItem[]; loading: boolean }) {
  const score = healthScore(items)
  const grouped = (['down', 'warn', 'idle'] as AttentionTone[])
    .map((tone) => ({ tone, items: items.filter((i) => i.tone === tone) }))
    .filter((g) => g.items.length > 0)

  return (
    <SectionCard
      title="Data quality & attention"
      description="Limitations that apply to every score on this page."
      className="h-full"
    >
      {loading ? <SkeletonBlock label="Loading data quality checks" lines={4} /> : items.length === 0 ? (
        <div className="flex items-center gap-3">
          <CheckCircle2 className="size-5 text-signal-ok" />
          <p className="text-sm text-muted">No data-quality issues were reported by the loaded status.</p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                'flex size-11 items-center justify-center rounded-xl text-lg font-bold tabular-nums',
                score >= 70 ? 'bg-signal-ok/10 text-signal-ok' : score >= 40 ? 'bg-signal-warn/10 text-signal-warn' : 'bg-signal-down/10 text-signal-down',
              )}
            >
              {score}
            </div>
            <div>
              <p className="text-sm font-semibold">Health Score</p>
              <p className="text-xs text-muted">
                {score >= 70 ? 'Data quality is good' : score >= 40 ? 'Some issues need attention' : 'Critical issues detected'}
              </p>
            </div>
          </div>

          <div className="space-y-2">
            {grouped.map((g) => (
              <SeverityGroup key={g.tone} tone={g.tone} items={g.items} />
            ))}
          </div>
        </div>
      )}
    </SectionCard>
  )
}
