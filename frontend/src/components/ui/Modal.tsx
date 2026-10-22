import { X } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../lib/cn'
import { IconButton } from './IconButton'

function useEscape(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
}

/** Centered dialog. */
export function Modal({ open, onClose, title, children, footer, wide }: {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}) {
  useEscape(open, onClose)
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-zinc-950/40 backdrop-blur-[2px]" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          'animate-fade-in relative flex max-h-[85vh] w-full flex-col rounded-2xl border border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-900',
          wide ? 'max-w-4xl' : 'max-w-md',
        )}
      >
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-3.5 dark:border-zinc-800">
          <h2 className="text-sm font-semibold">{title}</h2>
          <IconButton label="Close" icon={<X size={16} />} size="sm" onClick={onClose} />
        </div>
        <div className="overflow-y-auto scrollbar-thin px-5 py-4">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 border-t border-zinc-200 px-5 py-3 dark:border-zinc-800">{footer}</div>
        )}
      </div>
    </div>,
    document.body,
  )
}

/** Panel sliding in from the right (schema explorer, mobile inspector). */
export function Drawer({ open, onClose, title, children, className }: {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  className?: string
}) {
  useEscape(open, onClose)
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-40">
      <div className="absolute inset-0 bg-zinc-950/30" onClick={onClose} />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          'absolute inset-y-0 right-0 flex w-full flex-col border-l border-zinc-200 bg-white shadow-2xl sm:max-w-xl dark:border-zinc-800 dark:bg-zinc-950',
          className,
        )}
      >
        <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <h2 className="text-sm font-semibold">{title}</h2>
          <IconButton label="Close" icon={<X size={16} />} size="sm" onClick={onClose} />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">{children}</div>
      </aside>
    </div>,
    document.body,
  )
}
