import { ArrowRight, GitBranch, Plus, SlidersHorizontal } from 'lucide-react'
import type { FollowUpSuggestion } from '../../api/types'

const KIND_ICON = {
  drill_down: <GitBranch size={13} />,
  refine: <SlidersHorizontal size={13} />,
  related: <Plus size={13} />,
}

const KIND_LABEL = { drill_down: 'Break down', refine: 'Refine', related: 'Related' }

/** "Dive deeper": three grounded follow-up questions; clicking one continues the conversation. */
export function DiveDeeper({ suggestions, onPick, disabled }: {
  suggestions: FollowUpSuggestion[]
  onPick: (question: string) => void
  disabled?: boolean
}) {
  if (!suggestions.length) return null
  return (
    <div className="mt-6 max-w-[620px] border-t border-zinc-900/[0.07] pt-5 dark:border-white/10" onClick={(e) => e.stopPropagation()}>
      <div className="mb-3.5 flex items-center gap-2.5">
        <span className="h-[3px] w-5 rounded-full bg-gradient-to-br from-brand-600 to-brand-800" />
        <span className="text-[11px] font-bold tracking-[0.09em] text-brand-700 uppercase dark:text-brand-300">Dive deeper</span>
      </div>
      <div className="flex flex-col gap-2.5">
        {suggestions.slice(0, 3).map((s) => (
          <button
            key={s.question}
            type="button"
            disabled={disabled}
            onClick={() => onPick(s.question)}
            className="group flex w-full cursor-pointer items-center justify-between gap-3.5 rounded-[14px] border border-brand-600/[0.18] bg-white px-[18px] py-3.5 text-left text-[13.5px] leading-snug font-medium text-ink shadow-[0_1px_3px_rgba(16,24,40,0.05)] transition-all duration-200 hover:-translate-y-0.5 hover:border-transparent hover:bg-gradient-to-br hover:from-brand-600 hover:to-brand-800 hover:text-white hover:shadow-[0_10px_24px_rgba(79,70,229,0.30)] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0 disabled:hover:bg-none disabled:hover:text-ink dark:border-white/10 dark:bg-zinc-900 dark:text-zinc-100"
          >
            <span className="flex items-center gap-2.5">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-brand-50 text-brand-700 transition-colors group-hover:bg-white/15 group-hover:text-white dark:bg-brand-950 dark:text-brand-300" title={KIND_LABEL[s.kind]}>
                {KIND_ICON[s.kind]}
              </span>
              {s.question}
            </span>
            <ArrowRight size={16} className="shrink-0 text-brand-600 transition-transform duration-200 group-hover:translate-x-[3px] group-hover:text-white" />
          </button>
        ))}
      </div>
    </div>
  )
}
