import { BookOpen, Code2, Cpu, GitBranch, History, MousePointerClick, Table2, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import type { AssistantMessage } from '../../types/chat'
import { Badge } from '../ui/Badge'
import { IconButton } from '../ui/IconButton'
import { EmptyHint } from '../ui/Section'
import { Tabs, type TabItem } from '../ui/Tabs'
import { DevTab } from './DevTab'
import { ExplanationTab } from './ExplanationTab'
import { PipelineTab } from './PipelineTab'
import { ResultsTab } from './ResultsTab'
import { RunsTab } from './RunsTab'
import { SqlTab } from './SqlTab'

type TabId = 'sql' | 'explanation' | 'results' | 'pipeline' | 'dev' | 'runs'

/** Details of the selected answer: SQL, explanation, results, pipeline — plus, for the dev account,
 *  the internals of the answer (Dev) and the run history across all chats (Runs). */
export function Inspector({ message, onClose, onOpenThread, runsKey = 0 }: {
  message?: AssistantMessage
  onClose?: () => void
  onOpenThread?: (threadId: string) => void
  /** Changes whenever a turn finishes, so the run history refreshes. */
  runsKey?: number
}) {
  const { isDev: devMode } = useAuth()
  const r = message?.response
  const hasSql = !!r?.sql

  const tabs = useMemo(() => {
    const items: TabItem<TabId>[] = []
    if (hasSql) {
      items.push({ id: 'sql', label: 'SQL', icon: <Code2 size={14} /> })
      if (r?.explanation) items.push({ id: 'explanation', label: 'Explanation', icon: <BookOpen size={14} /> })
      if (r?.type === 'sql')
        items.push({
          id: 'results',
          label: 'Results',
          icon: <Table2 size={14} />,
          badge: r.results && !r.results.error ? <Badge>{r.results.total_rows ?? r.results.row_count}</Badge> : undefined,
        })
    }
    items.push({ id: 'pipeline', label: 'Pipeline', icon: <GitBranch size={14} /> })
    if (devMode) {
      items.push({ id: 'dev', label: 'Dev', icon: <Cpu size={14} /> })
      items.push({ id: 'runs', label: 'Runs', icon: <History size={14} /> })
    }
    return items
  }, [hasSql, r, devMode])

  const [tab, setTab] = useState<TabId>('sql')
  useEffect(() => {
    setTab(hasSql ? 'sql' : 'pipeline')
  }, [message?.id, hasSql])
  const active = tabs.some((t) => t.id === tab) ? tab : tabs[0].id

  return (
    <div className="flex h-full min-h-0 flex-col bg-white dark:bg-zinc-950">
      <div className="flex shrink-0 items-center gap-1 pr-2 pl-1">
        <Tabs items={tabs} value={active} onChange={setTab} className="min-w-0 flex-1 border-b-0" />
        {onClose && <IconButton label="Close details" icon={<X size={16} />} size="sm" onClick={onClose} />}
      </div>
      <div className="border-b border-zinc-200 dark:border-zinc-800" />
      <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin p-4">
        {active === 'runs' ? (
          <RunsTab refreshKey={runsKey} onOpenThread={onOpenThread} />
        ) : !message ? (
          <EmptyHint icon={<MousePointerClick size={28} />} title="Select an answer">
            Click an answer in the chat to see its SQL, explanation, results and the pipeline that produced it.
          </EmptyHint>
        ) : message.status === 'streaming' ? (
          <PipelineTab steps={message.steps} />
        ) : !r ? (
          <EmptyHint title="No details for this message" />
        ) : active === 'sql' ? (
          <SqlTab response={r} />
        ) : active === 'explanation' ? (
          <ExplanationTab response={r} />
        ) : active === 'results' ? (
          <ResultsTab key={r.request_id} response={r} />
        ) : active === 'dev' ? (
          <DevTab dev={r.dev} />
        ) : (
          <PipelineTab steps={message.steps} response={r} />
        )}
      </div>
    </div>
  )
}
