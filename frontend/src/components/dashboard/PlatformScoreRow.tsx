/**
 * One marketplace in a saved prediction: rank, heuristic opportunity score on
 * the fixed 0-100 scale, signal coverage and provenance. A missing score says
 * why instead of drawing an empty bar.
 */

import { SourceBadge } from '@/components/SourceBadge'
import { PlatformBadge } from '@/components/dashboard/PlatformBadge'
import { platformColour } from '@/lib/platforms'
import { title } from '@/lib/predictionFormat'
import type { PlatformPrediction } from '@/types/prediction'

export function PlatformScoreRow({ platform, rank, recommended = false }: { platform: PlatformPrediction; rank: number | null; recommended?: boolean }) {
  const score = platform.opportunity_score
  return (
    <div className="min-w-0">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm">
        <span className="flex min-w-0 items-center gap-2">
          <span className="w-5 shrink-0 text-xs tabular-nums text-subtle">{rank === null ? '—' : `#${rank}`}</span>
          <PlatformBadge platform={platform.platform} />
          {recommended && <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-semibold tracking-wide text-accent-text uppercase">Top score</span>}
        </span>
        <span className="flex items-center gap-2">
          {platform.source_type && <SourceBadge kind={platform.source_type} />}
          <span className="font-semibold tabular-nums">{score == null ? 'No score' : `${score.toFixed(1)} / 100`}</span>
        </span>
      </div>
      {score != null ? (
        <>
          <div
            role="meter"
            aria-label={`${title(platform.platform)} opportunity score`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={score}
            className="mt-2 ml-7 h-2 overflow-hidden rounded-full bg-chart-track"
          >
            <div className="h-full rounded-full transition-[width] duration-200" style={{ width: `${score}%`, backgroundColor: platformColour(platform.platform) }} />
          </div>
          <p className="mt-1.5 ml-7 text-xs text-subtle">
            {platform.coverage_weight}% signal coverage
            {platform.key_factors.length > 0 && <> · strongest: {platform.key_factors.slice(0, 2).map(title).join(', ')}</>}
            {platform.stale && <span className="font-medium text-signal-warn"> · STALE observation</span>}
          </p>
        </>
      ) : (
        <p className="mt-1.5 ml-7 text-xs text-subtle">{platform.reason ?? 'Insufficient data / unavailable.'}</p>
      )}
    </div>
  )
}
