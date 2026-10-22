import { AlertTriangle, CheckCircle2, RotateCcw, XCircle } from 'lucide-react'
import type { Validation } from '../../api/types'
import { CHECK_LABELS } from '../../lib/pipeline'

const ORDER = ['syntax', 'read_only', 'tables', 'columns', 'values', 'joins', 'engine', 'plan']

/** The deterministic checks every query passed before it was shown or run. */
export function ValidationChecklist({ validation }: { validation: Validation }) {
  const passed = new Set(validation.checks_passed)
  const checks = ORDER.filter((c) => passed.has(c) || c !== 'plan')
  return (
    <div className="space-y-3">
      <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
        {checks.map((check) => (
          <li key={check} className="flex items-center gap-2 text-sm">
            {passed.has(check) ? (
              <CheckCircle2 size={15} className="shrink-0 text-emerald-600 dark:text-emerald-400" />
            ) : (
              <XCircle size={15} className="shrink-0 text-zinc-300 dark:text-zinc-600" />
            )}
            <span className={passed.has(check) ? 'text-zinc-700 dark:text-zinc-300' : 'text-zinc-400'}>
              {CHECK_LABELS[check]}
            </span>
          </li>
        ))}
      </ul>
      {validation.attempts > 1 && (
        <p className="flex items-center gap-2 rounded-lg bg-brand-50 px-3 py-2 text-xs text-brand-800 dark:bg-brand-950/50 dark:text-brand-200">
          <RotateCcw size={13} className="shrink-0" />
          Self-corrected: the first draft failed validation and was repaired ({validation.attempts} attempts).
        </p>
      )}
      {[...validation.errors, ...validation.warnings].map((f, i) => (
        <div
          key={i}
          className={
            f.severity === 'error'
              ? 'rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200'
              : 'rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200'
          }
        >
          <p className="flex items-start gap-1.5 font-medium">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" />
            {f.message}
          </p>
          {f.hint && <p className="mt-1 pl-5 opacity-80">{f.hint}</p>}
        </div>
      ))}
    </div>
  )
}
