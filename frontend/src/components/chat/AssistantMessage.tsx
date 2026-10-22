import { AlertOctagon, ArrowRight, Database, HelpCircle, RefreshCw, ShieldAlert, ShieldCheck, Sparkles, Wrench, Zap } from 'lucide-react'
import type { ReactNode } from 'react'
import type { AgentResponse } from '../../api/types'
import { cn } from '../../lib/cn'
import { plural } from '../../lib/format'
import type { AssistantMessage as AssistantMessageModel } from '../../types/chat'
import { CostBadge } from '../sql/CostCard'
import { SqlCode } from '../sql/SqlCode'
import { Badge } from '../ui/Badge'
import { CopyButton } from '../ui/CopyButton'
import { Markdown } from '../ui/Markdown'
import { DiveDeeper } from './DiveDeeper'
import { StreamingProgress } from './StreamingProgress'

interface Props {
  message: AssistantMessageModel
  selected: boolean
  onSelect: () => void
  onRetry: () => void
  onAnswer: (text: string) => void
  /** Another answer is being produced: follow-up suggestions are disabled meanwhile. */
  busy?: boolean
}

/** An answer sits directly on the canvas (no bubble); notices use a white card. */
export function AssistantMessage({ message, selected, onSelect, onRetry, onAnswer, busy }: Props) {
  const r = message.response
  if (message.status === 'streaming') {
    return (
      <div className="animate-fade-in py-1">
        <StreamingProgress steps={message.steps} text={message.streamText} />
      </div>
    )
  }
  if (message.status === 'failed') {
    return <Notice tone="danger" icon={<AlertOctagon size={18} />} text={message.error ?? 'Something went wrong.'} onRetry={onRetry} />
  }
  if (!r) return null

  switch (r.type) {
    case 'refusal':
      return <Notice tone="warning" icon={<ShieldAlert size={18} />} text={r.message} />
    case 'error':
      return <Notice tone="danger" icon={<AlertOctagon size={18} />} text={r.message} onRetry={onRetry} onDetails={onSelect} />
    case 'clarification':
      return (
        <div className="animate-fade-in space-y-3">
          <p className="flex items-start gap-2.5 text-[15px] leading-relaxed text-ink/90 dark:text-zinc-200">
            <HelpCircle size={18} className="mt-0.5 shrink-0 text-brand-600 dark:text-brand-400" /> {r.message}
          </p>
          {!!r.clarification?.options.length && (
            <div className="flex flex-wrap gap-2 pl-7">
              {r.clarification.options.map((o) => (
                <button key={o} type="button" onClick={() => onAnswer(o)}
                  className="cursor-pointer rounded-full border border-brand-200 bg-white px-3.5 py-1.5 text-[13px] font-medium text-brand-700 shadow-sm transition-all hover:-translate-y-0.5 hover:border-brand-400 hover:bg-brand-50 dark:border-brand-800 dark:bg-zinc-900 dark:text-brand-300 dark:hover:bg-brand-950/40">
                  {o}
                </button>
              ))}
            </div>
          )}
        </div>
      )
    case 'answer':
      return (
        <Selectable selected={selected} onSelect={onSelect}>
          <Markdown>{r.answer ?? r.message}</Markdown>
        </Selectable>
      )
    default:
      return <SqlAnswer response={r} selected={selected} onSelect={onSelect} onAnswer={onAnswer} busy={busy} />
  }
}

