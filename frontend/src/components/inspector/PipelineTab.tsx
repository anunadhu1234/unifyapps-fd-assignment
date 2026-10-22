import { Check, GitBranch, X } from 'lucide-react'
import type { AgentResponse } from '../../api/types'
import { formatMs } from '../../lib/format'
import { INTENT_LABELS, stepLabel } from '../../lib/pipeline'
import type { PipelineStep } from '../../types/chat'
import { Badge } from '../ui/Badge'
import { EmptyHint, Section } from '../ui/Section'

/** The LangGraph nodes this answer went through, with timings. */
export function PipelineTab({ steps, response }: { steps: PipelineStep[]; response?: AgentResponse }) {
  const shown = steps.filter((s) => s.node !== 'receive_request')
  if (!shown.length) return <EmptyHint icon={<GitBranch size={28} />} title="No pipeline steps recorded" />
  const total = shown.reduce((sum, s) => sum + (s.ms ?? 0), 0)
  const slowest = Math.max(...shown.map((s) => s.ms ?? 0), 1)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        {response?.intent && <Badge tone="brand">{INTENT_LABELS[response.intent] ?? response.intent}</Badge>}
        <Badge tone="neutral">{shown.length} steps</Badge>
        {total > 0 && <Badge tone="neutral">{formatMs(total)} total</Badge>}
      </div>
      <Section title="LangGraph workflow">
        <ol className="relative space-y-0.5">
          {shown.map((s, i) => (
            <li key={`${s.node}-${i}`} className="grid grid-cols-[18px_1fr_auto] items-center gap-2.5 py-1.5">
              <span
                className={
                  s.ok
                    ? 'flex h-[18px] w-[18px] items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                    : 'flex h-[18px] w-[18px] items-center justify-center rounded-full bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
                }
              >
                {s.ok ? <Check size={11} /> : <X size={11} />}
              </span>
              <div className="min-w-0">
                <p className="text-sm text-zinc-800 dark:text-zinc-200">{stepLabel(s.node)}</p>
                <div className="mt-1 h-1 rounded-full bg-zinc-100 dark:bg-zinc-800">
                  <div
                    className="h-1 rounded-full bg-brand-400/70"
                    style={{ width: `${Math.max(2, ((s.ms ?? 0) / slowest) * 100)}%` }}
                  />
                </div>
              </div>
              <span className="font-mono text-[11px] text-zinc-400 tabular-nums">{formatMs(s.ms)}</span>
            </li>
          ))}
        </ol>
      </Section>
      <p className="text-xs text-zinc-500 dark:text-zinc-400">
        <code className="font-mono">{shown.map((s) => s.node).join(' → ')}</code>
      </p>
    </div>
  )
}
