/** Dashboard navigation, per PROJECT_CONTEXT.md section 9. */

import type { IconName } from '@/components/Icon'

export type DashboardNavGroup = 'insights' | 'data'

export interface DashboardNavItem {
  label: string
  to: string
  icon: IconName
  /** Which phase delivers this screen; drives the "not built yet" badge. */
  available: boolean
  group: DashboardNavGroup
  /** Short contextual subtitle shown under the page title in the top bar. */
  description: string
}

export const dashboardNavGroups: { id: DashboardNavGroup; label: string }[] = [
  { id: 'insights', label: 'Decision support' },
  { id: 'data', label: 'Data & models' },
]

export const dashboardNav: DashboardNavItem[] = [
  {
    label: 'Overview',
    to: '/dashboard',
    icon: 'dashboard',
    available: true,
    group: 'insights',
    description: 'Stored marketplace signals, saved predictions and data limitations.',
  },
  {
    label: 'Search',
    to: '/dashboard/search',
    icon: 'search',
    available: true,
    group: 'insights',
    description: 'Search products across Amazon, Flipkart, Croma and Alibaba.',
  },
  {
    label: 'Products',
    to: '/dashboard/products',
    icon: 'package',
    available: true,
    group: 'insights',
    description: 'Browse and compare products discovered across all platforms.',
  },
  {
    label: 'ML Predictor',
    to: '/dashboard/predictor',
    icon: 'compass',
    available: true,
    group: 'insights',
    description: 'Compare heuristic opportunity scores for one stored product.',
  },
  {
    label: 'Compare',
    to: '/dashboard/compare',
    icon: 'chart',
    available: true,
    group: 'insights',
    description: 'Side-by-side comparison of 2-4 products across marketplaces.',
  },
  {
    label: 'Trend Analysis',
    to: '/dashboard/trends',
    icon: 'trend',
    available: true,
    group: 'insights',
    description: 'Price, discount, rating and review histories per listing.',
  },
  {
    label: 'Analytics',
    to: '/dashboard/analytics',
    icon: 'chart',
    available: true,
    group: 'insights',
    description: 'Cross-platform comparison of stored observations.',
  },
  {
    label: 'Marketplace Data',
    to: '/dashboard/marketplace-data',
    icon: 'database',
    available: true,
    group: 'data',
    description: 'Collector status, imports, the demo fixture and stored records.',
  },
  {
    label: 'Train Model',
    to: '/dashboard/train',
    icon: 'layers',
    available: true,
    group: 'data',
    description: 'Build datasets, train models and inspect measured quality.',
  },
  {
    label: 'Price Alerts',
    to: '/dashboard/alerts',
    icon: 'pulse',
    available: true,
    group: 'data',
    description: 'Set up price threshold alerts across marketplaces.',
  },
]

/** Marketplaces the system targets. Configured, not yet collected from. */
export const supportedPlatforms = [
  'Amazon',
  'Flipkart',
  'Croma',
  'Alibaba',
] as const
