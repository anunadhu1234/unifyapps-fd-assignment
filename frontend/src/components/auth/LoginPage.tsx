import { Code2, Cpu, Database, Eye, EyeOff, LogIn, ShieldCheck, User as UserIcon } from 'lucide-react'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { api } from '../../api/client'
import type { Role, User } from '../../api/types'
import { useAuth } from '../../context/AuthContext'
import { cn } from '../../lib/cn'
import { Button } from '../ui/Button'
import { Spinner } from '../ui/Spinner'

const WAKE_HINT_AFTER_MS = 3000

const ROLE_INFO: Record<Role, { title: string; icon: ReactNode; sees: string[] }> = {
  normal: {
    title: 'Business user',
    icon: <UserIcon size={16} />,
    sees: ['Chat in plain English', 'SQL, explanation and results', 'Validation checks and cost estimate'],
  },
  dev: {
    title: 'Developer',
    icon: <Cpu size={16} />,
    sees: ['Everything a business user sees', 'Model routing and every LLM call (tokens, cost)', 'Plan, retrieval, validation attempts, node trace, prompts'],
  },
}

/** Sign in with one of the two test accounts (passwords are shared with reviewers). */
export function LoginPage() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [accounts, setAccounts] = useState<User[]>([])
  // The free hosting tier sleeps when idle; if the first call is slow, say why instead of looking broken.
  const [waking, setWaking] = useState(false)

  useEffect(() => {
    const timer = window.setTimeout(() => setWaking(true), WAKE_HINT_AFTER_MS)
    api
      .accounts()
      .then(setAccounts)
      .catch(() => setAccounts([]))
      .finally(() => {
        window.clearTimeout(timer)
        setWaking(false)
      })
    return () => window.clearTimeout(timer)
  }, [])

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(username, password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app-canvas flex min-h-full items-center justify-center px-4 py-10">
      <div className="relative grid w-full max-w-4xl overflow-hidden rounded-3xl border border-zinc-200/70 bg-white lg:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900" style={{ boxShadow: '0 24px 60px -24px rgba(30,27,75,0.32)' }}>
        <section className="bg-brand-panel flex flex-col justify-between gap-8 p-8 text-white">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-white/10 shadow-inner ring-1 ring-white/15"><Database size={20} /></div>
              <span className="text-lg font-semibold">SQL Query Agent</span>
            </div>
            <h1 className="mt-8 text-2xl leading-snug font-semibold">Ask your database questions in plain English.</h1>
            <p className="mt-3 text-sm text-brand-100">
              A LangGraph agent that plans, writes, validates and explains read-only SQL over the Summit Supply Co.
              database — and optimizes or debugs the SQL you paste.
            </p>
          </div>
          <ul className="space-y-2.5 text-sm text-brand-50">
            <Feature icon={<ShieldCheck size={15} />}>Every query validated against the real schema — read-only, always</Feature>
            <Feature icon={<Code2 size={15} />}>SQL, plain-English explanation, results, cost estimate</Feature>
          </ul>
        </section>

        <section className="p-8">
          <h2 className="text-lg font-semibold">Sign in</h2>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">Choose one of the two test accounts and enter its password.</p>
          {waking && (
            <p role="status" className="mt-3 flex items-center gap-2 rounded-lg bg-brand-50 px-3 py-2 text-xs text-brand-700 dark:bg-brand-950/40 dark:text-brand-300">
              <Spinner className="h-3 w-3 shrink-0" /> Waking the server up — the free host sleeps when idle, so this can take up to a minute.
            </p>
          )}

          <div className="mt-5 grid grid-cols-1 gap-2 sm:grid-cols-2">
            {accounts.map((a) => (
              <button
                key={a.username}
                type="button"
                onClick={() => setUsername(a.username)}
                className={cn(
                  'rounded-xl border p-3 text-left transition-colors',
                  username === a.username
                    ? 'border-brand-400 bg-brand-50/60 dark:border-brand-600 dark:bg-brand-950/40'
                    : 'border-zinc-200 hover:border-zinc-300 dark:border-zinc-700 dark:hover:border-zinc-600',
                )}
              >
                <p className="flex items-center gap-1.5 text-sm font-semibold">
                  <span className="text-brand-600 dark:text-brand-400">{ROLE_INFO[a.role].icon}</span>
                  {ROLE_INFO[a.role].title}
                </p>
                <p className="mt-0.5 font-mono text-[11px] text-zinc-500">{a.username}</p>
                <ul className="mt-2 space-y-0.5 text-[11px] text-zinc-500 dark:text-zinc-400">
                  {ROLE_INFO[a.role].sees.map((s) => <li key={s}>• {s}</li>)}
                </ul>
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="mt-5 space-y-3">
            <Field label="Username">
              <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required
                className="h-10 w-full bg-transparent px-3 text-sm outline-none" />
            </Field>
            <Field label="Password">
              <div className="flex items-center">
                <input type={show ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password" required className="h-10 min-w-0 flex-1 bg-transparent px-3 text-sm outline-none" />
                <button type="button" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'}
                  className="px-3 text-zinc-400 hover:text-zinc-600">
                  {show ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </Field>
            {error && <p role="alert" className="text-sm text-rose-600 dark:text-rose-400">{error}</p>}
            <Button type="submit" variant="primary" className="h-10 w-full" icon={<LogIn size={16} />} disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </section>
      </div>
    </div>
  )
}

function Feature({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <span className="mt-0.5 shrink-0">{icon}</span>
      {children}
    </li>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300">{label}</span>
      <div className="mt-1 rounded-lg border border-zinc-200 focus-within:border-brand-400 focus-within:ring-4 focus-within:ring-brand-500/10 dark:border-zinc-700">
        {children}
      </div>
    </label>
  )
}
