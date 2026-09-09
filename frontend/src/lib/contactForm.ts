/** Validation and WhatsApp message construction for the contact form. */

import { env } from '@/config/env'

export interface ContactFormValues {
  name: string
  email: string
  phone: string
  message: string
}

export type ContactFormErrors = Partial<Record<keyof ContactFormValues, string>>

export const emptyContactForm: ContactFormValues = {
  name: '',
  email: '',
  phone: '',
  message: '',
}

// Deliberately permissive: catches obvious typos without rejecting valid
// addresses that a stricter pattern would.
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

export function validateContactForm(
  values: ContactFormValues,
): ContactFormErrors {
  const errors: ContactFormErrors = {}

  if (!values.name.trim()) {
    errors.name = 'Please enter your name.'
  } else if (values.name.trim().length < 2) {
    errors.name = 'Name looks too short.'
  }

  if (!values.email.trim()) {
    errors.email = 'Please enter your email address.'
  } else if (!EMAIL_PATTERN.test(values.email.trim())) {
    errors.email = 'Enter a valid email address, e.g. name@example.com.'
  }

  const digits = values.phone.replace(/\D/g, '')
  if (!digits) {
    errors.phone = 'Please enter a contact number.'
  } else if (digits.length < 7 || digits.length > 15) {
    errors.phone = 'Enter a valid phone number (7-15 digits).'
  }

  if (!values.message.trim()) {
    errors.message = 'Please enter a message.'
  } else if (values.message.trim().length < 10) {
    errors.message = 'Message should be at least 10 characters.'
  }

  return errors
}

/**
 * Builds the wa.me deep link.
 *
 * The destination number comes from VITE_WHATSAPP_NUMBER — a public contact
 * detail, not a secret. Returns null when it is not configured, so the caller
 * can say so plainly rather than opening a broken link.
 */
export function buildWhatsappUrl(values: ContactFormValues): string | null {
  if (!env.isWhatsappConfigured) return null

  const lines = [
    'New MarketPulse AI enquiry',
    '',
    `Name: ${values.name.trim()}`,
    `Email: ${values.email.trim()}`,
    `Phone: ${values.phone.trim()}`,
    '',
    'Message:',
    values.message.trim(),
  ]

  return `https://wa.me/${env.whatsappNumber}?text=${encodeURIComponent(lines.join('\n'))}`
}
