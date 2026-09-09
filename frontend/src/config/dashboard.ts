/** Dashboard navigation, per PROJECT_CONTEXT.md section 9. */

import type { IconName } from '@/components/Icon'

export interface DashboardNavItem {
  label: string
  to: string
  icon: IconName
  /** Which phase delivers this screen; drives the "not built yet" badge. */
  available: boolean
}

export const dashboardNav: DashboardNavItem[] = [
  { label: 'Dashboard', to: '/dashboard', icon: 'dashboard', available: true },
  {
    label: 'Marketplace Data',
    to: '/dashboard/marketplace-data',
    icon: 'database',
    available: false,
  },
  {
    label: 'ML Predictor',
    to: '/dashboard/predictor',
    icon: 'compass',
    available: false,
  },
  {
    label: 'Train Model',
    to: '/dashboard/train',
    icon: 'layers',
    available: false,
  },
  {
    label: 'Trend Analysis',
    to: '/dashboard/trends',
    icon: 'trend',
    available: false,
  },
  {
    label: 'Analytics',
    to: '/dashboard/analytics',
    icon: 'chart',
    available: false,
  },
]

/** Marketplaces the system targets. Configured, not yet collected from. */
export const supportedPlatforms = [
  'Amazon',
  'Flipkart',
  'Croma',
  'Alibaba',
] as const
