import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { AuthLayout } from '@/components/AuthLayout'
import { Button } from '@/components/Button'
import { Field } from '@/components/Field'
import { FormAlert } from '@/components/FormAlert'
import { useAuth } from '@/hooks/useAuth'
import { ApiRequestError } from '@/services/apiClient'

interface Errors {
  fullName?: string
  email?: string
  password?: string
  confirmPassword?: string
}

// Mirrors the backend rules in app/schemas/auth.py, so the user gets immediate
// feedback instead of a round trip. The server remains the real gate.
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/
const MIN_PASSWORD_LENGTH = 8

export function RegisterPage() {
  const { register, status } = useAuth()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (status === 'authenticated') return <Navigate to="/dashboard" replace />

  const validate = (): Errors => {
    const next: Errors = {}

    if (!email.trim()) {
      next.email = 'Please enter your email address.'
    } else if (!EMAIL_PATTERN.test(email.trim())) {
      next.email = 'Enter a valid email address, e.g. name@example.com.'
    }

    if (fullName.trim().length > 120) next.fullName = 'Name must be at most 120 characters.'

    if (!password) {
      next.password = 'Please choose a password.'
    } else if (password.length < MIN_PASSWORD_LENGTH) {
      next.password = `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`
    } else if (password.length > 64 || new TextEncoder().encode(password).length > 72) {
      next.password = 'Password must be at most 64 characters and 72 UTF-8 bytes.'
    } else if (!/\p{L}/u.test(password)) {
      next.password = 'Password must contain at least one letter.'
    } else if (!/\p{N}/u.test(password)) {
      next.password = 'Password must contain at least one number.'
    }

    if (confirmPassword !== password) {
      next.confirmPassword = 'Passwords do not match.'
    }

    return next
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setFormError(null)

    const nextErrors = validate()
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setSubmitting(true)
    try {
      await register({
        email: email.trim(),
        password,
        full_name: fullName.trim() || undefined,
      })
      navigate('/dashboard', { replace: true })
    } catch (error) {
      setFormError(
        error instanceof ApiRequestError
          ? error.message
          : 'Something went wrong. Please try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  const clear = (field: keyof Errors) =>
    setErrors((current) => ({ ...current, [field]: undefined }))

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Set up MarketPulse AI and start comparing marketplace opportunities."
      footer={
        <>
          Already have an account?{' '}
          <Link
            to="/login"
            className="font-medium text-accent-text hover:underline"
          >
            Sign in
          </Link>
        </>
      }
    >
      <form noValidate onSubmit={handleSubmit} className="space-y-5">
        {formError && <FormAlert>{formError}</FormAlert>}

        <Field
          label="Full name (optional)"
          name="full_name"
          autoComplete="name"
          placeholder="Your name"
          value={fullName}
          onChange={(value) => {
            setFullName(value)
            clear('fullName')
          }}
          error={errors.fullName}
        />

        <Field
          label="Email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="name@example.com"
          value={email}
          onChange={(value) => {
            setEmail(value)
            clear('email')
          }}
          error={errors.email}
        />

        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          placeholder="At least 8 characters"
          value={password}
          onChange={(value) => {
            setPassword(value)
            clear('password')
          }}
          error={errors.password}
        />

        <Field
          label="Confirm password"
          name="confirm_password"
          type="password"
          autoComplete="new-password"
          placeholder="Repeat your password"
          value={confirmPassword}
          onChange={(value) => {
            setConfirmPassword(value)
            clear('confirmPassword')
          }}
          error={errors.confirmPassword}
        />

        <Button type="submit" size="lg" className="w-full" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Create account'}
        </Button>

        <p className="text-xs leading-relaxed text-subtle">
          Passwords are hashed with bcrypt before storage. Your password is never
          stored or logged in plain text.
        </p>
      </form>
    </AuthLayout>
  )
}
