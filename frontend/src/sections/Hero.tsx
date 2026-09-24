import { motion } from 'framer-motion'
import { TrendingUp, BarChart3, Target, Zap } from 'lucide-react'

import { Button } from '@/components/Button'
import { Icon } from '@/components/Icon'
import { Reveal } from '@/components/Reveal'
import { hero } from '@/config/site'

const floatingBadges = [
  { label: '+12% accuracy', icon: Target, x: -20, y: 40, delay: 0.6 },
  { label: '4 platforms', icon: BarChart3, x: 85, y: 70, delay: 0.8 },
  { label: 'Real-time', icon: Zap, x: 75, y: 10, delay: 1.0 },
] as const

function HeroIllustration() {
  return (
    <div aria-hidden="true" className="relative mx-auto h-[420px] w-full max-w-[480px]">
      <motion.div
        className="absolute inset-4 rounded-[40px] bg-linear-to-br from-accent/25 to-accent-secondary/15 blur-3xl"
        animate={{ scale: [1, 1.05, 1], opacity: [0.6, 0.8, 0.6] }}
        transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
      />

      <motion.div
        className="surface-card absolute top-4 right-0 left-8 overflow-hidden p-6 shadow-pop"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.2, ease: [0.2, 0, 0, 1] }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="size-2.5 rounded-full bg-signal-ok" />
            <span className="text-xs font-medium text-muted">Market Overview</span>
          </div>
          <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[10px] font-semibold text-accent-text">
            Live
          </span>
        </div>

        <div className="mt-5 flex h-28 items-end gap-2.5">
          {[42, 64, 50, 82, 58, 96, 74, 88].map((height, index) => (
            <motion.span
              key={index}
              className={`flex-1 rounded-t-lg ${index === 5 ? 'bg-accent shadow-glow' : 'bg-accent-secondary/35'}`}
              initial={{ height: 0 }}
              animate={{ height: `${height}%` }}
              transition={{ duration: 0.5, delay: 0.4 + index * 0.06, ease: [0.2, 0, 0, 1] }}
            />
          ))}
        </div>

        <svg viewBox="0 0 340 50" className="mt-4 h-10 w-full" fill="none">
          <defs>
            <linearGradient id="hero-line-grad" x1="0" y1="0" x2="340" y2="0" gradientUnits="userSpaceOnUse">
              <stop stopColor="var(--accent-secondary)" />
              <stop offset="1" stopColor="var(--accent)" />
            </linearGradient>
          </defs>
          <motion.path
            d="M0 40 L40 32 L80 36 L120 18 L160 24 L200 10 L240 16 L280 8 L340 4"
            stroke="url(#hero-line-grad)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 1.2, delay: 0.8, ease: 'easeOut' }}
          />
        </svg>
      </motion.div>

      <motion.div
        className="glass-card absolute bottom-10 left-0 flex items-center gap-3 px-4 py-3 shadow-pop"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, delay: 0.9 }}
      >
        <span className="grid size-10 place-items-center rounded-xl bg-linear-to-br from-signal-ok/20 to-signal-ok/5 text-signal-ok">
          <TrendingUp className="size-5" />
        </span>
        <span>
          <span className="block text-sm font-semibold">Score: 87/100</span>
          <span className="block text-[11px] text-muted">Opportunity detected</span>
        </span>
      </motion.div>

      {floatingBadges.map((badge) => (
        <motion.div
          key={badge.label}
          className="glass-card absolute flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium shadow-card"
          style={{ left: `${badge.x}%`, top: `${badge.y}%` }}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1, y: [0, -6, 0] }}
          transition={{
            opacity: { duration: 0.4, delay: badge.delay },
            scale: { duration: 0.4, delay: badge.delay },
            y: { duration: 3, repeat: Infinity, ease: 'easeInOut', delay: badge.delay },
          }}
        >
          <badge.icon className="size-3.5 text-accent-text" />
          {badge.label}
        </motion.div>
      ))}
    </div>
  )
}

export function Hero() {
  return (
    <section
      id="home"
      aria-labelledby="hero-heading"
      className="relative overflow-hidden pt-32 pb-20 sm:pt-40 sm:pb-28"
    >
      <div
        aria-hidden="true"
        className="bg-grid pointer-events-none absolute inset-0
                   [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,black,transparent)]"
      />
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute -top-32 left-1/2 size-[600px] -translate-x-1/2 rounded-full bg-accent/15 blur-[100px]"
        animate={{ scale: [1, 1.15, 1], opacity: [0.5, 0.8, 0.5] }}
        transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute top-20 -right-40 size-[400px] rounded-full bg-accent-secondary/10 blur-[80px]"
        animate={{ scale: [1, 1.1, 1] }}
        transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
      />

      <div className="relative mx-auto grid max-w-shell items-center gap-12 px-6 text-center lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:text-left">
        <div className="min-w-0">
          <Reveal>
            <span
              className="inline-flex items-center gap-2 rounded-full border border-border-hair
                         bg-surface/80 px-3.5 py-1.5 text-xs font-medium text-muted shadow-card backdrop-blur-sm"
            >
              <Icon name="spark" className="size-3.5 text-accent-text" />
              {hero.eyebrow}
            </span>
          </Reveal>

          <Reveal delay={80}>
            <h1
              id="hero-heading"
              className="mx-auto mt-7 max-w-4xl text-5xl font-semibold sm:text-6xl lg:mx-0 lg:text-[64px] lg:leading-[1.05]"
            >
              {hero.title}
            </h1>
          </Reveal>

          <Reveal delay={140}>
            <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-muted sm:text-lg lg:mx-0">
              {hero.description}
            </p>
          </Reveal>

          <Reveal delay={200}>
            <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row lg:justify-start">
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
            <div className="mt-14">
              <p className="text-xs font-medium tracking-[0.18em] text-subtle uppercase">
                Marketplaces covered
              </p>
              <ul className="mt-4 flex flex-wrap items-center justify-center gap-x-8 gap-y-3 lg:justify-start">
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

        <Reveal delay={180} className="hidden lg:block">
          <HeroIllustration />
        </Reveal>
      </div>
    </section>
  )
}
