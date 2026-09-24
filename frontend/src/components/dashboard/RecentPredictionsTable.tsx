/** Saved predictions as a compact table; scrolls inside its own region on narrow screens. */

import { Link } from 'react-router-dom'

import { SourceBadge } from '@/components/SourceBadge'
import { StatusPill } from '@/components/StatusPill'
import { PlatformBadge } from '@/components/dashboard/PlatformBadge'
import { SectionCard } from '@/components/dashboard/SectionCard'
import { EmptyState, ErrorState, SkeletonBlock } from '@/components/dashboard/StateViews'
import { qualityPresentation } from '@/lib/modelQuality'
import { timestamp } from '@/lib/predictionFormat'
import type { QualityStatus } from '@/types/data'
import type { PredictionHistory } from '@/types/prediction'

const head = 'px-3 py-2.5 text-left text-xs font-medium whitespace-nowrap text-subtle'
const cell = 'px-3 py-3 align-middle'

export function RecentPredictionsTable({ history, error, onRetry }: { history: PredictionHistory | null; error: string; onRetry: () => void }) {
  return (
    <SectionCard
      title="Recent predictions"
      description={history && history.total > 0 ? `Latest ${history.items.length} of ${history.total}. Each keeps the model quality measured when it was made.` : 'Your saved experimental predictions.'}
      actions={<Link to="/dashboard/predictor" className="text-sm font-medium text-accent-text hover:underline">Open ML Predictor</Link>}
      bodyClassName="px-0 sm:px-0"
      className="h-full"
    >
      <div className="px-5 sm:px-6">
        {error && <ErrorState message={error} onRetry={onRetry} />}
        {!history && !error && <SkeletonBlock label="Loading recent predictions" lines={4} />}
        {history?.total === 0 && <EmptyState icon="compass" title="No saved predictions yet">Predictions you run are saved here with their model quality and data provenance.</EmptyState>}
      </div>
      {history && history.items.length > 0 && (
        <div role="region" aria-label="Recent predictions table, scroll horizontally on small screens" tabIndex={0} className="relative overflow-x-auto">
          <table className="w-full min-w-[660px] text-sm">
            <caption className="sr-only">Recent saved predictions</caption>
            <thead className="border-y border-border-hair bg-background-alt">
              <tr>
                <th scope="col" className={`${head} sticky left-0 bg-background-alt pl-5 sm:pl-6`}>Product</th>
                <th scope="col" className={head}>Top score platform</th>
                <th scope="col" className={`${head} text-right`}>Score</th>
                <th scope="col" className={head}>Input data</th>
                <th scope="col" className={head}>Model quality</th>
                <th scope="col" className={head}>Saved</th>
                <th scope="col" className={`${head} pr-5 sm:pr-6`}><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {history.items.map((item) => {
                const status = item.model?.quality_status && item.model.quality_status in qualityPresentation ? qualityPresentation[item.model.quality_status as QualityStatus] : null
                return (
                  <tr key={item.id} className="border-b border-border-hair last:border-0">
                    <th scope="row" className={`${cell} sticky left-0 max-w-[14rem] bg-surface pl-5 text-left font-medium sm:pl-6`}>
                      <span className="block truncate" title={item.product}>{item.product}</span>
                    </th>
                    <td className={cell}>{item.recommended_platform ? <PlatformBadge platform={item.recommended_platform} /> : <span className="text-subtle">Unavailable</span>}</td>
                    <td className={`${cell} text-right font-semibold tabular-nums`}>{item.top_score?.toFixed(1) ?? '—'}</td>
                    <td className={cell}><span className="flex gap-1">{item.source_types.map((source) => <SourceBadge key={source} kind={source} />)}</span></td>
                    <td className={cell}>{status ? <StatusPill tone={status.tone}>{status.label}</StatusPill> : <span className="text-xs text-subtle">Not recorded</span>}</td>
                    <td className={`${cell} text-xs whitespace-nowrap text-muted`}>{timestamp(item.created_at)}</td>
                    <td className={`${cell} pr-5 text-right sm:pr-6`}>
                      <Link to={`/dashboard/predictor?prediction=${item.id}`} aria-label={`View saved result #${item.id} for ${item.product}`} className="text-sm font-medium whitespace-nowrap text-accent-text hover:underline">
                        View #{item.id}
                      </Link>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  )
}
