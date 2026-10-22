import { ChevronLeft, ChevronRight, Download, Table2, TriangleAlert } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api } from '../../api/client'
import type { AgentResponse } from '../../api/types'
import { cn } from '../../lib/cn'
import { downloadBlob } from '../../lib/download'
import { formatCell, formatMs, isNumeric, plural, toCsv } from '../../lib/format'
import { Button } from '../ui/Button'
import { CopyButton } from '../ui/CopyButton'
import { IconButton } from '../ui/IconButton'
import { EmptyHint } from '../ui/Section'
import { useToast } from '../ui/Toast'

const PAGE_SIZE = 50

export function ResultsTab({ response: r }: { response: AgentResponse }) {
  const results = r.results
  const [page, setPage] = useState(0)
  const [exporting, setExporting] = useState(false)
  const toast = useToast()

  const numericColumns = useMemo(
    () => new Set(results?.columns.filter((_, i) => results.rows.some((row) => isNumeric(row[i]))) ?? []),
    [results],
  )

  if (!results) {
    return (
      <EmptyHint icon={<Table2 size={28} />} title="This query was not run">
        Turn on “Run queries” in the header to execute validated SQL against the sample database.
      </EmptyHint>
    )
  }
  if (results.error) {
    return (
      <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
        <TriangleAlert size={16} className="mt-0.5 shrink-0" /> {results.error}
      </div>
    )
  }
  if (results.row_count === 0) {
    return <EmptyHint icon={<Table2 size={28} />} title="No rows matched">The query ran successfully but returned no rows.</EmptyHint>
  }

  const pages = Math.ceil(results.rows.length / PAGE_SIZE)
  const visible = results.rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)

  const exportFull = async () => {
    setExporting(true)
    try {
      const { blob, filename } = await api.exportCsv(r.request_id)
      downloadBlob(blob, filename)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Export failed.')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          {results.truncated && results.total_rows
            ? `Showing the first ${results.row_count.toLocaleString()} of ${results.total_rows.toLocaleString()} rows`
            : plural(results.row_count, 'row')}
          {results.ms !== null && ` · ${formatMs(results.ms)}`}
        </p>
        <div className="flex gap-1.5">
          <CopyButton text={toCsv(results.columns, results.rows)} label="Copy" successMessage="Rows copied as CSV" />
          <Button size="sm" variant="primary" icon={<Download size={14} />} onClick={exportFull} disabled={exporting}>
            {exporting ? 'Exporting…' : results.truncated ? 'Download all (CSV)' : 'Download CSV'}
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto scrollbar-thin rounded-lg border border-zinc-200 dark:border-zinc-800">
        <table className="w-full border-collapse text-xs">
          <thead className="sticky top-0 z-10 bg-zinc-50 dark:bg-zinc-900">
            <tr>
              {results.columns.map((c) => (
                <th
                  key={c}
                  className={cn(
                    'border-b border-zinc-200 px-3 py-2 font-semibold whitespace-nowrap text-zinc-600 dark:border-zinc-800 dark:text-zinc-300',
                    numericColumns.has(c) ? 'text-right' : 'text-left',
                  )}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.map((row, i) => (
              <tr key={i} className="odd:bg-white even:bg-zinc-50/60 hover:bg-brand-50/40 dark:odd:bg-zinc-950 dark:even:bg-zinc-900/40 dark:hover:bg-brand-950/20">
                {row.map((cell, j) => (
                  <td
                    key={j}
                    className={cn(
                      'max-w-72 truncate border-b border-zinc-100 px-3 py-1.5 whitespace-nowrap dark:border-zinc-900',
                      isNumeric(cell) ? 'text-right tabular-nums' : 'text-left',
                      cell === null && 'text-zinc-300 dark:text-zinc-600',
                    )}
                    title={cell === null ? 'NULL' : String(cell)}
                  >
                    {formatCell(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pages > 1 && (
        <div className="flex items-center justify-end gap-2 text-xs text-zinc-500">
          <IconButton label="Previous page" size="sm" icon={<ChevronLeft size={14} />} disabled={page === 0} onClick={() => setPage(page - 1)} />
          <span className="tabular-nums">
            Page {page + 1} of {pages}
          </span>
          <IconButton label="Next page" size="sm" icon={<ChevronRight size={14} />} disabled={page >= pages - 1} onClick={() => setPage(page + 1)} />
        </div>
      )}
    </div>
  )
}
