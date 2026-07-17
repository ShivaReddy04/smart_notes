/* src/lib/theme.ts
 *
 * The single source of truth for light/dark theming. One hook, `useTheme`,
 * owns the whole contract so the rest of the app never touches localStorage or
 * the `.dark` class directly:
 *
 *   * First load with no saved choice  -> follow the OS (prefers-color-scheme).
 *   * User toggles                      -> their choice is saved and wins.
 *   * OS theme changes while unsaved    -> the app follows it live.
 *
 * The actual switch is a single `.dark` class on <html>, which drives every
 * `dark:` utility (see the @custom-variant in index.css). A tiny inline script
 * in index.html applies the same class BEFORE React mounts, so there is no
 * flash of the wrong theme on load; this module keeps it in sync afterwards.
 *
 * STORAGE_KEY is duplicated in that inline script — keep the two in step. */

import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

/** localStorage key holding the user's explicit choice (absent = follow OS). */
const STORAGE_KEY = 'ai-smart-notes-theme'

/** The OS's current preference, used as the default when nothing is saved. */
function systemPrefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

/** Resolve the theme to use right now: saved choice if any, else the OS. */
function getInitialTheme(): Theme {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved === 'light' || saved === 'dark') return saved
  return systemPrefersDark() ? 'dark' : 'light'
}

/** Reflect a theme onto <html> — the one place the class is toggled. */
function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle('dark', theme === 'dark')
}

/**
 * React binding for the theme. Returns the current theme plus `toggle` (flip
 * and save) and `setTheme` (set explicitly and save). Whenever `theme` changes
 * the `.dark` class is re-applied; while the user has made no explicit choice,
 * the hook also tracks live OS changes.
 */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme)

  // Keep <html> in sync with state.
  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  // Follow the OS live, but only until the user makes an explicit choice.
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => {
      if (!localStorage.getItem(STORAGE_KEY)) {
        setThemeState(media.matches ? 'dark' : 'light')
      }
    }
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  const setTheme = (next: Theme) => {
    localStorage.setItem(STORAGE_KEY, next)
    setThemeState(next)
  }

  const toggle = () => setTheme(theme === 'dark' ? 'light' : 'dark')

  return { theme, setTheme, toggle }
}
