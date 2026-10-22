import { CheckCircle2, AlertTriangle, X } from 'lucide-react'
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { cn } from '../../lib/cn'

type ToastTone = 'success' | 'error'
interface ToastItem {
  id: number
  tone: ToastTone
  message: string
}

interface ToastApi {
  success: (message: string) => void
  error: (message: string) => void
}

const ToastContext = createContext<ToastApi | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: number) => setItems((all) => all.filter((t) => t.id !== id)), [])
  const push = useCallback(
    (tone: ToastTone, message: string) => {
      const id = Date.now() + Math.random()
      setItems((all) => [...all.slice(-2), { id, tone, message }])
      setTimeout(() => dismiss(id), tone === 'error' ? 6000 : 2500)
    },
    [dismiss],
  )
  const api = useMemo<ToastApi>(
    () => ({ success: (m) => push('success', m), error: (m) => push('error', m) }),
    [push],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-80 flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            className={cn(
              'animate-fade-in pointer-events-auto flex items-start gap-2.5 rounded-xl border bg-white px-3.5 py-3 text-sm shadow-lg dark:bg-zinc-900',
              t.tone === 'success' ? 'border-emerald-200 dark:border-emerald-900' : 'border-rose-200 dark:border-rose-900',
            )}
          >
            {t.tone === 'success' ? (
              <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-600" />
            ) : (
              <AlertTriangle size={16} className="mt-0.5 shrink-0 text-rose-600" />
            )}
            <p className="flex-1 text-zinc-700 dark:text-zinc-200">{t.message}</p>
            <button aria-label="Dismiss" onClick={() => dismiss(t.id)} className="text-zinc-400 hover:text-zinc-600">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
