import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export type Tone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger' | 'info'

const TONES: Record<Tone, string> = {
  neutral: 'bg-zinc-100 text-zinc-700 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:ring-zinc-700',
  brand: 'bg-brand-50 text-brand-700 ring-brand-200 dark:bg-brand-950/60 dark:text-brand-300 dark:ring-brand-800',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-300 dark:ring-emerald-900',
  warning: 'bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-950/50 dark:text-amber-300 dark:ring-amber-900',
  danger: 'bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-950/50 dark:text-rose-300 dark:ring-rose-900',
  info: 'bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-950/50 dark:text-sky-300 dark:ring-sky-900',
}

export function Badge({ tone = 'neutral', icon, children, className }: {
  tone?: Tone
  icon?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap ring-1 ring-inset',
        TONES[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  )
}
