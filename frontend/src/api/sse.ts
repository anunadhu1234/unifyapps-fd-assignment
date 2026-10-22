import type { StreamEvent } from './types'

export interface RawSseEvent {
  event: string
  data: unknown
}

/**
 * Parse a Server-Sent Events body (from fetch) into {event, data} pairs.
 * EventSource is not used because it cannot send the Authorization header.
 */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<RawSseEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const parsed = parseBlock(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
        if (parsed) yield parsed
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    reader.releaseLock()
  }
}

/** Chat stream: typed pipeline events. */
export async function* readEventStream(body: ReadableStream<Uint8Array>): AsyncGenerator<StreamEvent> {
  for await (const { event, data } of readSse(body)) {
    yield { ...(data as object), event } as StreamEvent
  }
}

function parseBlock(block: string): RawSseEvent | null {
  let name = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith(':')) continue // heartbeat / comment
    if (line.startsWith('event:')) name = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
  }
  if (!data.length) return null
  try {
    return { event: name, data: JSON.parse(data.join('\n')) }
  } catch {
    return null
  }
}
