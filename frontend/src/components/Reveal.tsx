/**
 * Reveals its children once as they scroll into view.
 *
 * Uses IntersectionObserver and unobserves after the first intersection, so
 * content never re-animates on the way back up. The CSS honours
 * prefers-reduced-motion, and content starts visible if the observer is
 * unavailable, so nothing can end up permanently hidden.
 */

import { useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/cn'

interface RevealProps {
  children: React.ReactNode
  className?: string
  /** Stagger, in ms, for items revealed as a group. */
  delay?: number
  as?: 'div' | 'section' | 'li' | 'article'
}

const supportsObserver = typeof IntersectionObserver !== 'undefined'

export function Reveal({
  children,
  className,
  delay = 0,
  as: Tag = 'div',
}: RevealProps) {
  const ref = useRef<HTMLElement>(null)
  // Without an observer there is nothing to trigger the reveal, so start shown.
  const [visible, setVisible] = useState(!supportsObserver)

  useEffect(() => {
    const node = ref.current
    if (!node || !supportsObserver) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          observer.unobserve(entry.target)
        }
      },
      { threshold: 0.12, rootMargin: '0px 0px -60px 0px' },
    )

    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  return (
    <Tag
      ref={ref as React.Ref<never>}
      className={cn('reveal', className)}
      data-visible={visible}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </Tag>
  )
}
