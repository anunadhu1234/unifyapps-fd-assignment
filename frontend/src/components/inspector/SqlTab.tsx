import { ArrowRight, Download, ListChecks, Sparkles, Wrench, Zap } from 'lucide-react'
import { useState } from 'react'
import type { AgentResponse } from '../../api/types'
import { downloadText, slugify } from '../../lib/download'
import { CostBadge, CostCard } from '../sql/CostCard'
import { SqlCode } from '../sql/SqlCode'
import { ValidationChecklist } from '../sql/ValidationChecklist'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { CopyButton } from '../ui/CopyButton'
import { Collapsible, Section } from '../ui/Section'
import { Segmented } from '../ui/Tabs'

const DIALECT_LABELS: Record<string, string> = { sqlite: 'SQLite', postgres: 'PostgreSQL', mysql: 'MySQL' }

export function SqlTab({ response: r }: { response: AgentResponse }) {
  const dialects = r.dialects ?? (r.sql ? { sqlite: r.sql } : {})
  const [dialect, setDialect] = useState('sqlite')
  const sql = dialects[dialect] ?? r.sql ?? ''
  const opt = r.optimization?.mode === 'user' ? r.optimization : null

  return (
    <div className="space-y-6">
      <Section
        title="Query"
        actions={
          <>
            <CopyButton text={sql} label="Copy" successMessage="SQL copied" />
            <Button
              size="sm"
              icon={<Download size={14} />}
              onClick={() => downloadText(`${sql};\n`, `${slugify(r.message)}.${dialect === 'sqlite' ? 'sql' : `${dialect}.sql`}`)}
            >
              .sql
            </Button>
          </>
        }
      >
        {Object.keys(dialects).length > 1 && (
          <div className="flex items-center gap-2">
            <Segmented
              items={Object.keys(dialects).map((d) => ({ id: d, label: DIALECT_LABELS[d] ?? d }))}
              value={dialect}
              onChange={setDialect}
            />
            {dialect !== 'sqlite' && (
              <span className="text-[11px] text-zinc-400">Converted for portability — executed in SQLite</span>
            )}
          </div>
        )}
        <SqlCode sql={sql} />
      </Section>

      {opt && (
        <Section title="Optimization" icon={<Zap size={13} />}>
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              {opt.accepted ? (
                <Badge tone="success">Rewrite accepted — returns identical results</Badge>
              ) : (
                <Badge tone="warning">Rewrite rejected — original kept</Badge>
              )}
              {opt.cost_before && opt.cost_after && (
                <span className="inline-flex items-center gap-1.5 text-xs text-zinc-500">
                  <CostBadge level={opt.cost_before.level} /> <ArrowRight size={12} /> <CostBadge level={opt.cost_after.level} />
                  <span className="tabular-nums">
                    ({opt.cost_before.score.toLocaleString()} → {opt.cost_after.score.toLocaleString()})
                  </span>
                </span>
              )}
            </div>
            {opt.summary && <p className="text-sm text-zinc-700 dark:text-zinc-300">{opt.summary}</p>}
            {opt.rejected_reason && <p className="text-xs text-amber-700 dark:text-amber-300">Reason: {opt.rejected_reason}</p>}
            {!!opt.changes?.length && (
              <ul className="space-y-1.5">
                {opt.changes.map((c, i) => (
                  <li key={i} className="text-sm">
                    <span className="font-medium text-zinc-800 dark:text-zinc-200">{c.change}</span>
                    <span className="text-zinc-500 dark:text-zinc-400"> — {c.reason}</span>
                  </li>
                ))}
              </ul>
            )}
            {opt.original_sql && (
              <Collapsible title="Your original query">
                <SqlCode sql={opt.original_sql} />
              </Collapsible>
            )}
          </div>
        </Section>
      )}

      {r.debug && (
        <Section title="Issues found" icon={<Wrench size={13} />}>
          {r.debug.issues.length === 0 ? (
            <p className="text-sm text-zinc-600 dark:text-zinc-400">No problems found — the query is correct.</p>
          ) : (
            <ol className="space-y-2">
              {r.debug.issues.map((issue, i) => (
                <li key={i} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
                  <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                    {i + 1}. {issue.problem}
                  </p>
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{issue.why_incorrect}</p>
                </li>
              ))}
            </ol>
          )}
          <Collapsible title="Your original query">
            <SqlCode sql={r.debug.original_sql} />
          </Collapsible>
        </Section>
      )}

      {r.validation && (
        <Section title="Validation" icon={<ListChecks size={13} />}>
          <ValidationChecklist validation={r.validation} />
        </Section>
      )}

      {(r.mappings.length > 0 || r.assumptions.length > 0) && (
        <Section title="How your request was interpreted" icon={<Sparkles size={13} />}>
          <ul className="space-y-1.5 text-sm text-zinc-700 dark:text-zinc-300">
            {r.mappings.map((m) => (
              <li key={m} className="flex items-start gap-2">
                <Badge tone="info" className="mt-0.5 shrink-0">value</Badge>
                <span className="font-mono text-xs leading-5">{m}</span>
              </li>
            ))}
            {r.assumptions.map((a) => (
              <li key={a} className="flex items-start gap-2">
                <Badge tone="neutral" className="mt-0.5 shrink-0">assumption</Badge>
                <span className="text-xs leading-5">{a}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {r.cost && (
        <Section title="Cost estimate">
          <CostCard cost={r.cost} recommendations={opt ? opt.index_recommendations : undefined} />
        </Section>
      )}
    </div>
  )
}
