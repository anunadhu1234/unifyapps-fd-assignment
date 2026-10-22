import { memo, useMemo } from 'react'
import { cn } from '../../lib/cn'
import { TOKEN_CLASS, tokenizeSql } from '../../lib/sqlHighlight'

/** Syntax-highlighted SQL with optional line numbers. */
export const SqlCode = memo(function SqlCode({ sql, lineNumbers = true, className, maxLines }: {
  sql: string
  lineNumbers?: boolean
  className?: string
  maxLines?: number
}) {
  const lines = useMemo(() => {
    const all = sql.split('\n')
    return maxLines && all.length > maxLines ? [...all.slice(0, maxLines), '…'] : all
  }, [sql, maxLines])

  return (
    <pre
      className={cn(
        'overflow-x-auto scrollbar-thin rounded-lg border border-zinc-200 bg-zinc-50 py-3 font-mono text-[12.5px] leading-6 dark:border-zinc-800 dark:bg-zinc-900/70',
        className,
      )}
    >
      <code>
        {lines.map((line, i) => (
          <div key={i} className="flex px-3">
            {lineNumbers && (
              <span className="mr-4 inline-block w-6 shrink-0 text-right text-zinc-300 select-none dark:text-zinc-600">
                {i + 1}
              </span>
            )}
            <span className="whitespace-pre">
              {tokenizeSql(line).map((t, j) => (
                <span key={j} className={TOKEN_CLASS[t.kind]}>
                  {t.text}
                </span>
              ))}
            </span>
          </div>
        ))}
      </code>
    </pre>
  )
})
