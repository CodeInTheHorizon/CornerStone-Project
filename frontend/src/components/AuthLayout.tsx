/**
 * Shared shell for Login and Register.
 *
 * Reuses the landing page's visual system: same grid backdrop and accent glow
 * as the hero, same panel treatment, same tokens.
 */

import { Link } from 'react-router-dom'

import { Icon } from '@/components/Icon'
import { Logo } from '@/components/Logo'
import { ThemeToggle } from '@/components/ThemeToggle'

interface AuthLayoutProps {
  title: string
  subtitle: string
  children: React.ReactNode
  footer: React.ReactNode
}

export function AuthLayout({
  title,
  subtitle,
  children,
  footer,
}: AuthLayoutProps) {
  return (
    <div className="page-canvas relative min-h-screen overflow-hidden">
      <div
        aria-hidden="true"
        className="bg-grid pointer-events-none absolute inset-0
                   [mask-image:radial-gradient(ellipse_60%_45%_at_50%_0%,black,transparent)]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 left-1/2 size-[520px] -translate-x-1/2
                   rounded-full bg-accent-secondary/25 blur-[120px]"
      />

      <header className="relative mx-auto flex h-16 max-w-shell items-center justify-between px-6">
        <Link to="/" aria-label="MarketPulse AI, home">
          <Logo />
        </Link>
        <ThemeToggle />
      </header>

      <main className="relative mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center px-6 py-12">
        <div className="surface-card p-6 shadow-pop sm:p-9">
          <div className="text-center">
            <span aria-hidden="true" className="mx-auto grid size-12 place-items-center rounded-full bg-linear-to-br from-brand to-brand-deep text-white shadow-accent">
              <Icon name="check" className="size-6" />
            </span>
            <h1 className="mt-4 text-2xl font-semibold sm:text-3xl">{title}</h1>
            <p className="mt-2 text-sm leading-relaxed text-muted">{subtitle}</p>
          </div>

          <div className="mt-7">{children}</div>
        </div>

        <p className="mt-6 text-center text-sm text-muted">{footer}</p>
      </main>
    </div>
  )
}
