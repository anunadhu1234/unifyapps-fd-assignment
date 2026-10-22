import { ChevronRight } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { cn } from '../../lib/cn'

/** Titled block inside the inspector panels. */
export function Section({ title, icon, actions, children, className }: {
  title: string
  icon?: ReactNode
  actions?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn('space-y-2.5', className)}>
      <div className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-zinc-500 uppercase dark:text-zinc-400">
          {icon}
          {title}
        </h3>
        {actions && <div className="flex items-center gap-1.5">{actions}</div>}
      </div>
      {children}
    </section>
  )
}

/** Expandable block for secondary detail (raw JSON, original SQL…). */
export function Collapsible({ title, children, defaultOpen = false, meta }: {
  title: ReactNode
  children: ReactNode
  defaultOpen?: boolean
  meta?: ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-medium hover:bg-zinc-50 dark:hover:bg-zinc-900"
      >
        <ChevronRight size={14} className={cn('shrink-0 text-zinc-400 transition-transform', open && 'rotate-90')} />
        <span className="flex-1 truncate">{title}</span>
        {meta}
      </button>
      {open && <div className="border-t border-zinc-200 p-3 dark:border-zinc-800">{children}</div>}
    </div>
  )
}

export function JsonView({ value }: { value: unknown }) {
  return (
    <pre className="max-h-96 overflow-auto scrollbar-thin rounded-md bg-zinc-50 p-3 font-mono text-[11px] leading-relaxed text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

export function EmptyHint({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      {icon && <div className="text-zinc-300 dark:text-zinc-600">{icon}</div>}
      <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{title}</p>
      {children && <p className="max-w-xs text-xs text-zinc-500 dark:text-zinc-400">{children}</p>}
    </div>
  )
}
