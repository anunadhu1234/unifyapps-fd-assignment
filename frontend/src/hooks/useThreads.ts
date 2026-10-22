import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { ThreadSummary } from '../api/types'

/** The chat list for this browser (conversation history panel). */
export function useThreads() {
  const [threads, setThreads] = useState<ThreadSummary[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      setThreads(await api.listThreads())
    } catch {
      /* the list is non-critical; keep what we have */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const rename = useCallback(async (threadId: string, title: string) => {
    setThreads((all) => all.map((t) => (t.thread_id === threadId ? { ...t, title } : t)))
    await api.renameThread(threadId, title)
  }, [])

  const remove = useCallback(async (threadId: string) => {
    setThreads((all) => all.filter((t) => t.thread_id !== threadId))
    await api.deleteThread(threadId)
  }, [])

  return { threads, loading, refresh, rename, remove }
}
