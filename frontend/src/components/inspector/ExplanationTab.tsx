import { BookOpen } from 'lucide-react'
import type { AgentResponse } from '../../api/types'
import { EmptyHint } from '../ui/Section'
import { Markdown } from '../ui/Markdown'

export function ExplanationTab({ response: r }: { response: AgentResponse }) {
  const e = r.explanation
  if (!e) return <EmptyHint icon={<BookOpen size={28} />} title="No explanation for this answer" />
  return (
    <div className="space-y-5">
      <p className="text-base leading-relaxed font-medium text-zinc-900 dark:text-zinc-100">{e.summary}</p>
      {e.steps.length > 0 && (
        <ol className="space-y-3">
          {e.steps.map((step, i) => (
            <li key={i} className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-700 dark:bg-brand-950 dark:text-brand-300">
                {i + 1}
              </span>
              <Markdown className="pt-0.5">{step}</Markdown>
            </li>
          ))}
        </ol>
      )}
      {r.assumptions.length > 0 && (
        <div className="rounded-lg bg-zinc-50 p-3 dark:bg-zinc-900">
          <p className="mb-1.5 text-xs font-semibold text-zinc-600 dark:text-zinc-400">Assumptions</p>
          <ul className="list-disc space-y-1 pl-4 text-xs text-zinc-600 dark:text-zinc-400">
            {r.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
