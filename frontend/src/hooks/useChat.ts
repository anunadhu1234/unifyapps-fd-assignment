import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/client'
import type { AgentResponse } from '../api/types'
import type { AssistantMessage, ChatMessage } from '../types/chat'

const newId = () => crypto.randomUUID()

interface Options {
  execute: boolean
  /** A new chat got its id from the server (first message). */
  onThreadCreated?: (threadId: string) => void
  /** A turn finished (successfully or not) — e.g. refresh the chat list. */
  onTurnFinished?: () => void
}

/** State and actions for one conversation: streaming a turn, loading a saved chat, stopping, retrying. */
export function useChat({ execute, onThreadCreated, onTurnFinished }: Options) {
  const [threadId, setThreadId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const threadRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  const patch = useCallback((id: string, change: (m: AssistantMessage) => AssistantMessage) => {
    setMessages((all) => all.map((m) => (m.id === id && m.kind === 'assistant' ? change(m) : m)))
  }, [])

  const streaming = messages.some((m) => m.kind === 'assistant' && m.status === 'streaming')

  const send = useCallback(
    async (question: string) => {
      const text = question.trim()
      if (!text || abortRef.current) return
      const assistantId = newId()
      setMessages((all) => [
        ...all,
        { kind: 'user', id: newId(), text },
        { kind: 'assistant', id: assistantId, question: text, status: 'streaming', steps: [], streamText: '' },
      ])

      const controller = new AbortController()
      abortRef.current = controller
      try {
        const events = api.streamChat({ question: text, thread_id: threadRef.current, execute }, controller.signal)
        for await (const event of events) {
          switch (event.event) {
            case 'start':
              if (!threadRef.current) {
                threadRef.current = event.thread_id
                setThreadId(event.thread_id)
                onThreadCreated?.(event.thread_id)
              }
              break
            case 'node':
              patch(assistantId, (m) => ({
                ...m,
                steps: [...m.steps, { node: event.node, ok: event.ok, ms: event.ms, detail: event.detail }],
              }))
              break
            case 'token':
              patch(assistantId, (m) => ({ ...m, streamText: m.streamText + event.text }))
              break
            case 'response':
              patch(assistantId, (m) => ({ ...m, status: 'done', response: event.response }))
              break
            case 'error':
              patch(assistantId, (m) => ({ ...m, status: 'failed', error: event.message }))
              break
          }
        }
        patch(assistantId, (m) =>
          m.status === 'streaming' ? { ...m, status: 'failed', error: 'The connection closed before the answer arrived.' } : m,
        )
      } catch (err) {
        const message = controller.signal.aborted
          ? 'Stopped.'
          : err instanceof ApiError
            ? err.message
            : 'Could not reach the server. Check your connection and try again.'
        patch(assistantId, (m) => ({ ...m, status: 'failed', error: message }))
      } finally {
        abortRef.current = null
        onTurnFinished?.()
      }
    },
    [execute, onThreadCreated, onTurnFinished, patch],
  )

  const stop = useCallback(() => abortRef.current?.abort(), [])

  const newChat = useCallback(() => {
    abortRef.current?.abort()
    threadRef.current = null
    setThreadId(null)
    setMessages([])
  }, [])

  const openThread = useCallback(async (id: string) => {
    abortRef.current?.abort()
    setLoading(true)
    try {
      const { turns } = await api.getThread(id)
      threadRef.current = id
      setThreadId(id)
      setMessages(
        turns.flatMap((t): ChatMessage[] => [
          { kind: 'user', id: `${t.request_id}-q`, text: t.question },
          {
            kind: 'assistant',
            id: t.request_id,
            question: t.question,
            status: 'done',
            steps: (t.response.pipeline ?? []).map((s) => ({ node: s.node, ok: s.ok, ms: s.ms })),
            streamText: '',
            response: t.response,
          },
        ]),
      )
      return true
    } catch {
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  const retry = useCallback(
    (message: AssistantMessage) => {
      setMessages((all) => all.filter((m) => m.id !== message.id))
      void send(message.question)
    },
    [send],
  )

  return { threadId, messages, streaming, loading, send, stop, newChat, openThread, retry }
}

export function lastResponse(messages: ChatMessage[]): AgentResponse | undefined {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i]
    if (m.kind === 'assistant' && m.response) return m.response
  }
  return undefined
}
