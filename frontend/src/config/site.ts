/**
 * Landing page content.
 *
 * Copy lives here rather than inside components so it can be edited without
 * touching markup.
 *
 * ─────────────────────────────────────────────────────────────────────────
 *  BEFORE PUBLISHING, fill in `developer` below and set VITE_WHATSAPP_NUMBER
 *  in your .env. Social links with an empty `href` are hidden automatically
 *  rather than rendered as dead icons.
 * ─────────────────────────────────────────────────────────────────────────
 */

import type { IconName } from '@/components/Icon'

export interface NavLink {
  label: string
  href: string
}

export const navLinks: NavLink[] = [
  { label: 'Home', href: '#home' },
  { label: 'About', href: '#about' },
  { label: 'Features', href: '#features' },
  { label: 'Contact', href: '#contact' },
]

export const hero = {
  eyebrow: 'Marketplace intelligence for electronics sellers',
  title: 'MarketPulse AI',
  description:
    'Explore stored marketplace observations through trend charts and experimental opportunity scores. Current training data is synthetic DEMO data; live collection is unavailable.',
  primaryCta: { label: 'Explore Market Intelligence', href: '/dashboard' },
  secondaryCta: { label: 'View Features', href: '#features' },
  platforms: ['Amazon', 'Flipkart', 'Croma', 'Alibaba'],
} as const

/** Section 2 — hover/flip cards. */
export interface WhyCard {
  icon: IconName
  title: string
  body: string
}

export const whyCards: WhyCard[] = [
  {
    icon: 'brain',
    title: 'AI-Powered',
    body: 'Machine-learning models transform marketplace data into predictions and opportunity insights.',
  },
  {
    icon: 'pulse',
    title: 'Stored Trend Analytics',
    body: 'Compare price, discount and review histories with visible DEMO, IMPORTED and LIVE provenance.',
  },
  {
    icon: 'target',
    title: 'Precision & Accuracy',
    body: 'Model performance is measured and predictions include confidence/score information instead of unexplained outputs.',
  },
]

/** Section 4 — feature grid. */
export interface Feature {
  icon: IconName
  title: string
  description: string
}

export const features: Feature[] = [
  {
    icon: 'chart',
    title: 'Predictive Analytics',
    description:
      'Experimental models demonstrate the prediction pipeline; current DEMO performance is below baseline.',
  },
  {
    icon: 'trend',
    title: 'Trend Analysis',
    description:
      'Track how price, discount, rating and review activity move across repeated observations.',
  },
  {
    icon: 'refresh',
    title: 'Data Freshness',
    description:
      'Inspect observation timestamps and source labels. Live refresh remains unavailable until a supported collector is connected.',
  },
  {
    icon: 'dashboard',
    title: 'Interactive Dashboard',
    description:
      'Select a product, compare marketplaces and read results through charts built for decisions.',
  },
  {
    icon: 'layers',
    title: 'Custom Models',
    description:
      'Train on your collected dataset and review the measured accuracy of every training run.',
  },
  {
    icon: 'compass',
    title: 'Cross-Platform Opportunity Score',
    description:
      'A 0-100 score per marketplace, broken down into the signals that produced it.',
  },
]

/** Section 3 — developer profile. */
export interface SocialLink {
  label: string
  href: string
  icon: IconName
}

export const developer = {
  name: 'Kshitij',
  role: 'Full-Stack & Machine Learning Developer',
  // Keep this factual — it appears publicly.
  intro:
    'I build end-to-end data products: collecting real marketplace data, turning it into a usable dataset, training models on it, and presenting the result in an interface people can actually act on. MarketPulse AI is that full loop in one project.',
  focus: [
    'React & TypeScript',
    'FastAPI & Python',
    'Data pipelines',
    'scikit-learn / XGBoost',
    'PostgreSQL',
    'Data visualisation',
  ],
  /** Leave an href empty to hide that link rather than render a dead icon. */
  socials: [
    { label: 'GitHub', href: '', icon: 'github' },
    { label: 'LinkedIn', href: '', icon: 'linkedin' },
    { label: 'Email', href: 'mailto:kshitijji30@gmail.com', icon: 'mail' },
    { label: 'Portfolio', href: '', icon: 'globe' },
  ] satisfies SocialLink[],
} as const

export const contact = {
  heading: 'Get in Touch',
  description:
    'Questions about the project, the data pipeline or the models? Send a message and it opens directly in WhatsApp.',
} as const
