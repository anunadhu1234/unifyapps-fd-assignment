import { useEffect, useState } from 'react'
import type { PipelineStep } from '../../types/chat'

// What the pipeline is doing after each finished node, phrased the way the
// workspace's loading captions are. Each stage rotates through a few phrasings.
const NEXT_STAGE: Record<string, string> = {
  start: 'understanding',
  receive_request: 'understanding',
  intent_detection: 'scope',
  scope_validation: 'retrieval',
  schema_retrieval: 'planning',
  query_planner: 'grounding',
  plan_grounding: 'writing',
  sql_generation: 'validating',
  sql_repair: 'validating',
  sql_debugging: 'validating',
  sql_optimization: 'running',
  execute_query: 'explaining',
  ask_clarification: 'finishing',
  schema_answer: 'finishing',
  generate_explanation: 'finishing',
  suggest_follow_ups: 'finishing',
}

const PHRASES: Record<string, string[]> = {
  understanding: ['Understanding your request…', 'Reading your question…', 'Thinking…'],
  scope: ['Checking the request is in scope…', 'Making sure this is a database question…'],
  retrieval: ['Finding the relevant tables…', 'Looking through the schema…', 'Gathering relevant columns…'],
  planning: ['Planning the query…', 'Working out the joins and filters…', 'Reasoning through your request…'],
  grounding: ['Matching names to the real schema…', 'Mapping values to what is stored…'],
  writing: ['Writing the SQL…', 'Composing your query…', 'Putting the query together…'],
  validating: ['Validating the SQL…', 'Checking tables, columns and joins…', 'Making sure it is read-only…'],
  repairing: ['Fixing an issue the validator found…', 'Self-correcting the query…'],
  running: ['Optimizing and estimating cost…', 'Running the query…'],
  explaining: ['Explaining the query…', 'Writing it up in plain English…'],
  finishing: ['Almost there…', 'Getting your answer ready…'],
}

function stageOf(steps: PipelineStep[]): string {
  const last = steps[steps.length - 1]
  if (!last) return 'understanding'
  if (last.node === 'sql_validation') return last.detail?.ok === false ? 'repairing' : 'running'
  return NEXT_STAGE[last.node] ?? 'finishing'
}

/** The waiting state: a pulsing dot, a shimmering stage-aware caption, and what the agent found so far. */
export function StreamingProgress({ steps, text }: { steps: PipelineStep[]; text: string }) {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setTick((t) => t + 1), 2000)
    return () => clearInterval(timer)
  }, [])

  const stage = stageOf(steps)
  const phrases = PHRASES[stage]
  const tables = steps.find((s) => s.node === 'schema_retrieval')?.detail?.tables as string[] | undefined

  if (text) {
    // Explanation tokens are streaming in: show them as they arrive.
    return <p className="text-[15px] leading-relaxed whitespace-pre-wrap text-ink/90 dark:text-zinc-200">{text}</p>
  }

  return (
    <div className="flex flex-wrap items-center gap-3 py-1">
      <span className="inline-block h-2 w-2 shrink-0 animate-pulse rounded-full bg-brand-600 dark:bg-brand-400" />
      <span key={`${stage}-${tick % phrases.length}`} className="animate-shine inline-block text-[15px]">
        {phrases[tick % phrases.length]}
      </span>
      {tables && tables.length > 0 && stage !== 'understanding' && stage !== 'scope' && (
        <span className="flex flex-wrap items-center gap-1.5">
          <span className="text-sm text-zinc-500 dark:text-zinc-400">using</span>
          {tables.map((t) => (
            <span key={t} className="rounded-md border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-[13px] font-medium tracking-wide text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200">
              {t}
            </span>
          ))}
        </span>
      )}
    </div>
  )
}
