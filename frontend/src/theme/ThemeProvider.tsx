/**
 * Light/dark theme with three states: an explicit 'light' or 'dark' choice,
 * or 'system' (the default) which follows the OS setting and keeps following
 * it if the user changes it while the page is open.
 */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import {
  THEME_STORAGE_KEY,
  ThemeContext,
  type ResolvedTheme,
  type ThemePreference,
} from '@/theme/themeContext'

function readStoredPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    if (stored === 'light' || stored === 'dark' || stored === 'system') {
      return stored
    }
  } catch {
    // Private mode or blocked storage: fall through to the system default.
  }
  return 'system'
}

function systemTheme(): ResolvedTheme {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] =
    useState<ThemePreference>(readStoredPreference)
  // Only tracks what the OS reports. The rendered theme is derived from it,
  // so no effect ever has to push a value back into state.
  const [systemPreference, setSystemPreference] =
    useState<ResolvedTheme>(systemTheme)

  const theme: ResolvedTheme =
    preference === 'system' ? systemPreference : preference

  // Apply the resolved theme to <html> and tell the browser which built-in
  // control colours to use.
  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', theme === 'dark')
    root.style.colorScheme = theme
  }, [theme])

  // Keep following the OS setting while it changes. Subscribed always, since
  // the value is only read when the preference is 'system'.
  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (event: MediaQueryListEvent) =>
      setSystemPreference(event.matches ? 'dark' : 'light')

    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next)
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next)
    } catch {
      // Preference simply will not persist; the session still works.
    }
  }, [])

  const toggle = useCallback(() => {
    setPreference(theme === 'dark' ? 'light' : 'dark')
  }, [setPreference, theme])

  const value = useMemo(
    () => ({ preference, theme, setPreference, toggle }),
    [preference, theme, setPreference, toggle],
  )

  return <ThemeContext value={value}>{children}</ThemeContext>
}
