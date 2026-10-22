import { LogOut, Moon, Sun, UserRound } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { useSettings } from '../../context/SettingsContext'
import { cn } from '../../lib/cn'

function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join('') || '?'
}

/** Avatar with a gradient ring that opens into an account card (role, theme, sign out). */
export function ProfileMenu() {
  const { user, isDev, logout } = useAuth()
  const { theme, toggleTheme } = useSettings()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false)
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('mousedown', close)
    window.addEventListener('keydown', esc)
    return () => {
      window.removeEventListener('mousedown', close)
      window.removeEventListener('keydown', esc)
    }
  }, [open])

  if (!user) return null
  const letters = initials(user.display_name)

  return (
    <div ref={ref} className="relative" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        aria-label="Account"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="relative h-10 w-10 cursor-pointer rounded-full bg-gradient-to-br from-brand-500 via-brand-600 to-brand-800 p-[2px] shadow-[0_10px_24px_-10px_rgba(55,48,163,0.6)] transition-transform duration-200 hover:scale-105"
      >
        <span className="grid h-full w-full place-items-center rounded-full bg-white text-[12px] font-bold tracking-wider text-brand-800 select-none dark:bg-zinc-900 dark:text-brand-300">
          {letters}
        </span>
      </button>

      <div
        className={cn(
          'absolute top-0 right-0 z-50 w-72 origin-top-right overflow-hidden rounded-2xl bg-white transition-all duration-300 ease-out dark:bg-zinc-900',
          open ? 'visible translate-y-0 scale-100 opacity-100' : 'pointer-events-none invisible -translate-y-2 scale-95 opacity-0',
        )}
        style={{ boxShadow: '0 24px 60px -24px rgba(30,27,75,0.45), 0 0 0 1px rgba(55,48,163,0.08)' }}
      >
        <div
          className="relative px-4 py-4 text-white"
          style={{ background: 'radial-gradient(130% 100% at 100% 0%, rgba(255,255,255,0.16), transparent 55%), linear-gradient(135deg, #5148e6 0%, #4338ca 55%, #3730a3 100%)' }}
        >
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-white text-[14px] font-bold tracking-wider text-brand-800 shadow-md ring-2 ring-white/30 select-none">
              {letters}
            </div>
            <div className="flex min-w-0 flex-col leading-tight">
              <span className="truncate text-[14px] font-semibold">{user.display_name}</span>
              <span className="truncate text-[11.5px] text-white/65">@{user.username}</span>
            </div>
            <span className="ml-auto shrink-0 rounded-full bg-white/15 px-2 py-0.5 text-[9px] font-bold tracking-[0.18em] ring-1 ring-white/25">
              {isDev ? 'DEV' : 'USER'}
            </span>
          </div>
          <p className="mt-3 text-[11.5px] leading-snug text-white/75">
            {isDev
              ? 'Developer view: every answer has a Dev tab with model routing, LLM calls, plan and trace.'
              : 'Business view: SQL, explanation, results, validation and cost for every answer.'}
          </p>
        </div>
        <div className="bg-white p-1.5 dark:bg-zinc-900">
          <MenuButton icon={<UserRound size={17} />} label={isDev ? 'Developer account' : 'Business account'} />
          <MenuButton icon={theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
            label={theme === 'dark' ? 'Light mode' : 'Dark mode'} onClick={toggleTheme} />
          <div className="mx-2 my-1 h-px bg-zinc-100 dark:bg-zinc-800" />
          <MenuButton icon={<LogOut size={17} />} label="Sign out" onClick={logout} accent />
        </div>
      </div>
    </div>
  )
}

function MenuButton({ icon, label, onClick, accent }: { icon: React.ReactNode; label: string; onClick?: () => void; accent?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className={cn(
        'flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-[13.5px] font-medium transition-colors duration-150',
        onClick ? 'cursor-pointer hover:bg-brand-600/[0.06] dark:hover:bg-white/5' : 'cursor-default',
        accent ? 'text-brand-700 dark:text-brand-300' : 'text-zinc-700 dark:text-zinc-200',
      )}
    >
      <span className="text-brand-600 dark:text-brand-400">{icon}</span>
      {label}
    </button>
  )
}
