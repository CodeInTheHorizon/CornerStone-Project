import { useEffect, useRef, useState } from 'react'
import { motion, useInView } from 'framer-motion'

import { Reveal } from '@/components/Reveal'

const stats = [
  { value: 4, label: 'Marketplaces', suffix: '' },
  { value: 31, label: 'ML Features', suffix: '' },
  { value: 100, label: 'Point Scoring', suffix: '-pt' },
  { value: 24, label: 'Hour Refresh', suffix: 'h' },
] as const

function AnimatedCounter({ value, suffix }: { value: number; suffix: string }) {
  const [display, setDisplay] = useState(0)
  const ref = useRef<HTMLSpanElement>(null)
  const isInView = useInView(ref, { once: true, margin: '-60px' })
  const raf = useRef<number | null>(null)

  useEffect(() => {
    if (!isInView) return
    const start = performance.now()
    const duration = 1200
    function tick(now: number) {
      const progress = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplay(Math.round(value * eased))
      if (progress < 1) raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => { if (raf.current) cancelAnimationFrame(raf.current) }
  }, [isInView, value])

  return <span ref={ref}>{display}{suffix}</span>
}

export function Stats() {
  return (
    <section className="relative py-16 sm:py-24">
      <div className="mx-auto max-w-shell px-6">
        <Reveal>
          <div className="surface-card mx-auto overflow-hidden p-8 sm:p-12">
            <div className="absolute inset-0 dot-grid opacity-40" aria-hidden="true" />
            <div className="relative grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {stats.map((stat, i) => (
                <motion.div
                  key={stat.label}
                  className="flex flex-col items-center text-center"
                  initial={{ opacity: 0, y: 12 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: '-40px' }}
                  transition={{ duration: 0.4, delay: i * 0.1 }}
                >
                  <span className="text-4xl font-bold tracking-tight text-accent-text sm:text-5xl">
                    <AnimatedCounter value={stat.value} suffix={stat.suffix} />
                  </span>
                  <span className="mt-2 text-sm font-medium text-muted">{stat.label}</span>
                </motion.div>
              ))}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
