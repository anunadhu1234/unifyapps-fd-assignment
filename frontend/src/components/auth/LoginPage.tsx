import { Building2, Cpu, Eye, EyeOff, Lock, User as UserIcon } from 'lucide-react'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { api } from '../../api/client'
import type { Role, User } from '../../api/types'
import { useAuth } from '../../context/AuthContext'
import { cn } from '../../lib/cn'
import { Spinner } from '../ui/Spinner'
import { LoginShowcase } from './LoginShowcase'
import { NetworkLines } from './NetworkLines'

const WAKE_HINT_AFTER_MS = 3000

const ROLE_INFO: Record<Role, { title: string; icon: ReactNode; sees: string }> = {
  normal: {
    title: 'Business user',
    icon: <UserIcon size={15} />,
    sees: 'Chat in plain English: SQL, explanation, results and cost estimate.',
  },
  dev: {
    title: 'Developer',
    icon: <Cpu size={15} />,
    sees: 'Everything a business user sees, plus the pipeline trace, every LLM call (tokens, cost) and run history.',
  },
}

/** Full-screen sign-in: product showcase on the left, the form on the right. */
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

  const selected = accounts.find((a) => a.username === username.trim().toLowerCase())

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
    <div className="grid min-h-full lg:grid-cols-[1.08fr_1fr]">
      <LoginShowcase />

      <main className="relative flex min-h-full flex-col items-center justify-center overflow-hidden bg-white px-6 py-16 dark:bg-zinc-950">
        <NetworkLines />

        <div className="relative w-full max-w-[400px]">
          {/* client logo placeholder: a deployment shows the customer's own mark here */}
          <div className="flex flex-col items-center text-center">
            <span className="grid h-16 w-16 place-items-center rounded-full bg-gradient-to-br from-brand-500 via-brand-600 to-violet-600 text-white shadow-brand ring-4 ring-brand-100 dark:ring-brand-950">
              <Building2 size={28} strokeWidth={2} />
            </span>
            <p className="mt-3 text-xl font-semibold tracking-tight text-brand-800 dark:text-brand-200">Client</p>
            <p className="mt-5 text-[15px] text-zinc-600 dark:text-zinc-400">Please enter your login details</p>
          </div>

          {waking && (
            <p role="status" className="mt-5 flex items-center gap-2 rounded-lg bg-brand-50 px-3 py-2 text-xs text-brand-700 dark:bg-brand-950/50 dark:text-brand-300">
              <Spinner className="h-3 w-3 shrink-0" /> Waking the server up — the free host sleeps when idle, so this can take up to a minute.
            </p>
          )}

          {accounts.length > 0 && (
            <div className="mt-6">
              <div className="grid grid-cols-2 gap-1 rounded-xl bg-zinc-100 p-1 dark:bg-zinc-900" role="radiogroup" aria-label="Test account">
                {accounts.map((a) => (
                  <button
                    key={a.username}
                    type="button"
                    role="radio"
                    aria-checked={selected?.username === a.username}
                    onClick={() => setUsername(a.username)}
                    className={cn(
                      'flex h-9 items-center justify-center gap-1.5 rounded-lg text-sm font-medium transition-all',
                      selected?.username === a.username
                        ? 'bg-white text-brand-700 shadow-sm ring-1 ring-brand-200 dark:bg-zinc-800 dark:text-brand-300 dark:ring-brand-800'
                        : 'text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200',
                    )}
                  >
                    {ROLE_INFO[a.role].icon}
                    {ROLE_INFO[a.role].title}
                  </button>
                ))}
              </div>
              <p className="mt-2 min-h-[2.5rem] text-center text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
                {selected ? ROLE_INFO[selected.role].sees : 'Choose a test account to see what it can access.'}
              </p>
            </div>
          )}

          <form onSubmit={submit} className="mt-4 space-y-3.5">
            <Field icon={<UserIcon size={16} />}>
              <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required
                placeholder="Username" aria-label="Username"
                className="h-12 min-w-0 flex-1 bg-transparent pr-4 text-[15px] outline-none placeholder:text-zinc-400" />
            </Field>
            <Field icon={<Lock size={16} />}>
              <input type={show ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password" required placeholder="Password" aria-label="Password"
                className="h-12 min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-zinc-400" />
              <button type="button" onClick={() => setShow(!show)} aria-label={show ? 'Hide password' : 'Show password'}
                className="px-4 text-zinc-400 transition-colors hover:text-brand-600">
                {show ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </Field>

            {error && <p role="alert" className="text-sm text-rose-600 dark:text-rose-400">{error}</p>}

            <button type="submit" disabled={busy}
              className="bg-brand-pill shadow-brand mt-2 flex h-12 w-full items-center justify-center gap-2 rounded-xl text-[15px] font-semibold text-white transition-opacity hover:opacity-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 disabled:cursor-not-allowed disabled:opacity-60">
              {busy && <Spinner className="h-4 w-4" />}
              {busy ? 'Signing in…' : 'Login'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-zinc-500 dark:text-zinc-400">
            Test passwords are shared with reviewers
          </p>
          <p className="mt-10 text-center text-[11px] font-semibold tracking-[0.28em] text-zinc-400 lg:hidden">
            POWERED BY SQL QUERY AGENT
          </p>
        </div>
      </main>
    </div>
  )
}

function Field({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <label className="flex items-center rounded-xl border border-brand-100 bg-brand-50/60 text-zinc-800 transition-shadow focus-within:border-brand-400 focus-within:bg-white focus-within:ring-4 focus-within:ring-brand-500/10 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 dark:focus-within:border-brand-500 dark:focus-within:bg-zinc-900 dark:focus-within:ring-brand-500/20">
      <span className="pl-4 pr-3 text-brand-400">{icon}</span>
      {children}
    </label>
  )
}
