/**
 * Sticky header: logo left, section links centred, auth actions right.
 *
 * Gains a border and blurred background once the page scrolls, so it sits
 * flat over the hero and separates cleanly from content below it.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/Button'
import { Icon } from '@/components/Icon'
import { Logo } from '@/components/Logo'
import { ThemeToggle } from '@/components/ThemeToggle'
import { navLinks } from '@/config/site'
import { cn } from '@/lib/cn'

export function Navbar() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Close the mobile sheet on Escape.
  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMenuOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menuOpen])

  return (
    <header
      className={cn(
        'fixed inset-x-0 top-0 z-50 transition-colors duration-300',
        scrolled || menuOpen
          ? 'border-b border-border-hair bg-background/85 backdrop-blur-md'
          : 'border-b border-transparent',
      )}
    >
      <nav
        aria-label="Main"
        className="mx-auto flex h-16 max-w-shell items-center justify-between gap-4 px-6"
      >
        <a href="#home" className="shrink-0" aria-label="MarketPulse AI, home">
          <Logo />
        </a>

        {/* Centre links — desktop only. */}
        <ul className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-1 lg:flex">
          {navLinks.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                className="rounded-card px-3.5 py-2 text-sm text-muted transition-colors hover:text-foreground"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>

        <div className="flex items-center gap-2">
          <ThemeToggle />

          <Link
            to="/login"
            className="hidden rounded-card px-3.5 py-2 text-sm text-muted transition-colors hover:text-foreground sm:inline-flex"
          >
            Login
          </Link>
          <Link
            to="/register"
            className="hidden rounded-card border border-border-strong px-3.5 py-2 text-sm font-medium transition-colors hover:border-accent hover:text-accent-text sm:inline-flex"
          >
            Register
          </Link>
          {/* The wrapper carries the responsive display class: putting it on
              Button would collide with the `inline-flex` in its base styles,
              and which one wins depends on stylesheet order, not class order. */}
          <span className="hidden md:block">
            <Button as="a" href="#contact" size="sm">
              Contact
            </Button>
          </span>

          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            aria-controls="mobile-menu"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            className="grid size-9 place-items-center rounded-card border border-border-hair text-muted lg:hidden"
          >
            <Icon name={menuOpen ? 'close' : 'menu'} className="size-[18px]" />
          </button>
        </div>
      </nav>

      {/* Mobile sheet. */}
      <div
        id="mobile-menu"
        hidden={!menuOpen}
        className="border-t border-border-hair bg-background px-6 py-4 lg:hidden"
      >
        <ul className="flex flex-col gap-1">
          {navLinks.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                onClick={() => setMenuOpen(false)}
                className="block rounded-card px-3 py-2.5 text-sm text-muted transition-colors hover:bg-accent-soft hover:text-accent-text"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex gap-2 border-t border-border-hair pt-4">
          <Link
            to="/login"
            className="flex-1 rounded-card border border-border-strong px-3 py-2.5 text-center text-sm"
          >
            Login
          </Link>
          <Link
            to="/register"
            className="flex-1 rounded-card bg-accent px-3 py-2.5 text-center text-sm font-medium text-accent-ink"
          >
            Register
          </Link>
        </div>
      </div>
    </header>
  )
}