function SqlAnswer({ response: r, selected, onSelect, onAnswer, busy }: {
  response: AgentResponse
  selected: boolean
  onSelect: () => void
  onAnswer: (text: string) => void
  busy?: boolean
}) {
  const results = r.results
  return (
    <Selectable selected={selected} onSelect={onSelect}>
      <div className="space-y-3.5">
        {r.intent === 'debug_sql' && r.debug && (
          <p className="flex items-center gap-1.5 text-[11px] font-semibold tracking-[0.14em] text-brand-600 uppercase dark:text-brand-300">
            <Wrench size={13} /> Found {plural(r.debug.issues.length, 'issue')} — corrected query
          </p>
        )}
        {r.intent === 'optimize_sql' && r.optimization && (
          <p className="flex items-center gap-1.5 text-[11px] font-semibold tracking-[0.14em] text-brand-600 uppercase dark:text-brand-300">
            <Zap size={13} /> {r.optimization.accepted ? 'Optimized — same results, verified' : 'Kept your query — rewrite rejected'}
          </p>
        )}
        <p className="text-[15px] leading-relaxed text-ink/90 dark:text-zinc-200">{r.explanation?.summary || r.message}</p>
        {r.sql && (
          <div className="relative overflow-hidden rounded-2xl border border-zinc-200/80 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between border-b border-zinc-100 px-4 py-2 dark:border-zinc-800">
              <span className="text-[10.5px] font-semibold tracking-[0.2em] text-zinc-400 uppercase">SQLite</span>
              <CopyButton text={r.sql} compact label="Copy SQL" successMessage="SQL copied" />
            </div>
            <SqlCode sql={r.sql} lineNumbers={false} maxLines={14} className="rounded-none border-0 bg-transparent dark:bg-transparent" />
          </div>
        )}
        <div className="flex flex-wrap items-center gap-1.5">
          {r.validation?.ok && <Badge tone="success" icon={<ShieldCheck size={11} />}>Validated · read-only</Badge>}
          {results && !results.error && (
            <Badge tone="neutral" icon={<Database size={11} />}>
              {results.truncated && results.total_rows
                ? `${results.row_count} of ${results.total_rows.toLocaleString()} rows`
                : plural(results.row_count, 'row')}
            </Badge>
          )}
          {results?.error && <Badge tone="danger">Execution failed</Badge>}
          {r.cost && <CostBadge level={r.cost.level} />}
          {(r.validation?.attempts ?? 0) > 1 && <Badge tone="brand" icon={<RefreshCw size={11} />}>Self-corrected</Badge>}
          {r.mappings.length > 0 && <Badge tone="info" icon={<Sparkles size={11} />}>{plural(r.mappings.length, 'value')} mapped</Badge>}
          <button type="button" onClick={onSelect}
            className="ml-auto inline-flex cursor-pointer items-center gap-1 text-[13px] font-medium text-brand-700 hover:underline dark:text-brand-300">
            View details <ArrowRight size={13} />
          </button>
        </div>
        <DiveDeeper suggestions={r.suggestions ?? []} onPick={onAnswer} disabled={busy} />
      </div>
    </Selectable>
  )
}

/** Answer block; the selected answer (shown in the details panel) carries a brand rule on its left. */
function Selectable({ children, selected, onSelect }: { children: ReactNode; selected: boolean; onSelect: () => void }) {
  return (
    <div
      onClick={onSelect}
      className={cn(
        'animate-fade-in cursor-pointer border-l-2 py-1 pl-4 transition-colors',
        selected ? 'border-brand-500' : 'border-transparent hover:border-zinc-200 dark:hover:border-zinc-700',
      )}
    >
      {children}
    </div>
  )
}

function Notice({ tone, icon, text, onRetry, onDetails }: {
  tone: 'warning' | 'danger'
  icon: ReactNode
  text: string
  onRetry?: () => void
  onDetails?: () => void
}) {
  return (
    <div className="animate-fade-in max-w-[640px] rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-start gap-3">
        <span className={cn('grid h-9 w-9 shrink-0 place-items-center rounded-full ring-1',
          tone === 'warning' ? 'bg-amber-50 text-amber-600 ring-amber-200 dark:bg-amber-950/40 dark:ring-amber-900'
            : 'bg-rose-50 text-rose-600 ring-rose-200 dark:bg-rose-950/40 dark:ring-rose-900')}>
          {icon}
        </span>
        <p className="pt-1.5 text-[14.5px] leading-relaxed text-zinc-700 dark:text-zinc-200">{text}</p>
      </div>
      {(onRetry || onDetails) && (
        <div className="mt-4 flex gap-2 pl-12">
          {onRetry && (
            <button type="button" onClick={onRetry}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-gradient-to-r from-brand-600 to-brand-800 px-3.5 py-2 text-[13px] font-semibold text-white shadow-sm hover:opacity-95">
              <RefreshCw size={13} /> Try again
            </button>
          )}
          {onDetails && (
            <button type="button" onClick={onDetails}
              className="cursor-pointer rounded-lg border border-zinc-200 px-3.5 py-2 text-[13px] font-medium text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800">
              Details
            </button>
          )}
        </div>
      )}
    </div>
  )
}
