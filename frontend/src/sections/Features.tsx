/** Section 4 — feature grid. */

import { FeatureCard } from '@/components/FeatureCard'
import { Reveal } from '@/components/Reveal'
import { Section } from '@/components/Section'
import { features } from '@/config/site'

export function Features() {
  return (
    <Section
      id="features"
      eyebrow="Features"
      heading="Features"
      description="Everything MarketPulse AI does sits on top of data it collected itself — no borrowed dataset, no invented numbers."
      tone="alt"
    >
      <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {features.map((feature, index) => (
          <Reveal as="li" key={feature.title} delay={(index % 3) * 90}>
            <FeatureCard {...feature} />
          </Reveal>
        ))}
      </ul>
    </Section>
  )
}
