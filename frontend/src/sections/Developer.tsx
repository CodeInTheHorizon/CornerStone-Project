/** Section 3 — Meet the Developer. */

import { Icon } from '@/components/Icon'
import { Reveal } from '@/components/Reveal'
import { Section } from '@/components/Section'
import { developer } from '@/config/site'

/** Initials stand in until a real photo is added to public/. */
function Avatar({ name }: { name: string }) {
  const initials = name
    .split(' ')
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <div
      className="grid size-28 shrink-0 place-items-center rounded-panel border border-border-hair
                 bg-accent-soft text-3xl font-semibold text-accent-text sm:size-32"
      aria-hidden="true"
    >
      {initials}
    </div>
  )
}

export function Developer() {
  // An unset social link is hidden rather than rendered as a dead icon.
  const socials = developer.socials.filter((social) => social.href)

  return (
    <Section id="developer" eyebrow="Team" heading="Meet the Developer">
      <Reveal>
        <div className="rounded-panel border border-border-hair bg-surface p-8 sm:p-10">
          <div className="flex flex-col gap-8 sm:flex-row sm:items-start">
            <Avatar name={developer.name} />

            <div className="min-w-0">
              <h3 className="text-2xl font-semibold">{developer.name}</h3>
              <p className="mt-1 text-sm font-medium text-accent-text">
                {developer.role}
              </p>

              <p className="mt-5 max-w-2xl leading-relaxed text-muted">
                {developer.intro}
              </p>

              <ul className="mt-6 flex flex-wrap gap-2">
                {developer.focus.map((skill) => (
                  <li
                    key={skill}
                    className="rounded-full border border-border-hair bg-background-alt px-3 py-1 text-xs text-muted"
                  >
                    {skill}
                  </li>
                ))}
              </ul>

              {socials.length > 0 && (
                <ul className="mt-8 flex flex-wrap gap-2">
                  {socials.map((social) => {
                    const external = social.href.startsWith('http')
                    return (
                      <li key={social.label}>
                        <a
                          href={social.href}
                          target={external ? '_blank' : undefined}
                          rel={external ? 'noreferrer noopener' : undefined}
                          className="inline-flex items-center gap-2 rounded-card border border-border-hair
                                     px-3.5 py-2 text-sm text-muted transition-colors
                                     hover:border-accent hover:text-accent-text"
                        >
                          <Icon name={social.icon} className="size-4" />
                          {social.label}
                        </a>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </div>
        </div>
      </Reveal>
    </Section>
  )
}
