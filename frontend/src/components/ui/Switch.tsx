import { useId } from 'react'
import { cn } from '../../lib/cn'

export function Switch({ checked, onChange, label, description }: {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  description?: string
}) {
  const id = useId()
  return (
    <label htmlFor={id} className="inline-flex cursor-pointer items-center gap-2 select-none" title={description}>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors',
          'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500',
          checked ? 'bg-brand-600 dark:bg-brand-500' : 'bg-zinc-300 dark:bg-zinc-700',
        )}
      >
        <span
          className={cn(
            'inline-block h-4 w-4 rounded-full bg-white shadow transition-transform',
            checked ? 'translate-x-4' : 'translate-x-0.5',
          )}
        />
      </button>
      <span className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{label}</span>
    </label>
  )
}
