import { Cpu, FileText, Network, Route } from 'lucide-react'
import { useState } from 'react'
import { api } from '../../api/client'
import type { DevInfo } from '../../api/types'
import { formatCost, formatMs } from '../../lib/format'
import { PromptsDialog } from '../dev/PromptsDialog'
import { SqlCode } from '../sql/SqlCode'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Collapsible, EmptyHint, JsonView, Section } from '../ui/Section'

/** Internals for developers: routing, LLM calls, intent, retrieval, plan, validation attempts, trace. */
export function DevTab({ dev }: { dev?: DevInfo }) {
  const [showPrompts, setShowPrompts] = useState(false)
  if (!dev) {
    return <EmptyHint icon={<Cpu size={28} />} title="No developer data">This answer was produced before dev mode was enabled.</EmptyHint>
  }
  const t = dev.totals
  const intent = (dev.intent ?? {}) as Record<string, unknown>
  const retrieval = (dev.retrieval ?? {}) as Record<string, unknown>

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2">
        <Button size="sm" icon={<FileText size={14} />} onClick={() => setShowPrompts(true)}>
          Prompts
        </Button>
        <a href={api.schemaGraphUrl} target="_blank" rel="noreferrer">
          <Button size="sm" icon={<Network size={14} />}>Knowledge graph</Button>
        </a>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="LLM calls" value={String(t.llm_calls)} />
        <Stat label="Tokens in → out" value={`${(t.input_tokens / 1000).toFixed(1)}k → ${(t.output_tokens / 1000).toFixed(1)}k`} />
        <Stat label="LLM cost" value={formatCost(t.cost_usd)} />
        <Stat label="Pipeline time" value={formatMs(t.pipeline_ms)} />
      </div>

      <Section title="Model routing & LLM calls" icon={<Route size={13} />}>
        <ul className="divide-y divide-zinc-100 rounded-lg border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
          {dev.llm_calls.map((c, i) => {
            const fallback = c.served_by && c.served_by !== c.model
            return (
              <li key={i} className="space-y-1 px-3 py-2.5 text-xs">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-semibold text-zinc-800 dark:text-zinc-200">{c.step}</span>
                  <Badge tone={c.tier === 'fast' ? 'info' : c.tier === 'main' ? 'brand' : 'neutral'}>{c.tier}</Badge>
                  {!c.ok && <Badge tone="danger">failed</Badge>}
                  {c.retried && <Badge tone="warning">retried</Badge>}
                  {fallback && <Badge tone="warning">fallback</Badge>}
                  <span className="ml-auto text-zinc-500 tabular-nums">
                    {formatMs(c.ms)} · {(c.input_tokens ?? 0).toLocaleString()} → {(c.output_tokens ?? 0).toLocaleString()} tok · {formatCost(c.cost_usd)}
                  </span>
                </div>
                <p className="font-mono text-[11px] break-all text-zinc-600 dark:text-zinc-400">
                  {c.served_by ?? c.model}
                  {fallback && <span className="text-zinc-400"> (requested {c.model})</span>}
                </p>
                <p className="text-zinc-500">{c.route_reason}</p>
                {c.error && <p className="text-rose-600 dark:text-rose-400">{c.error}</p>}
              </li>
            )
          })}
        </ul>
      </Section>

      <Section title="Intent">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
          <dt className="text-zinc-500">Intent</dt>
          <dd className="font-medium">{String(intent.intent ?? '–')}</dd>
          <dt className="text-zinc-500">Understood as</dt>
          <dd>{dev.standalone_question ?? '–'}</dd>
          <dt className="text-zinc-500">Reason</dt>
          <dd className="text-zinc-600 dark:text-zinc-400">{String(intent.reason ?? '–')}</dd>
        </dl>
      </Section>

      {dev.retrieval && (
        <Section title="Schema retrieval (swarm)">
          <div className="flex flex-wrap gap-1.5">
            {((retrieval.tables as string[]) ?? []).map((tb) => <Badge key={tb} tone="brand">{tb}</Badge>)}
            {((retrieval.metrics as string[]) ?? []).map((m) => <Badge key={m} tone="warning">metric: {m}</Badge>)}
            {((retrieval.glossary as string[]) ?? []).map((g) => <Badge key={g} tone="info">term: {g}</Badge>)}
          </div>
          <Collapsible title="Schema context sent to the model">
            <pre className="max-h-96 overflow-auto scrollbar-thin font-mono text-[11px] whitespace-pre-wrap text-zinc-600 dark:text-zinc-400">
              {String(retrieval.schema_context ?? '')}
            </pre>
          </Collapsible>
          <Collapsible title="Full retrieval output"><JsonView value={{ ...retrieval, schema_context: undefined }} /></Collapsible>
        </Section>
      )}

      {(dev.plan || dev.grounded_plan) && (
        <Section title="Planner">
          {dev.plan && <Collapsible title="Query plan (LLM)"><JsonView value={dev.plan} /></Collapsible>}
          {dev.grounded_plan && <Collapsible title="Grounded plan (deterministic)"><JsonView value={dev.grounded_plan} /></Collapsible>}
        </Section>
      )}

      {!!dev.validation_history?.length && (
        <Section title="Validation attempts">
          {dev.validation_history.map((a) => (
            <Collapsible
              key={a.attempt + a.origin}
              title={`Attempt ${a.attempt} · ${a.origin}`}
              meta={<Badge tone={a.ok ? 'success' : 'danger'}>{a.ok ? 'passed' : `${a.findings.filter((f) => f.severity === 'error').length} errors`}</Badge>}
              defaultOpen={!a.ok}
            >
              <SqlCode sql={a.sql} lineNumbers={false} />
              {a.findings.map((f, i) => (
                <p key={i} className="mt-2 text-xs">
                  <code className="font-mono text-rose-600 dark:text-rose-400">{f.code}</code> {f.message}
                  {f.hint && <span className="text-zinc-500"> — {f.hint}</span>}
                </p>
              ))}
            </Collapsible>
          ))}
        </Section>
      )}

      {dev.failure && (
        <Section title="Failure"><JsonView value={dev.failure} /></Section>
      )}

      <Section title="Node trace">
        <Collapsible title={`${dev.trace.length} trace events`}><JsonView value={dev.trace} /></Collapsible>
      </Section>

      <Section title="LLM usage by stage">
        <UsageTable dev={dev} />
      </Section>

      <PromptsDialog open={showPrompts} onClose={() => setShowPrompts(false)} />
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


/** Input tokens, output tokens and time for every LLM stage of this answer, with totals. */
function UsageTable({ dev }: { dev: DevInfo }) {
  const t = dev.totals
  const cell = 'px-2.5 py-1.5 text-right tabular-nums whitespace-nowrap'
  if (!dev.llm_calls.length) return <p className="text-xs text-zinc-500">No LLM calls were needed for this answer.</p>
  return (
    <div className="overflow-x-auto scrollbar-thin rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-xs">
        <thead className="bg-zinc-50 text-zinc-500 dark:bg-zinc-900">
          <tr>
            <th className="px-2.5 py-2 text-left font-medium">Stage</th>
            <th className="px-2.5 py-2 text-right font-medium">Input tokens</th>
            <th className="px-2.5 py-2 text-right font-medium">Output tokens</th>
            <th className="px-2.5 py-2 text-right font-medium">Time</th>
          </tr>
        </thead>
        <tbody>
          {dev.llm_calls.map((c, i) => (
            <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
              <td className="px-2.5 py-1.5">
                <span className="font-medium text-zinc-800 dark:text-zinc-200">{c.step}</span>
                <span className="block max-w-[200px] truncate font-mono text-[10px] text-zinc-400" title={c.served_by ?? c.model}>{c.served_by ?? c.model}</span>
              </td>
              <td className={cell}>{(c.input_tokens ?? 0).toLocaleString()}</td>
              <td className={cell}>{(c.output_tokens ?? 0).toLocaleString()}</td>
              <td className={cell}>{formatMs(c.ms)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot className="border-t-2 border-zinc-200 bg-zinc-50 font-semibold dark:border-zinc-700 dark:bg-zinc-900">
          <tr>
            <td className="px-2.5 py-2">Total ({t.llm_calls} LLM calls)</td>
            <td className={cell}>{t.input_tokens.toLocaleString()}</td>
            <td className={cell}>{t.output_tokens.toLocaleString()}</td>
            <td className={cell}>{formatMs(t.llm_ms)}</td>
          </tr>
          <tr className="text-zinc-500">
            <td className="px-2.5 py-1.5 font-normal" colSpan={3}>End-to-end pipeline time (all nodes; parallel LLM calls overlap)</td>
            <td className={cell}>{formatMs(t.pipeline_ms)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
