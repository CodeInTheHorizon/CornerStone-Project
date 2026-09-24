/** Marketplace name with its series colour swatch. The name, not the colour, identifies it. */

import { platformColour } from '@/lib/platforms'
import { title } from '@/lib/predictionFormat'

export function PlatformBadge({ platform, className }: { platform: string; className?: string }) {
  return (
    <span className={`inline-flex min-w-0 items-center gap-2 font-medium ${className ?? ''}`}>
      <span aria-hidden="true" className="size-2.5 shrink-0 rounded-[3px]" style={{ backgroundColor: platformColour(platform) }} />
      <span className="truncate">{title(platform)}</span>
    </span>
  )
}
