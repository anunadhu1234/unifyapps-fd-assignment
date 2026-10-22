import { Menu, PanelRight } from 'lucide-react'
import type { SchemaSummary } from '../../api/types'
import { useSettings } from '../../context/SettingsContext'
import type { AssistantMessage, ChatMessage } from '../../types/chat'
import { ProfileMenu } from '../layout/ProfileMenu'
import { IconButton } from '../ui/IconButton'
import { Spinner } from '../ui/Spinner'
import { Switch } from '../ui/Switch'
import { Composer } from './Composer'
import { EmptyState } from './EmptyState'
import { MessageList } from './MessageList'

interface Props {
  title: string
  messages: ChatMessage[]
  streaming: boolean
  loading: boolean
  schema: SchemaSummary | null
  selectedId: string | null
  inspectorOpen: boolean
  onSend: (text: string) => void
  onStop: () => void
  onRetry: (m: AssistantMessage) => void
  onSelect: (id: string) => void
  onOpenSidebar: () => void
  onToggleInspector: () => void
}

export function ChatView(props: Props) {
  const { execute, setExecute } = useSettings()
  const { messages, streaming, loading } = props
  const empty = messages.length === 0

  return (
    <div className="app-canvas flex h-full min-w-0 flex-1 flex-col">
      <header className="relative z-10 flex h-16 shrink-0 items-center gap-3 px-4">
        <IconButton label="Open chats" icon={<Menu size={18} />} className="lg:hidden" onClick={props.onOpenSidebar} />
        <h2 className="min-w-0 flex-1 truncate text-sm font-medium text-zinc-500 dark:text-zinc-400">
          {empty ? '' : props.title}
        </h2>
        <Switch
          checked={execute}
          onChange={setExecute}
          label="Run queries"
          description="Execute validated SQL against the sample database (turn off for SQL only)"
        />
        <IconButton
          label={props.inspectorOpen ? 'Hide details panel' : 'Show details panel'}
          icon={<PanelRight size={18} />}
          active={props.inspectorOpen}
          onClick={props.onToggleInspector}
        />
        <ProfileMenu />
      </header>

      <div className="relative min-h-0 flex-1 overflow-y-auto scrollbar-thin">
        {loading ? (
          <div className="flex h-full items-center justify-center text-brand-500">
            <Spinner />
          </div>
        ) : empty ? (
          <EmptyState schema={props.schema} onPick={props.onSend} />
        ) : (
          <MessageList
            messages={messages}
            selectedId={props.selectedId}
            onSelect={props.onSelect}
            onRetry={props.onRetry}
            onAnswer={props.onSend}
            busy={streaming}
          />
        )}
      </div>

      <div className="relative shrink-0 px-4 pt-2 pb-5">
        <Composer onSend={props.onSend} onStop={props.onStop} busy={streaming} autoFocus />
      </div>
    </div>
  )
}
