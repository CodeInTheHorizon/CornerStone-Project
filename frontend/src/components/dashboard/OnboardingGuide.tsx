import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Database, Layers, Brain, Compass, X, ChevronRight } from 'lucide-react'

const steps = [
  { icon: Database, label: 'Load demo data', description: 'Import sample marketplace observations to explore the platform.', to: '/dashboard/marketplace-data', cta: 'Go to Marketplace Data' },
  { icon: Layers, label: 'Build dataset', description: 'Transform raw observations into ML-ready features for training.', to: '/dashboard/train', cta: 'Open Training' },
  { icon: Brain, label: 'Train model', description: 'Train RandomForest + XGBoost models and inspect quality metrics.', to: '/dashboard/train', cta: 'Train Model' },
  { icon: Compass, label: 'Run prediction', description: 'Pick a product and get opportunity scores across marketplaces.', to: '/dashboard/predictor', cta: 'Make Prediction' },
] as const

const DISMISSED_KEY = 'marketpulse-onboarding-dismissed'

function isDismissed(): boolean {
  try { return localStorage.getItem(DISMISSED_KEY) === '1' } catch { return false }
}

export function OnboardingGuide({ completedSteps = 0 }: { completedSteps?: number }) {
  const [dismissed, setDismissed] = useState(isDismissed)

  if (dismissed) return null

  function dismiss() {
    try { localStorage.setItem(DISMISSED_KEY, '1') } catch { /* noop */ }
    setDismissed(true)
  }

  return (
    <AnimatePresence>
      {!dismissed && (
        <motion.div
          className="surface-card overflow-hidden"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.3 }}
        >
          <div className="flex items-center justify-between border-b border-border-hair px-5 py-4 sm:px-7">
            <div>
              <h2 className="text-base font-semibold">Get started with MarketPulse AI</h2>
              <p className="mt-1 text-sm text-muted">Follow these steps to set up your first prediction.</p>
            </div>
            <button onClick={dismiss} className="grid size-8 place-items-center rounded-full text-muted transition-colors hover:bg-background-alt hover:text-foreground" aria-label="Dismiss guide">
              <X className="size-4" />
            </button>
          </div>

          <div className="grid gap-3 p-5 sm:grid-cols-2 sm:p-7 lg:grid-cols-4">
            {steps.map((step, i) => {
              const done = i < completedSteps
              return (
                <motion.div
                  key={step.label}
                  className={`relative rounded-xl border p-4 transition-colors ${done ? 'border-signal-ok/30 bg-signal-ok/5' : 'border-border-hair bg-background-alt/40'}`}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.08 }}
                >
                  <div className="flex items-center gap-3">
                    <span className={`grid size-9 place-items-center rounded-lg ${done ? 'bg-signal-ok/15 text-signal-ok' : 'bg-accent-soft text-accent-text'}`}>
                      <step.icon className="size-4" />
                    </span>
                    <span className="text-[11px] font-medium text-subtle">Step {i + 1}</span>
                  </div>
                  <h3 className="mt-3 text-sm font-semibold">{step.label}</h3>
                  <p className="mt-1 text-xs leading-relaxed text-muted">{step.description}</p>
                  {!done && (
                    <Link to={step.to} className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-accent-text transition-colors hover:text-accent-hover">
                      {step.cta}
                      <ChevronRight className="size-3" />
                    </Link>
                  )}
                  {done && <p className="mt-3 text-xs font-medium text-signal-ok">Complete</p>}
                </motion.div>
              )
            })}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
