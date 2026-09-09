/** Feature grid tile: icon, title, one-line description. */

import { Icon, type IconName } from '@/components/Icon'

interface FeatureCardProps {
  icon: IconName
  title: string
  description: string
}

export function FeatureCard({ icon, title, description }: FeatureCardProps) {
  return (
    <article
      className="group h-full rounded-panel border border-border-hair bg-surface p-7
                 transition-[border-color,transform] duration-300
                 hover:-translate-y-1 hover:border-accent/60"
    >
      <span
        className="grid size-11 place-items-center rounded-card bg-accent-soft text-accent-text
                   transition-colors duration-300 group-hover:bg-accent group-hover:text-accent-ink"
        aria-hidden="true"
      >
        <Icon name={icon} className="size-[22px]" />
      </span>
      <h3 className="mt-6 text-lg font-semibold">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted">{description}</p>
    </article>
  )
}
