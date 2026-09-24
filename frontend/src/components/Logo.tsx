/** Wordmark with a small pulse glyph. */

import { cn } from '@/lib/cn'

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <span
        className="grid size-8 place-items-center rounded-[10px] bg-linear-to-br from-brand to-brand-deep text-white shadow-accent"
        aria-hidden="true"
      >
        <svg viewBox="0 0 24 24" fill="none" className="size-5">
          <path
            d="M3 14h3.2l2.2-6.5 3.4 10 2.6-7 1.8 3.5H21"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <span className="text-[15px] font-semibold tracking-tight">
        MarketPulse<span className="text-accent-text"> AI</span>
      </span>
    </span>
  )
}
