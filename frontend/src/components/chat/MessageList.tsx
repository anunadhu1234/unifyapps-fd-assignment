import { useEffect, useRef } from 'react'
import type { AssistantMessage as AssistantMessageModel, ChatMessage } from '../../types/chat'
import { AssistantMessage } from './AssistantMessage'
import { UserMessage } from './UserMessage'

/** Scrolls to the newest message while the user is near the bottom (doesn't yank them back up). */
export function MessageList({ messages, selectedId, onSelect, onRetry, onAnswer, busy }: {
  messages: ChatMessage[]
  selectedId: string | null
  onSelect: (id: string) => void
  onRetry: (m: AssistantMessageModel) => void
  onAnswer: (text: string) => void
  busy?: boolean
}) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = containerRef.current?.parentElement
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 240
    if (nearBottom) bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  return (
    <div ref={containerRef} className="mx-auto w-full max-w-3xl space-y-7 px-6 py-6">
      {messages.map((m) =>
        m.kind === 'user' ? (
          <UserMessage key={m.id} message={m} />
        ) : (
          <AssistantMessage
            key={m.id}
            message={m}
            selected={m.id === selectedId}
            onSelect={() => onSelect(m.id)}
            onRetry={() => onRetry(m)}
            onAnswer={onAnswer}
            busy={busy}
          />
        ),
      )}
      <div ref={bottomRef} />
    </div>
  )
}
