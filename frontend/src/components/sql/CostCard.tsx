import { Gauge, Lightbulb } from 'lucide-react'
import type { CostEstimate, CostLevel, IndexRecommendation } from '../../api/types'
import { Badge, type Tone } from '../ui/Badge'
import { CopyButton } from '../ui/CopyButton'

const LEVEL_TONE: Record<CostLevel, Tone> = { low: 'success', medium: 'warning', high: 'danger' }

export function CostBadge({ level }: { level: CostLevel }) {
  return (
    <Badge tone={LEVEL_TONE[level]} icon={<Gauge size={11} />}>
      {level} cost
    </Badge>
  )
}

/** Query cost estimate from SQLite's plan, plus index recommendations. */
export function CostCard({ cost, recommendations }: { cost: CostEstimate; recommendations?: IndexRecommendation[] }) {
  const recs = recommendations ?? cost.recommendations
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <CostBadge level={cost.level} />
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          Relative score {cost.score.toLocaleString()} · {cost.full_scans.length} full scan
          {cost.full_scans.length === 1 ? '' : 's'} · {cost.index_lookups.length} index lookup
          {cost.index_lookups.length === 1 ? '' : 's'}
        </span>
      </div>
      <ol className="space-y-1 border-l-2 border-zinc-200 pl-3 text-xs text-zinc-600 dark:border-zinc-800 dark:text-zinc-400">
        {cost.plan.map((step, i) => (
          <li key={i}>{step}</li>
        ))}
      </ol>
      {recs.length > 0 && <IndexRecommendations recommendations={recs} />}
    </div>
  )
}

export function IndexRecommendations({ recommendations }: { recommendations: IndexRecommendation[] }) {
  return (
    <div className="space-y-2">
      <p className="flex items-center gap-1.5 text-xs font-medium text-zinc-700 dark:text-zinc-300">
        <Lightbulb size={13} className="text-amber-500" /> Recommended indexes (advice only — never executed)
      </p>
      {recommendations.map((r) => (
        <div key={r.ddl} className="rounded-lg border border-zinc-200 p-2.5 dark:border-zinc-800">
          <div className="flex items-start justify-between gap-2">
            <code className="font-mono text-xs break-all text-brand-700 dark:text-brand-300">{r.ddl}</code>
            <CopyButton text={r.ddl} compact label="Copy index DDL" />
          </div>
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{r.reason}</p>
        </div>
      ))}
    </div>
  )
}
