import { motion } from 'framer-motion'
import { Database, Layers, Brain, Compass } from 'lucide-react'

import { Reveal } from '@/components/Reveal'

const steps = [
  { icon: Database, label: 'Collect Data', description: 'Gather marketplace observations from Amazon, Flipkart, Croma and Alibaba.' },
  { icon: Layers, label: 'Build Dataset', description: 'Clean, normalize and engineer 31 ML features from raw snapshots.' },
  { icon: Brain, label: 'Train Model', description: 'RandomForest + XGBoost with temporal splits and quality gates.' },
  { icon: Compass, label: 'Get Predictions', description: 'Opportunity scores, price forecasts and actionable recommendations.' },
] as const

export function HowItWorks() {
  return (
    <section className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-shell px-6">
        <Reveal>
          <div className="text-center">
            <p className="text-xs font-semibold tracking-[0.18em] text-accent-text uppercase">How it works</p>
            <h2 className="mt-3 text-3xl font-semibold sm:text-4xl">From raw data to decisions</h2>
            <p className="mx-auto mt-4 max-w-xl text-base text-muted">
              Four steps turn scattered marketplace signals into ML-powered insights you can act on.
            </p>
          </div>
        </Reveal>

        <div className="relative mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div
            aria-hidden="true"
            className="absolute top-12 right-12 left-12 hidden h-px bg-linear-to-r from-transparent via-accent/30 to-transparent lg:block"
          />

          {steps.map((step, i) => (
            <Reveal key={step.label} delay={i * 100}>
              <motion.div
                className="relative flex flex-col items-center text-center"
                whileHover={{ y: -4 }}
                transition={{ duration: 0.2 }}
              >
                <div className="relative">
                  <div className="absolute inset-0 rounded-full bg-accent/10 blur-lg" />
                  <span className="relative grid size-16 place-items-center rounded-2xl bg-linear-to-br from-accent-soft to-accent/5 text-accent-text shadow-card">
                    <step.icon className="size-7" />
                  </span>
                  <span className="absolute -top-2 -right-2 grid size-6 place-items-center rounded-full bg-accent text-[11px] font-bold text-accent-ink shadow-accent">
                    {i + 1}
                  </span>
                </div>

                <h3 className="mt-5 text-base font-semibold">{step.label}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{step.description}</p>
              </motion.div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}
