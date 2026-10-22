import { readStorage, STORAGE_KEYS, writeStorage } from '../lib/storage'
import { readEventStream } from './sse'
import type {
  LoginResponse,
  PromptInfo,
  RunHistory,
  SchemaSummary,
  StreamEvent,
  ThreadSummary,
  Turn,
  User,
} from './types'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

/** Fired when the server rejects the session (expired / invalid token) — the app returns to sign-in. */
export const AUTH_EXPIRED_EVENT = 'sql-agent:auth-expired'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Per-browser id: chats belong to (account, browser), so reviewers sharing a test login stay separate. */
export function getClientId(): string {
  let id = readStorage(STORAGE_KEYS.clientId)
  if (!id) {
    id = `c-${crypto.randomUUID().replace(/-/g, '')}`
    writeStorage(STORAGE_KEYS.clientId, id)
  }
  return id
}

export const session = {
  token: () => readStorage(STORAGE_KEYS.authToken),
  set: (token: string | null) => writeStorage(STORAGE_KEYS.authToken, token),
}

function headers(extra?: HeadersInit): Headers {
  const h = new Headers(extra)
  h.set('X-Client-Id', getClientId())
  const token = session.token()
  if (token) h.set('Authorization', `Bearer ${token}`)
  return h
}

async function errorFrom(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status})`
  try {
    const body = await response.json()
    message = body?.error?.message ?? message
  } catch {
    /* non-JSON error body */
  }
  if (response.status === 401 && session.token()) window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
  return new ApiError(response.status, message)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers: headers(init.headers) })
  if (!response.ok) throw await errorFrom(response)
  return response.json() as Promise<T>
}

function json(method: string, body: unknown): RequestInit {
  return { method, body: JSON.stringify(body), headers: { 'Content-Type': 'application/json' } }
}

export interface ChatRequest {
  question: string
  thread_id?: string | null
  execute: boolean
}

export const api = {
  login: (username: string, password: string) =>
    request<LoginResponse>('/api/auth/login', json('POST', { username, password })),
  me: () => request<{ user: User }>('/api/auth/me').then((r) => r.user),
  /** Test accounts available on this server (usernames and roles only). */
  accounts: () => request<{ accounts: User[] }>('/api/auth/accounts').then((r) => r.accounts),

  /** Ask a question; yields pipeline progress, explanation tokens and finally the response. */
  async *streamChat(body: ChatRequest, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
    const response = await fetch(`${BASE_URL}/api/chat/stream`, {
      ...json('POST', body),
      headers: headers({ 'Content-Type': 'application/json' }),
      signal,
    })
    if (!response.ok || !response.body) throw await errorFrom(response)
    yield* readEventStream(response.body)
  },

  listThreads: () => request<{ threads: ThreadSummary[] }>('/api/threads').then((r) => r.threads),
  getThread: (threadId: string) => request<{ thread_id: string; turns: Turn[] }>(`/api/threads/${threadId}`),
  renameThread: (threadId: string, title: string) => request(`/api/threads/${threadId}`, json('PATCH', { title })),
  deleteThread: (threadId: string) => request(`/api/threads/${threadId}`, { method: 'DELETE' }),

  getSchema: () => request<SchemaSummary>('/api/schema'),
  schemaGraphUrl: `${BASE_URL}/api/schema/graph`,

  /** Full results of an answer as CSV (re-run server-side without the on-screen row cap). */
  async exportCsv(requestId: string): Promise<{ blob: Blob; filename: string }> {
    const response = await fetch(`${BASE_URL}/api/export/${requestId}.csv`, { headers: headers() })
    if (!response.ok) throw await errorFrom(response)
    const disposition = response.headers.get('Content-Disposition') ?? ''
    const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? 'results.csv'
    return { blob: await response.blob(), filename }
  },

  getPrompts: () => request<{ prompts: PromptInfo[] }>('/api/dev/prompts').then((r) => r.prompts),
  getLlmConfig: () => request<Record<string, unknown>>('/api/dev/llm'),
  getRuns: (limit = 100) => request<RunHistory>(`/api/dev/runs?limit=${limit}`),
}
