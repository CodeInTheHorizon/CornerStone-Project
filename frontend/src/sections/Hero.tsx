/** Section 1 — hero. */

import { Button } from '@/components/Button'
import { Icon } from '@/components/Icon'
import { Reveal } from '@/components/Reveal'
import { hero } from '@/config/site'

export function Hero() {
  return (
    <section
      id="home"
      aria-labelledby="hero-heading"
      className="relative overflow-hidden pt-32 pb-20 sm:pt-40 sm:pb-28"
    >
      {/* Decorative backdrop: faint grid, faded out at the edges. */}
      <div
        aria-hidden="true"
        className="bg-grid pointer-events-none absolute inset-0
                   [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,black,transparent)]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-32 left-1/2 size-[560px] -translate-x-1/2
                   rounded-full bg-accent/10 blur-[120px]"
      />

      <div className="relative mx-auto max-w-shell px-6 text-center">
        <Reveal>
          <span
            className="inline-flex items-center gap-2 rounded-full border border-border-hair
                       bg-surface px-3.5 py-1.5 text-xs font-medium text-muted"
          >
            <Icon name="spark" className="size-3.5 text-accent-text" />
            {hero.eyebrow}
          </span>
        </Reveal>

        <Reveal delay={80}>
          <h1
            id="hero-heading"
            className="mx-auto mt-7 max-w-4xl text-5xl font-semibold sm:text-6xl lg:text-7xl"
          >
            {hero.title}
          </h1>
        </Reveal>

        <Reveal delay={140}>
          <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">
            {hero.description}
          </p>
        </Reveal>

        <Reveal delay={200}>
          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button as="a" href={hero.primaryCta.href} size="lg" className="w-full sm:w-auto">
              {hero.primaryCta.label}
              <Icon name="arrow-right" className="size-4" />
            </Button>
            <Button
              as="a"
              href={hero.secondaryCta.href}
              size="lg"
              variant="secondary"
              className="w-full sm:w-auto"
            >
              {hero.secondaryCta.label}
            </Button>
          </div>
        </Reveal>

        <Reveal delay={260}>
          <div className="mt-16">
            <p className="text-xs font-medium tracking-[0.18em] text-subtle uppercase">
              Marketplaces covered
            </p>
            <ul className="mt-5 flex flex-wrap items-center justify-center gap-x-10 gap-y-3">
              {hero.platforms.map((platform) => (
                <li
                  key={platform}
                  className="text-base font-medium text-subtle transition-colors hover:text-foreground"
                >
                  {platform}
                </li>
              ))}
            </ul>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
