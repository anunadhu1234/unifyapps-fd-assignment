import { Check, Pencil, Trash2 } from 'lucide-react'
import { useState, type KeyboardEvent, type MouseEvent } from 'react'
import type { ThreadSummary } from '../../api/types'
import { cn } from '../../lib/cn'
import { relativeTime } from '../../lib/format'
import { Modal } from '../ui/Modal'

const ROW_ICON = 'grid h-6 w-6 shrink-0 place-items-center rounded-md text-white/70 transition-colors hover:bg-white/20 hover:text-white'

/** One chat in the sidebar: accent bar when active, rename inline, delete with confirmation. */
export function ThreadItem({ thread, active, onOpen, onRename, onDelete }: {
  thread: ThreadSummary
  active: boolean
  onOpen: () => void
  onRename: (title: string) => void
  onDelete: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [title, setTitle] = useState(thread.title)

  const save = () => {
    const next = title.trim()
    if (next && next !== thread.title) onRename(next)
    setEditing(false)
  }
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') save()
    if (e.key === 'Escape') {
      setTitle(thread.title)
      setEditing(false)
    }
  }
  const stop = (fn: () => void) => (e: MouseEvent) => {
    e.stopPropagation()
    fn()
  }

  if (editing) {
    return (
      <div className="mx-2 flex items-center gap-1 rounded-lg bg-white/15 px-3 py-1.5 ring-1 ring-white/20">
        <input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} onKeyDown={onKey} onBlur={save}
          aria-label="Chat title" className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none" />
        <button type="button" aria-label="Save" className={ROW_ICON} onMouseDown={(e) => e.preventDefault()} onClick={save}>
          <Check size={13} />
        </button>
      </div>
    )
  }

  return (
    <>
      <div
        role="button"
        tabIndex={0}
        onClick={onOpen}
        onKeyDown={(e) => e.key === 'Enter' && onOpen()}
        className={cn(
          'group mx-2 flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm transition-all duration-200',
          active ? 'bg-white/15 text-white shadow-inner ring-1 ring-white/15' : 'text-white/80 hover:bg-white/10 hover:text-white',
        )}
      >
        <span className={cn('h-5 w-[3px] shrink-0 rounded-full transition-all duration-200',
          active ? 'bg-white/90' : 'bg-transparent group-hover:bg-white/40')} />
        <span className="min-w-0 flex-1">
          <span className="block truncate">{thread.title}</span>
          <span className="block text-[10.5px] text-white/45">{relativeTime(thread.updated_at)}</span>
        </span>
        <span className="flex shrink-0 items-center opacity-0 transition-opacity duration-200 group-focus-within:opacity-100 group-hover:opacity-100">
          <button type="button" aria-label="Rename chat" title="Rename" className={ROW_ICON} onClick={stop(() => setEditing(true))}>
            <Pencil size={12} />
          </button>
          <button type="button" aria-label="Delete chat" title="Delete" className={ROW_ICON} onClick={stop(() => setConfirming(true))}>
            <Trash2 size={12} />
          </button>
        </span>
      </div>

      <Modal
        open={confirming}
        onClose={() => setConfirming(false)}
        title="Delete this chat?"
        footer={
          <>
            <button type="button" onClick={() => setConfirming(false)}
              className="rounded-lg border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800">
              Cancel
            </button>
            <button type="button" onClick={() => { setConfirming(false); onDelete() }}
              className="inline-flex items-center gap-2 rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700">
              <Trash2 size={14} /> Delete chat
            </button>
          </>
        }
      >
        <p className="text-sm leading-relaxed text-zinc-600 dark:text-zinc-300">
          You're about to permanently remove
          <span className="mx-1 rounded-md bg-zinc-100 px-1.5 py-0.5 font-medium text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100">{thread.title}</span>
          and all of its messages. This can't be undone.
        </p>
      </Modal>
    </>
  )
}
