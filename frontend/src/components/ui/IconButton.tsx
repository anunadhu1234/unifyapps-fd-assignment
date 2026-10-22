import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { cn } from '../../lib/cn'

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string // accessible name and tooltip
  icon: ReactNode
  size?: 'sm' | 'md'
  active?: boolean
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, icon, size = 'md', active, className, type = 'button', ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      title={label}
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-lg transition-colors',
        'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100',
        'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 disabled:opacity-50',
        size === 'sm' ? 'h-7 w-7' : 'h-9 w-9',
        active && 'bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100',
        className,
      )}
      {...props}
    >
      {icon}
    </button>
  )
})
