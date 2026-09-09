/**
 * Theme context, kept separate from the provider component so that the
 * provider file exports components only and Fast Refresh keeps working.
 */

import { createContext } from 'react'

export type ThemePreference = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'marketpulse-theme'

export interface ThemeContextValue {
  /** What the user chose, including 'system'. */
  preference: ThemePreference
  /** What is actually rendered right now. */
  theme: ResolvedTheme
  setPreference: (next: ThemePreference) => void
  /** Flips between light and dark, leaving 'system' behind. */
  toggle: () => void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)
