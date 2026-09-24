import { motion } from 'framer-motion'
import { platformColour } from '@/lib/platforms'
import { title } from '@/lib/predictionFormat'

interface PlatformHealthProps {
  platform: string
  available: boolean
  reason?: string | null
  recordCount?: number
  lastCollection?: string | null
}

export function PlatformHealthCard({ platform, available, reason, recordCount, lastCollection }: PlatformHealthProps) {
  return (
    <motion.div
      className="flex items-center gap-3 rounded-xl border border-border-hair bg-surface p-3 transition-colors hover:border-accent/20"
      whileHover={{ y: -1 }}
      transition={{ duration: 0.15 }}
    >
      <span
        className="size-2.5 shrink-0 rounded-full"
        style={{ backgroundColor: available ? 'var(--signal-ok)' : 'var(--muted)' }}
        title={available ? 'Available' : 'Unavailable'}
      />
      <span
        className="size-3 shrink-0 rounded-[3px]"
        style={{ backgroundColor: platformColour(platform) }}
        aria-hidden="true"
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{title(platform)}</p>
        {reason && <p className="truncate text-[11px] text-muted">{reason}</p>}
      </div>
      <div className="text-right">
        {recordCount != null && (
          <p className="text-xs font-semibold tabular-nums">{recordCount.toLocaleString()}</p>
        )}
        {lastCollection && (
          <p className="text-[10px] text-subtle">{new Date(lastCollection).toLocaleDateString()}</p>
        )}
      </div>
    </motion.div>
  )
}
