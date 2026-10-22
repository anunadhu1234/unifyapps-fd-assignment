import { ArrowUpRight } from 'lucide-react'
import { useState } from 'react'
import type { SchemaSummary } from '../../api/types'
import { useAuth } from '../../context/AuthContext'

// Data-voiced greetings — picked once per visit, never re-rolled on re-render.
const GREETINGS = [
  'Which numbers shall we pull today?',
  'Ask your data anything.',
  'Let’s turn questions into SQL.',
  'Ready when you are — what do you need to know?',
  'Good to see you! What shall we query?',
  'Your data, in plain English.',
]

export function EmptyState({ schema, onPick }: { schema: SchemaSummary | null; onPick: (q: string) => void }) {
  const { user } = useAuth()
  const [greeting] = useState(() => GREETINGS[Math.floor(Math.random() * GREETINGS.length)])
  const firstName = user?.display_name.split(' ')[0]

  return (
    <div className="flex min-h-full flex-col items-center justify-center px-6 py-10">
      <div className="animate-fade-up w-full max-w-2xl text-center">
        <div className="mb-4 flex items-center justify-center gap-3">
          <span className="h-px w-10 bg-gradient-to-r from-transparent to-brand-600/45" />
          <span className="text-[11px] font-semibold tracking-[0.24em] text-brand-600/85 uppercase dark:text-brand-300">
            SQL Query Agent{firstName ? ` · Hi ${firstName}` : ''}
          </span>
          <span className="h-px w-10 bg-gradient-to-l from-transparent to-brand-600/45" />
        </div>
        <h1 className="bg-gradient-to-b from-brand-600 to-brand-800 bg-clip-text pb-2 text-[34px] leading-[1.12] font-semibold tracking-tight text-transparent sm:text-[38px] dark:from-brand-300 dark:to-brand-500">
          {greeting}
        </h1>
        <p className="mt-4 text-[15px] leading-relaxed font-light text-zinc-500 dark:text-zinc-400">
          Ask about customers, orders, products and employees — I’ll plan, validate and explain the SQL. Paste a query to
          optimize, debug or explain it.
        </p>
      </div>

      {schema && (
        <div className="animate-fade-up mt-9 grid w-full max-w-2xl grid-cols-1 gap-2.5 sm:grid-cols-2" style={{ animationDelay: '120ms' }}>
          {schema.suggested_questions.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => onPick(q)}
              className="group flex cursor-pointer items-start justify-between gap-3 rounded-2xl border border-zinc-200/80 bg-white/80 px-4 py-3 text-left text-[13.5px] text-zinc-600 shadow-sm backdrop-blur transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-300 hover:text-brand-800 hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-zinc-300 dark:hover:border-brand-700 dark:hover:text-brand-200"
            >
              <span>{q}</span>
              <ArrowUpRight size={15} className="mt-0.5 shrink-0 text-zinc-300 transition-colors group-hover:text-brand-600" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
