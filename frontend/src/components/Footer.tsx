/** Site footer. */

import { Link } from 'react-router-dom'

import { Icon } from '@/components/Icon'
import { Logo } from '@/components/Logo'
import { developer, navLinks } from '@/config/site'

export function Footer() {
  const socials = developer.socials.filter((social) => social.href)
  const year = new Date().getFullYear()

  return (
    <footer className="border-t border-border-hair bg-background">
      <div className="mx-auto max-w-shell px-6 py-14">
        <div className="flex flex-col gap-10 lg:flex-row lg:justify-between">
          <div className="max-w-sm">
            <Logo />
            <p className="mt-4 text-sm leading-relaxed text-muted">
              Marketplace intelligence for electronics sellers. Built on fresh
              marketplace observations, not borrowed datasets.
            </p>
          </div>

          <div className="flex gap-16">
            <nav aria-label="Footer">
              <h2 className="text-xs font-semibold tracking-[0.16em] text-subtle uppercase">
                Explore
              </h2>
              <ul className="mt-4 space-y-2.5">
                {navLinks.map((link) => (
                  <li key={link.href}>
                    <a
                      href={link.href}
                      className="text-sm text-muted transition-colors hover:text-foreground"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </nav>

            <div>
              <h2 className="text-xs font-semibold tracking-[0.16em] text-subtle uppercase">
                Account
              </h2>
              <ul className="mt-4 space-y-2.5">
                <li>
                  <Link
                    to="/login"
                    className="text-sm text-muted transition-colors hover:text-foreground"
                  >
                    Login
                  </Link>
                </li>
                <li>
                  <Link
                    to="/register"
                    className="text-sm text-muted transition-colors hover:text-foreground"
                  >
                    Register
                  </Link>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-12 flex flex-col gap-4 border-t border-border-hair pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-subtle">
            © {year} MarketPulse AI. Built by {developer.name}.
          </p>

          {socials.length > 0 && (
            <ul className="flex gap-1">
              {socials.map((social) => {
                const external = social.href.startsWith('http')
                return (
                  <li key={social.label}>
                    <a
                      href={social.href}
                      target={external ? '_blank' : undefined}
                      rel={external ? 'noreferrer noopener' : undefined}
                      aria-label={social.label}
                      className="grid size-9 place-items-center rounded-card text-subtle transition-colors hover:bg-accent-soft hover:text-accent-text"
                    >
                      <Icon name={social.icon} className="size-[18px]" />
                    </a>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </footer>
  )
}
