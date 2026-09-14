import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { AuthLayout } from '@/components/AuthLayout'
import { Button } from '@/components/Button'
import { Field } from '@/components/Field'
import { FormAlert } from '@/components/FormAlert'
import { useAuth } from '@/hooks/useAuth'
import { ApiRequestError } from '@/services/apiClient'

interface Errors {
  email?: string
  password?: string
}

export function LoginPage() {
  const { login, status, sessionError } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Where ProtectedRoute was sending the user. Only same-app paths are honoured.
  const requested = (location.state as { from?: unknown } | null)?.from
  const destination = typeof requested === 'string' && requested.startsWith('/') && !requested.startsWith('//') ? requested : '/dashboard'

  // Already signed in (including the render right after a successful login):
  // go straight to the requested page rather than showing a dead form.
  if (status === 'authenticated') return <Navigate to={destination} replace />

  const validate = (): Errors => {
    const next: Errors = {}
    if (!email.trim()) next.email = 'Please enter your email address.'
    if (!password) next.password = 'Please enter your password.'
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
      await login({ email: email.trim(), password })
      // Return the user to whatever they were trying to reach.
      navigate(destination, { replace: true })
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

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to reach your MarketPulse AI dashboard."
      footer={
        <>
          Don&rsquo;t have an account?{' '}
          <Link
            to="/register"
            className="font-medium text-accent-text hover:underline"
          >
            Create one
          </Link>
        </>
      }
    >
      <form noValidate onSubmit={handleSubmit} className="space-y-5">
        {(formError || sessionError) && <FormAlert>{formError || sessionError}</FormAlert>}

        <Field
          label="Email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="name@example.com"
          value={email}
          onChange={(value) => {
            setEmail(value)
            setErrors((current) => ({ ...current, email: undefined }))
          }}
          error={errors.email}
        />

        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="current-password"
          placeholder="Your password"
          value={password}
          onChange={(value) => {
            setPassword(value)
            setErrors((current) => ({ ...current, password: undefined }))
          }}
          error={errors.password}
        />

        <Button type="submit" size="lg" className="w-full" disabled={submitting}>
          {submitting ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
    </AuthLayout>
  )
}
