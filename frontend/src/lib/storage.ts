// localStorage can be unavailable (private mode, blocked storage) — never let that break the app.

export function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    /* storage unavailable: keep working without persistence */
  }
}

export const STORAGE_KEYS = {
  clientId: 'sql-agent:client-id',
  authToken: 'sql-agent:auth-token',
  theme: 'theme',
  execute: 'sql-agent:execute',
  activeThread: 'sql-agent:active-thread',
} as const
