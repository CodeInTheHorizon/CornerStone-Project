/**
 * Section 5 — Get in Touch.
 *
 * Validates locally, then hands the formatted enquiry to WhatsApp. Nothing is
 * sent to the backend: there is no contact endpoint, and pretending otherwise
 * would claim a delivery path that does not exist.
 */

import { useState } from 'react'

import { Button } from '@/components/Button'
import { Field } from '@/components/Field'
import { Icon } from '@/components/Icon'
import { Reveal } from '@/components/Reveal'
import { Section } from '@/components/Section'
import { env } from '@/config/env'
import { contact } from '@/config/site'
import {
  buildWhatsappUrl,
  emptyContactForm,
  validateContactForm,
  type ContactFormErrors,
  type ContactFormValues,
} from '@/lib/contactForm'

export function Contact() {
  const [values, setValues] = useState<ContactFormValues>(emptyContactForm)
  const [errors, setErrors] = useState<ContactFormErrors>({})
  const [sent, setSent] = useState(false)

  const update = (field: keyof ContactFormValues) => (value: string) => {
    setValues((current) => ({ ...current, [field]: value }))
    // Clear this field's error as soon as the user starts correcting it.
    setErrors((current) =>
      current[field] ? { ...current, [field]: undefined } : current,
    )
    setSent(false)
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()

    const nextErrors = validateContactForm(values)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    const url = buildWhatsappUrl(values)
    if (!url) return

    window.open(url, '_blank', 'noopener,noreferrer')
    setSent(true)
  }

  return (
    <Section
      id="contact"
      eyebrow="Contact"
      heading={contact.heading}
      description={contact.description}
    >
      <Reveal className="mx-auto max-w-2xl">
        <form
          noValidate
          onSubmit={handleSubmit}
          className="surface-card p-6 sm:p-10"
        >
          <div className="grid gap-5 sm:grid-cols-2">
            <Field
              label="Name"
              name="name"
              autoComplete="name"
              placeholder="Your name"
              value={values.name}
              onChange={update('name')}
              error={errors.name}
            />
            <Field
              label="Email"
              name="email"
              type="email"
              autoComplete="email"
              placeholder="name@example.com"
              value={values.email}
              onChange={update('email')}
              error={errors.email}
            />
          </div>

          <div className="mt-5">
            <Field
              label="Phone / Contact"
              name="phone"
              type="tel"
              autoComplete="tel"
              placeholder="+91 98765 43210"
              value={values.phone}
              onChange={update('phone')}
              error={errors.phone}
            />
          </div>

          <div className="mt-5">
            <Field
              label="Message"
              name="message"
              multiline
              placeholder="What would you like to know?"
              value={values.message}
              onChange={update('message')}
              error={errors.message}
            />
          </div>

          {!env.isWhatsappConfigured && (
            <p
              role="status"
              className="mt-6 rounded-card border border-signal-warn/30 bg-signal-warn/10 px-4 py-3 text-sm text-signal-warn"
            >
              Messaging is not configured yet. Set VITE_WHATSAPP_NUMBER in your
              environment to enable it.
            </p>
          )}

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Button type="submit" size="lg" disabled={!env.isWhatsappConfigured}>
              <Icon name="whatsapp" className="size-4" />
              Send Message
            </Button>

            {sent && (
              <p role="status" className="text-sm text-signal-ok">
                WhatsApp opened in a new tab.
              </p>
            )}
          </div>

          <p className="mt-5 text-xs leading-relaxed text-subtle">
            Submitting opens WhatsApp with your message pre-filled. Nothing is
            stored on this site.
          </p>
        </form>
      </Reveal>
    </Section>
  )
}
