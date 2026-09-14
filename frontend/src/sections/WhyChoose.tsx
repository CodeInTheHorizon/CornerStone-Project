/** Section 2 — Why Choose MarketPulse AI? */

import { FlipCard } from '@/components/FlipCard'
import { Reveal } from '@/components/Reveal'
import { Section } from '@/components/Section'
import { whyCards } from '@/config/site'

export function WhyChoose() {
  return (
    <Section
      id="about"
      eyebrow="About"
      heading="Why Choose MarketPulse AI?"
      description="Built around one honest loop: gather marketplace observations with their provenance, turn them into a dataset, train on it, and show what the model actually found."
      tone="alt"
    >
      <ul className="grid gap-6 md:grid-cols-3">
        {whyCards.map((card, index) => (
          <Reveal as="li" key={card.title} delay={index * 90}>
            <FlipCard icon={card.icon} title={card.title} body={card.body} />
          </Reveal>
        ))}
      </ul>
    </Section>
  )
}
