import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, ApiError, AUTH_EXPIRED_EVENT, session } from '../api/client'
import type { User } from '../api/types'

interface Auth {
  user: User | null
  /** True while a remembered session is being checked on page load. */
  checking: boolean
  /** The dev account sees the internals (Dev tab, prompts, LLM calls). Enforced by the API too. */
  isDev: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<Auth | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [checking, setChecking] = useState(() => !!session.token())

  const logout = useCallback(() => {
    session.set(null)
    setUser(null)
  }, [])

  // Restore a remembered session.
  useEffect(() => {
    if (!session.token()) return
    api
      .me()
      .then(setUser)
      .catch(() => session.set(null))
      .finally(() => setChecking(false))
  }, [])

  // Any 401 from the API (expired token) signs the user out.
  useEffect(() => {
    window.addEventListener(AUTH_EXPIRED_EVENT, logout)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, logout)
  }, [logout])

  const login = useCallback(async (username: string, password: string) => {
    try {
      const { token, user: signedIn } = await api.login(username, password)
      session.set(token)
      setUser(signedIn)
    } catch (err) {
      throw err instanceof ApiError ? err : new ApiError(0, 'Could not reach the server.')
    }
  }, [])

  const value = useMemo<Auth>(
    () => ({ user, checking, isDev: user?.role === 'dev', login, logout }),
    [user, checking, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): Auth {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
