import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { useSettings } from '../../context/SettingsContext'
import { useChat } from '../../hooks/useChat'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import { useSchema } from '../../hooks/useSchema'
import { useThreads } from '../../hooks/useThreads'
import { cn } from '../../lib/cn'
import { readStorage, STORAGE_KEYS, writeStorage } from '../../lib/storage'
import type { AssistantMessage } from '../../types/chat'
import { ChatView } from '../chat/ChatView'
import { Inspector } from '../inspector/Inspector'
import { SchemaDrawer } from '../schema/SchemaDrawer'
import { Drawer } from '../ui/Modal'
import { useToast } from '../ui/Toast'
import { Sidebar } from './Sidebar'

/**
 * Three-pane layout: chats (left) · conversation (center) · answer details (right).
 * Below the `lg` breakpoint the side panes become overlays.
 */
export function AppShell() {
  const { execute } = useSettings()
  const { user } = useAuth()
  // Remember the open chat per account (switching accounts never reopens the other account's chat).
  const activeKey = `${STORAGE_KEYS.activeThread}:${user?.username}`
  const toast = useToast()
  const desktop = useMediaQuery('(min-width: 1024px)')
  const { schema } = useSchema()
  const threads = useThreads()

  const onThreadCreated = useCallback((id: string) => writeStorage(activeKey, id), [activeKey])
  const chat = useChat({ execute, onThreadCreated, onTurnFinished: threads.refresh })

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [inspectorOpen, setInspectorOpen] = useState(true)
  const [mobileInspector, setMobileInspector] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [schemaOpen, setSchemaOpen] = useState(false)

  // Reopen the chat the user had open last time.
  useEffect(() => {
    const last = readStorage(activeKey)
    if (last) chat.openThread(last).then((ok) => !ok && writeStorage(activeKey, null))
  }, [])

  const assistantMessages = useMemo(
    () => chat.messages.filter((m): m is AssistantMessage => m.kind === 'assistant'),
    [chat.messages],
  )
  // Follow the newest answer unless the user picked an older one.
  const selected = assistantMessages.find((m) => m.id === selectedId) ?? assistantMessages[assistantMessages.length - 1]

  useEffect(() => {
    setSelectedId(null)
  }, [assistantMessages.length])

  const select = (id: string) => {
    setSelectedId(id)
    if (desktop) setInspectorOpen(true)
    else setMobileInspector(true)
  }

  const newChat = () => {
    chat.newChat()
    writeStorage(activeKey, null)
    setSidebarOpen(false)
  }

  const openThread = async (id: string) => {
    setSidebarOpen(false)
    if (id === chat.threadId) return
    if (await chat.openThread(id)) writeStorage(activeKey, id)
    else toast.error('Could not open that chat.')
  }

  const deleteThread = async (id: string) => {
    try {
      await threads.remove(id)
      if (id === chat.threadId) newChat()
    } catch {
      toast.error('Could not delete the chat.')
      void threads.refresh()
    }
  }

  const renameThread = (id: string, title: string) =>
    threads.rename(id, title).catch(() => toast.error('Could not rename the chat.'))

  // Refresh the dev run history whenever an answer finishes.
  const runsKey = assistantMessages.filter((m) => m.status !== 'streaming').length

  const title = threads.threads.find((t) => t.thread_id === chat.threadId)?.title ?? 'New chat'

  const sidebar = (
    <Sidebar
      threads={threads.threads}
      loading={threads.loading}
      activeThreadId={chat.threadId}
      onNewChat={newChat}
      onOpenThread={openThread}
      onRenameThread={renameThread}
      onDeleteThread={deleteThread}
      onOpenSchema={() => {
        setSidebarOpen(false)
        setSchemaOpen(true)
      }}
    />
  )

  return (
    <div className="flex h-full overflow-hidden">
      {/* Chats */}
      <aside className="hidden w-[300px] shrink-0 lg:block">{sidebar}</aside>
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-zinc-950/30" onClick={() => setSidebarOpen(false)} />
          <div className="animate-fade-in absolute inset-y-0 left-0 w-[300px] shadow-xl">
            {sidebar}
          </div>
        </div>
      )}

      {/* Conversation */}
      <main className="flex min-w-0 flex-1">
        <ChatView
          title={title}
          messages={chat.messages}
          streaming={chat.streaming}
          loading={chat.loading}
          schema={schema}
          selectedId={selected?.id ?? null}
          inspectorOpen={desktop ? inspectorOpen : mobileInspector}
          onSend={chat.send}
          onStop={chat.stop}
          onRetry={chat.retry}
          onSelect={select}
          onOpenSidebar={() => setSidebarOpen(true)}
          onToggleInspector={() => (desktop ? setInspectorOpen(!inspectorOpen) : setMobileInspector(!mobileInspector))}
        />
      </main>

      {/* Answer details */}
      {desktop && (
        <aside
          className={cn(
            'shrink-0 border-l border-zinc-200/80 bg-white transition-[width] dark:border-zinc-800 dark:bg-zinc-950',
            inspectorOpen ? 'w-[440px] xl:w-[520px]' : 'w-0 overflow-hidden border-l-0',
          )}
        >
          {inspectorOpen && <Inspector message={selected} onOpenThread={openThread} runsKey={runsKey} />}
        </aside>
      )}
      {!desktop && (
        <Drawer open={mobileInspector} onClose={() => setMobileInspector(false)} title="Answer details">
          <Inspector message={selected} onOpenThread={openThread} runsKey={runsKey} />
        </Drawer>
      )}

      <SchemaDrawer open={schemaOpen} onClose={() => setSchemaOpen(false)} onAsk={chat.send} />
    </div>
  )
}
