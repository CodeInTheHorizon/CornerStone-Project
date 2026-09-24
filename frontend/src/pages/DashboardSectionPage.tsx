/**
 * Placeholder for dashboard sections whose feature has not been built yet.
 *
 * Keeps the navigation honest: the route exists and is reachable, and the page
 * says plainly what is missing instead of faking a screen full of numbers.
 */

import { Link, useLocation } from 'react-router-dom'

import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import { Icon } from '@/components/Icon'
import { dashboardNav } from '@/config/dashboard'

const explanations: Record<string, string> = {
  '/dashboard/marketplace-data':
    'Collecting marketplace listings, normalising them into snapshots and storing them. Until a collector runs, there is nothing to show.',
  '/dashboard/predictor':
    'Choosing an electronics product and getting a ranked marketplace recommendation with a 0-100 opportunity score per platform.',
  '/dashboard/train':
    'Training a model on the collected dataset and recording its measured accuracy, dataset size and feature names.',
  '/dashboard/trends':
    'Price, discount and review-momentum trends built from repeated marketplace snapshots over time.',
  '/dashboard/analytics':
    'Cross-platform comparison and opportunity-score breakdowns drawn from stored snapshots.',
}

export function DashboardSectionPage() {
  const { pathname } = useLocation()
  const item = dashboardNav.find((entry) => entry.to === pathname)
  const label = item?.label ?? 'This section'

  return (
    <DashboardLayout title={label}>
      <div className="surface-card p-8 sm:p-10">
        <span
          className="grid size-11 place-items-center rounded-card bg-accent-soft text-accent-text"
          aria-hidden="true"
        >
          <Icon name={item?.icon ?? 'dashboard'} className="size-[22px]" />
        </span>

        <h2 className="mt-6 text-2xl font-semibold">{label}</h2>
        <p className="mt-3 max-w-2xl leading-relaxed text-muted">
          {explanations[pathname] ??
            'This section is part of a later phase of the build.'}
        </p>

        <p className="mt-6 text-sm text-subtle">
          Not built yet — this screen is a placeholder so the navigation stays
          complete.
        </p>

        <Link
          to="/dashboard"
          className="mt-7 inline-flex items-center gap-2 rounded-card border border-border-strong px-5 py-2.5 text-sm font-medium transition-colors hover:border-accent hover:text-accent-text"
        >
          <Icon name="arrow-right" className="size-4 rotate-180" />
          Back to dashboard
        </Link>
      </div>
    </DashboardLayout>
  )
}
