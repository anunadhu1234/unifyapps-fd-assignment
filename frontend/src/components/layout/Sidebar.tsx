import { Database, FileText, Network, SquarePen, TableProperties } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { api } from '../../api/client'
import type { ThreadSummary } from '../../api/types'
import { useAuth } from '../../context/AuthContext'
import { PromptsDialog } from '../dev/PromptsDialog'
import { Spinner } from '../ui/Spinner'
import { ThreadItem } from './ThreadItem'

interface Props {
  threads: ThreadSummary[]
  loading: boolean
  activeThreadId: string | null
  onNewChat: () => void
  onOpenThread: (id: string) => void
  onRenameThread: (id: string, title: string) => void
  onDeleteThread: (id: string) => void
  onOpenSchema: () => void
}

/** Brand-gradient workspace rail: product mark, new chat, tools, and the chat history. */
export function Sidebar(props: Props) {
  const { isDev } = useAuth()
  const [prompts, setPrompts] = useState(false)

  return (
    <nav
      aria-label="Chats"
      className="bg-brand-panel flex h-full w-full flex-col overflow-hidden text-white"
      style={{ boxShadow: 'inset -1px 0 0 rgba(255,255,255,0.07), 24px 0 64px -28px rgba(30,27,75,0.6)' }}
    >
      <div className="flex items-center gap-3 border-b border-white/10 px-5 py-5">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-white/10 shadow-inner ring-1 shadow-black/10 ring-white/15">
          <Database size={20} />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-[15px] font-semibold tracking-tight">SQL Query Agent</span>
          <span className="text-[10.5px] font-medium tracking-[0.22em] text-white/55 uppercase">AI Workspace</span>
        </div>
      </div>

      <div className="px-3 pt-4 pb-1">
        <button
          type="button"
          onClick={props.onNewChat}
          className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-white/15 py-2.5 text-[13.5px] font-semibold text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.2),0_10px_24px_-14px_rgba(0,0,0,0.6)] ring-1 ring-white/25 transition-all duration-200 hover:bg-white/25 hover:ring-white/40 active:scale-[0.99]"
        >
          <SquarePen size={17} />
          New chat
        </button>
      </div>

      <div className="space-y-0.5 px-3 py-3">
        <NavItem icon={<TableProperties size={16} />} label="Database schema" onClick={props.onOpenSchema} />
        {isDev && (
          <>
            <NavItem icon={<FileText size={16} />} label="Prompt library" onClick={() => setPrompts(true)} />
            <NavItem icon={<Network size={16} />} label="Knowledge graph" onClick={() => window.open(api.schemaGraphUrl, '_blank', 'noopener')} />
          </>
        )}
      </div>

      <div className="mt-3 mb-1 flex items-center gap-3 px-5">
        <span className="text-[10.5px] font-semibold tracking-[0.2em] text-white/55 uppercase">Your chats</span>
        <span className="h-px flex-1 bg-white/10" />
      </div>

      <div className="scrollbar-on-brand mt-1 min-h-0 flex-1 space-y-0.5 overflow-y-auto px-1 pb-3">
        {props.loading ? (
          <div className="flex justify-center py-6 text-white/60"><Spinner /></div>
        ) : props.threads.length === 0 ? (
          <p className="px-5 py-3 text-xs text-white/50">Your conversations will appear here.</p>
        ) : (
          props.threads.map((t) => (
            <ThreadItem
              key={t.thread_id}
              thread={t}
              active={t.thread_id === props.activeThreadId}
              onOpen={() => props.onOpenThread(t.thread_id)}
              onRename={(title) => props.onRenameThread(t.thread_id, title)}
              onDelete={() => props.onDeleteThread(t.thread_id)}
            />
          ))
        )}
      </div>

      <div className="border-t border-white/10 px-5 py-3 text-[11px] text-white/45">
        Summit Supply Co. · SQLite · read-only
      </div>
      <PromptsDialog open={prompts} onClose={() => setPrompts(false)} />
    </nav>
  )
}

function NavItem({ icon, label, onClick }: { icon: ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group/nav flex w-full cursor-pointer items-center gap-3 rounded-xl px-2.5 py-2.5 text-[13.5px] font-medium text-white/85 transition-all duration-200 hover:bg-white/10 hover:text-white active:scale-[0.99]"
    >
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-white/[0.06] text-white/80 ring-1 ring-white/10 transition-colors duration-200 group-hover/nav:bg-white/15 group-hover/nav:text-white">
        {icon}
      </span>
      <span className="truncate">{label}</span>
    </button>
  )
}
