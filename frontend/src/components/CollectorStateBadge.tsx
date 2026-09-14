/**
 * A collector's runtime state, as distinct from the provenance of stored rows.
 *
 * "LIVE ready" means a permitted LIVE fetch may be attempted; it does not mean
 * any LIVE data exists. Stored provenance keeps using SourceBadge.
 */

import { StatusPill } from '@/components/StatusPill'
import { collectorStatePresentation } from '@/lib/collectorState'
import type { CollectorState } from '@/types/data'

export function CollectorStateBadge({ state }: { state: CollectorState | undefined }) {
  const { tone, label } = state ? collectorStatePresentation[state] : { tone: 'idle' as const, label: 'Unknown' }
  return <StatusPill tone={tone}>{label}</StatusPill>
}
