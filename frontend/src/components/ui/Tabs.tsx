import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export interface TabItem<T extends string> {
  id: T
  label: string
  icon?: ReactNode
  badge?: ReactNode
}

/** Underlined tab bar (keyboard: arrow keys move between tabs). */
export function Tabs<T extends string>({ items, value, onChange, className }: {
  items: TabItem<T>[]
  value: T
  onChange: (id: T) => void
  className?: string
}) {
  const move = (delta: number) => {
    const i = items.findIndex((t) => t.id === value)
    onChange(items[(i + delta + items.length) % items.length].id)
  }
  return (
    <div
      role="tablist"
      className={cn('flex gap-1 overflow-x-auto scrollbar-thin border-b border-zinc-200 dark:border-zinc-800', className)}
      onKeyDown={(e) => {
        if (e.key === 'ArrowRight') move(1)
        if (e.key === 'ArrowLeft') move(-1)
      }}
    >
      {items.map((tab) => {
        const active = tab.id === value
        return (
          <button
            key={tab.id}
            role="tab"
            type="button"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(tab.id)}
            className={cn(
              '-mb-px inline-flex items-center gap-1.5 border-b-2 px-2.5 py-2.5 text-[13px] font-medium whitespace-nowrap transition-colors',
              active
                ? 'border-brand-600 text-brand-700 dark:border-brand-400 dark:text-brand-300'
                : 'border-transparent text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200',
            )}
          >
            {tab.icon}
            {tab.label}
            {tab.badge}
          </button>
        )
      })}
    </div>
  )
}

/** Compact pill switcher (e.g. SQL dialects). */
export function Segmented<T extends string>({ items, value, onChange }: {
  items: { id: T; label: string }[]
  value: T
  onChange: (id: T) => void
}) {
  return (
    <div className="inline-flex rounded-lg bg-zinc-100 p-0.5 dark:bg-zinc-800" role="radiogroup">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="radio"
          aria-checked={item.id === value}
          onClick={() => onChange(item.id)}
          className={cn(
            'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
            item.id === value
              ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-950 dark:text-zinc-100'
              : 'text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200',
          )}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
