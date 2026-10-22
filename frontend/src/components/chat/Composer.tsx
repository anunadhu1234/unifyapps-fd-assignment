import { ArrowUp, Square } from 'lucide-react'
import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { cn } from '../../lib/cn'

const MAX_CHARS = 2000

/** Gradient pill input: Enter sends, Shift+Enter adds a line (pasted SQL grows the pill). */
export function Composer({ onSend, onStop, busy, autoFocus }: {
  onSend: (text: string) => void
  onStop: () => void
  busy: boolean
  autoFocus?: boolean
}) {
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)
  const multiline = text.includes('\n') || text.length > 90

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [text])

  useEffect(() => {
    if (autoFocus) ref.current?.focus()
  }, [autoFocus])

  const submit = () => {
    if (busy || !text.trim() || text.length > MAX_CHARS) return
    onSend(text)
    setText('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  const tooLong = text.length > MAX_CHARS
  return (
    <div className="mx-auto w-full max-w-3xl">
      <div
        className={cn(
          'bg-brand-pill group relative flex items-end gap-1.5 py-2.5 pr-2.5 pl-6 text-white ring-1 ring-white/10 transition-all duration-300',
          'shadow-[inset_0_1px_0_rgba(255,255,255,0.22),0_18px_44px_-18px_rgba(79,70,229,0.55)]',
          'focus-within:shadow-[inset_0_1px_0_rgba(255,255,255,0.28),0_24px_56px_-16px_rgba(79,70,229,0.72)] focus-within:ring-white/30',
          multiline ? 'rounded-[28px]' : 'rounded-full',
          tooLong && 'ring-2 ring-rose-300',
        )}
      >
        <textarea
          ref={ref}
          rows={1}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about your data, or paste SQL to optimize / debug…"
          aria-label="Message"
          className="max-h-52 min-h-[44px] flex-1 resize-none bg-transparent py-[11px] text-[16px] tracking-tight text-white caret-white outline-none placeholder:text-white/55"
        />
        {busy ? (
          <button
            type="button"
            onClick={onStop}
            aria-label="Stop generating"
            title="Stop"
            className="grid h-11 w-11 shrink-0 cursor-pointer place-items-center rounded-full bg-white/15 text-white shadow-sm ring-1 ring-white/20 transition-all duration-200 hover:scale-105 hover:bg-white/25 active:scale-95"
          >
            <Square size={14} fill="currentColor" />
          </button>
        ) : (
          <button
            type="button"
            onClick={submit}
            disabled={!text.trim() || tooLong}
            aria-label="Send message"
            title="Send (Enter)"
            className="grid h-11 w-11 shrink-0 cursor-pointer place-items-center rounded-full bg-white/15 text-white shadow-sm ring-1 ring-white/20 transition-all duration-200 hover:scale-105 hover:bg-white/25 active:scale-95 disabled:cursor-default disabled:hover:scale-100"
          >
            <ArrowUp size={19} className={text.trim() ? 'opacity-100' : 'opacity-45'} />
          </button>
        )}
      </div>
      <div className="mt-2 flex justify-between px-6 text-[11px] text-zinc-400">
        <span>Read-only · every query is validated against the schema before it runs</span>
        {text.length > MAX_CHARS * 0.8 && (
          <span className={tooLong ? 'text-rose-500' : ''}>
            {text.length}/{MAX_CHARS}
          </span>
        )}
      </div>
    </div>
  )
}
