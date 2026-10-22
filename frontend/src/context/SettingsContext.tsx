import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { readStorage, STORAGE_KEYS, writeStorage } from '../lib/storage'

type Theme = 'light' | 'dark'

interface Settings {
  theme: Theme
  toggleTheme: () => void
  /** Run validated SQL against the sample database (off = SQL only). */
  execute: boolean
  setExecute: (value: boolean) => void
}

const SettingsContext = createContext<Settings | null>(null)

function initialTheme(): Theme {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(initialTheme)
  const [execute, setExecuteState] = useState(() => readStorage(STORAGE_KEYS.execute) !== 'false')

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    writeStorage(STORAGE_KEYS.theme, theme)
  }, [theme])

  const value = useMemo<Settings>(
    () => ({
      theme,
      toggleTheme: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')),
      execute,
      setExecute: (v) => {
        setExecuteState(v)
        writeStorage(STORAGE_KEYS.execute, String(v))
      },
    }),
    [theme, execute],
  )

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
}

export function useSettings(): Settings {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used inside <SettingsProvider>')
  return ctx
}
