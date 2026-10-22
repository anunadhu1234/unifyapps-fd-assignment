import type { AgentResponse } from '../api/types'

/** One finished (or running) pipeline step, as streamed by the backend. */
export interface PipelineStep {
  node: string
  ok: boolean
  ms: number | null
  detail?: Record<string, unknown>
}

export interface UserMessage {
  kind: 'user'
  id: string
  text: string
}

export interface AssistantMessage {
  kind: 'assistant'
  id: string
  question: string
  status: 'streaming' | 'done' | 'failed'
  steps: PipelineStep[]
  streamText: string // explanation / answer tokens while streaming
  response?: AgentResponse
  error?: string
}

export type ChatMessage = UserMessage | AssistantMessage
