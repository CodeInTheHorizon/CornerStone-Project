/**
 * States plainly that visible observations are synthetic. Rendered whenever
 * stored data includes DEMO rows, so a DEMO chart can never pass as current data.
 */

import { Icon } from '@/components/Icon'
import { SourceBadge } from '@/components/SourceBadge'

export function DemoDataBanner({ demoRecords, liveRecords, notice }: { demoRecords: number; liveRecords: number; notice?: string }) {
  return (
    <div role="note" className="flex items-start gap-3 rounded-card border border-border-strong bg-background-alt px-4 py-3 text-sm">
      <Icon name="info" className="mt-0.5 size-4 shrink-0 text-muted" />
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2 font-medium">
          <SourceBadge kind="demo" /> DEMO data in use
        </p>
        <p className="mt-1 leading-relaxed text-muted">
          {demoRecords.toLocaleString()} stored record{demoRecords === 1 ? ' is' : 's are'} synthetic development fixtures, not observed marketplace listings.
          {liveRecords === 0 ? ' No LIVE observations are stored.' : ` ${liveRecords.toLocaleString()} LIVE record${liveRecords === 1 ? '' : 's'} are kept separate.`}
          {notice ? ` ${notice}` : ''}
        </p>
      </div>
    </div>
  )
}
