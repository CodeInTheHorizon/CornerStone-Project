/**
 * Pure derivations for the overview dashboard. Everything here reads fields the
 * backend already returned; nothing is estimated, extrapolated or invented.
 */

import { collectorStateLabel } from '@/lib/collectorState'
import { BELOW_BASELINE_MESSAGE, qualityPresentation } from '@/lib/modelQuality'
import { title } from '@/lib/predictionFormat'
import type { AnalyticsSummary, TrendPoint, TrendSeries } from '@/types/analytics'
import type { ModelStatus } from '@/types/data'
import type { PredictionResult } from '@/types/prediction'

export type AttentionTone = 'down' | 'warn' | 'idle'

export interface AttentionItem {
  id: string
  tone: AttentionTone
  title: string
  detail: string
  link?: { to: string; label: string }
}

const percent = (value: number | null | undefined) => value == null ? 'unknown' : `${(value * 100).toFixed(1)}%`

/** Data-quality and model limitations worth reading before acting on any score. */
export function attentionItems(summary: AnalyticsSummary | null, model: ModelStatus | null, latest: PredictionResult | null): AttentionItem[] {
  const items: AttentionItem[] = []
  const dataLink = { to: '/dashboard/marketplace-data', label: 'Open Marketplace Data' }
  const trainLink = { to: '/dashboard/train', label: 'Open Train Model' }

  if (summary) {
    const bySource = summary.records_by_source_type
    const live = bySource.live ?? 0
    if (summary.stored_records === 0) {
      items.push({ id: 'no-records', tone: 'warn', title: 'No stored observations', detail: 'Collect, import or load the demo fixture before building a dataset.', link: dataLink })
    } else if (live === 0) {
      items.push({
        id: 'no-live',
        tone: 'warn',
        title: 'No LIVE observations stored',
        detail: `Stored data: ${bySource.demo ?? 0} DEMO, ${bySource.imported ?? 0} IMPORTED. DEMO rows are synthetic and never current market data.`,
        link: dataLink,
      })
    }

    if (summary.available_live_platforms.length === 0) {
      const states = summary.refresh_sources.map((source) => `${title(source.platform)}: ${collectorStateLabel(source.state)}`).join(' · ')
      items.push({ id: 'collectors-gated', tone: 'idle', title: 'LIVE collection is gated', detail: states || 'No LIVE collector is configured and approved.', link: dataLink })
    }

    if (!summary.latest_dataset) {
      items.push({ id: 'no-dataset', tone: 'idle', title: 'No prepared dataset', detail: 'Predictions need a dataset built from stored observations.', link: trainLink })
    } else if (!summary.latest_dataset.file_available) {
      items.push({ id: 'dataset-missing', tone: 'warn', title: 'Latest dataset file unavailable', detail: `${summary.latest_dataset.dataset_id} is recorded but its file could not be found.`, link: trainLink })
    }
  }

  if (model) {
    const status = model.quality?.quality_status
    if (!model.trained) {
      items.push({ id: 'no-model', tone: 'warn', title: 'No active trained model', detail: 'Predictions stay unavailable until a model is trained.', link: trainLink })
    } else if (status === 'below_baseline') {
      items.push({ id: 'below-baseline', tone: 'down', title: 'Active model is below baseline', detail: `${BELOW_BASELINE_MESSAGE} Weighted F1 ${percent(model.primary_metric_value)}; majority baseline accuracy ${percent(model.majority_baseline)}.`, link: trainLink })
    } else if (status && status !== 'validated') {
      items.push({ id: 'model-quality', tone: 'warn', title: `Model quality: ${qualityPresentation[status].label}`, detail: 'Scores are experimental and not validated on real data.', link: trainLink })
    }
    if (model.trained && model.notice) {
      items.push({ id: 'model-notice', tone: 'warn', title: 'Model training data notice', detail: model.notice, link: trainLink })
    }
  }

  if (latest) {
    const stale = latest.platform_results.filter((platform) => platform.stale).map((platform) => title(platform.platform))
    if (stale.length) items.push({ id: 'stale', tone: 'warn', title: 'Stale observations in the latest prediction', detail: `${stale.join(', ')} used older observations. Compare observation dates before relying on the ranking.` })
    const missing = latest.platform_results.filter((platform) => platform.opportunity_score == null).map((platform) => title(platform.platform))
    if (missing.length) items.push({ id: 'unscored', tone: 'idle', title: 'Platforms without a score', detail: `${missing.join(', ')} had insufficient data in the latest prediction.` })
  }

  return items
}

export type ChartMetric = 'price' | 'discount' | 'rating'

export interface ChartSeries {
  key: string
  platform: string
  label: string
  sourceType: TrendSeries['source_type']
  currency: string
  points: { timestamp: string; value: number | null }[]
}

/**
 * One chart line per stored listing history. Prices are only comparable within
 * a currency, so price series are restricted to `currency`.
 */
export function chartSeries(series: TrendSeries[], metric: ChartMetric, currency: string | null): ChartSeries[] {
  return series
    .filter((item) => metric !== 'price' || currency === null || item.currency === currency)
    .map((item) => ({
      key: `${item.platform}|${item.source_type}|${item.currency}|${item.listing_key}`,
      platform: item.platform,
      label: `${title(item.platform)} · ${item.source_type.toUpperCase()}${metric === 'price' ? ` · ${item.currency}` : ''}`,
      sourceType: item.source_type,
      currency: item.currency,
      points: item.points.map((point: TrendPoint) => ({ timestamp: point.timestamp, value: point[metric] })),
    }))
    .filter((item) => item.points.some((point) => point.value !== null))
    .map((item, _index, all) => {
      // Several listings can share platform, source and currency; number them so labels stay unique.
      const same = all.filter((other) => other.label === item.label)
      return same.length > 1 ? { ...item, label: `${item.label} · listing ${same.indexOf(item) + 1}` } : item
    })
}

/** Distinct currencies across listing histories, in first-seen order. */
export function seriesCurrencies(series: TrendSeries[]): string[] {
  return [...new Set(series.map((item) => item.currency))]
}
