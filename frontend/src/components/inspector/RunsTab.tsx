import { History, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { RunHistory, ResponseType } from '../../api/types'
import { formatMs, relativeTime } from '../../lib/format'
import { INTENT_LABELS } from '../../lib/pipeline'
import { Badge, type Tone } from '../ui/Badge'
import { IconButton } from '../ui/IconButton'
import { EmptyHint } from '../ui/Section'
import { Spinner } from '../ui/Spinner'

const TYPE_TONE: Record<ResponseType, Tone> = {
  sql: 'success', answer: 'info', clarification: 'brand', refusal: 'warning', error: 'danger',
}

/** Developer run history: every question this developer ran, with tokens and timing. Click to reopen. */
export function RunsTab({ refreshKey, onOpenThread }: { refreshKey: number; onOpenThread?: (threadId: string) => void }) {
  const [data, setData] = useState<RunHistory | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await api.getRuns())
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load the run history.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  if (!data) {
    return error ? <EmptyHint title="Run history unavailable">{error}</EmptyHint>
      : <div className="flex justify-center py-12 text-brand-500"><Spinner /></div>
  }
  if (!data.runs.length) {
    return <EmptyHint icon={<History size={28} />} title="No runs yet">Every question you ask appears here with its tokens and timing.</EmptyHint>
  }

  const s = data.summary
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="grid flex-1 grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Runs" value={String(s.runs)} />
          <Stat label="Input tokens" value={s.input_tokens.toLocaleString()} />
          <Stat label="Output tokens" value={s.output_tokens.toLocaleString()} />
          <Stat label="Avg time" value={formatMs(s.avg_pipeline_ms)} />
        </div>
        <IconButton label="Refresh" size="sm" className="ml-2" icon={loading ? <Spinner className="h-3.5 w-3.5" /> : <RefreshCw size={14} />} onClick={() => void load()} />
      </div>

      <div className="overflow-x-auto scrollbar-thin rounded-lg border border-zinc-200 dark:border-zinc-800">
        <table className="w-full text-xs">
          <thead className="bg-zinc-50 text-zinc-500 dark:bg-zinc-900">
            <tr>
              <th className="px-2.5 py-2 text-left font-medium">Question</th>
              <th className="px-2.5 py-2 text-right font-medium">Calls</th>
              <th className="px-2.5 py-2 text-right font-medium">In tok</th>
              <th className="px-2.5 py-2 text-right font-medium">Out tok</th>
              <th className="px-2.5 py-2 text-right font-medium">Time</th>
            </tr>
          </thead>
          <tbody>
            {data.runs.map((r) => (
              <tr key={r.request_id} onClick={() => onOpenThread?.(r.thread_id)} title={`${r.question}\n(in chat: ${r.thread_title})`}
                className="cursor-pointer border-t border-zinc-100 align-top hover:bg-brand-50/50 dark:border-zinc-800 dark:hover:bg-brand-950/20">
                <td className="w-full min-w-[180px] px-2.5 py-2">
                  <p className="line-clamp-2 font-medium text-zinc-800 dark:text-zinc-200">{r.question}</p>
                  <p className="mt-1 flex flex-wrap items-center gap-1 text-[10.5px] text-zinc-400">
                    {r.type && <Badge tone={TYPE_TONE[r.type]}>{r.type}</Badge>}
                    {r.intent && <span>{INTENT_LABELS[r.intent] ?? r.intent}</span>}
                    {r.rows !== null && <span>· {r.rows.toLocaleString()} rows</span>}
                    {(r.attempts ?? 0) > 1 && <span>· {r.attempts} attempts</span>}
                    <span>· {relativeTime(r.created_at)}</span>
                  </p>
                </td>
                <td className="px-2.5 py-2 text-right tabular-nums">{r.llm_calls}</td>
                <td className="px-2.5 py-2 text-right tabular-nums">{r.input_tokens.toLocaleString()}</td>
                <td className="px-2.5 py-2 text-right tabular-nums">{r.output_tokens.toLocaleString()}</td>
                <td className="px-2.5 py-2 text-right whitespace-nowrap tabular-nums" title={`LLM time ${formatMs(r.llm_ms)}`}>{formatMs(r.pipeline_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2 dark:border-zinc-800">
      <p className="text-[11px] text-zinc-500">{label}</p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums">{value}</p>
    </div>
  )
}
