import { ExternalLink, KeyRound, Link2 } from 'lucide-react'
import { api } from '../../api/client'
import type { SchemaColumn } from '../../api/types'
import { useSchema } from '../../hooks/useSchema'
import { Badge } from '../ui/Badge'
import { Drawer } from '../ui/Modal'
import { Collapsible, Section } from '../ui/Section'
import { Spinner } from '../ui/Spinner'

/** Browse the database: tables and columns, relationships, business metrics. */
export function SchemaDrawer({ open, onClose, onAsk }: { open: boolean; onClose: () => void; onAsk: (q: string) => void }) {
  const { schema, error } = useSchema()
  return (
    <Drawer open={open} onClose={onClose} title="Database schema">
      {!schema ? (
        <div className="flex justify-center py-12 text-zinc-400">{error ?? <Spinner />}</div>
      ) : (
        <div className="space-y-6 p-4">
          <div>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">{schema.database}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge tone="brand">{schema.dialect}</Badge>
              <Badge>Data as of {schema.as_of_date}</Badge>
              <a href={api.schemaGraphUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline dark:text-brand-300">
                Knowledge graph <ExternalLink size={12} />
              </a>
            </div>
          </div>

          <Section title="Tables">
            <div className="space-y-2">
              {schema.tables.map((t) => (
                <Collapsible key={t.name} title={<span className="font-mono text-sm">{t.name}</span>} meta={<Badge>{t.row_count.toLocaleString()} rows</Badge>}>
                  <p className="mb-3 text-xs text-zinc-500 dark:text-zinc-400">{t.description}</p>
                  <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
                    {t.columns.map((c) => <ColumnRow key={c.name} column={c} />)}
                  </ul>
                </Collapsible>
              ))}
            </div>
          </Section>

          <Section title="Relationships">
            <ul className="space-y-2">
              {schema.relationships.map((r) => (
                <li key={r.join} className="text-xs">
                  <code className="font-mono text-brand-700 dark:text-brand-300">{r.join}</code>
                  <p className="text-zinc-500 dark:text-zinc-400">{r.description}</p>
                </li>
              ))}
            </ul>
          </Section>

          <Section title="Business metrics">
            <div className="flex flex-wrap gap-1.5">
              {schema.metrics.map((m) => (
                <button key={m.name} type="button" title={m.description} onClick={() => { onAsk(`What is the ${m.name.toLowerCase()} by month in 2025?`); onClose() }}>
                  <Badge tone="neutral" className="hover:ring-brand-300">{m.name}</Badge>
                </button>
              ))}
            </div>
          </Section>
        </div>
      )}
    </Drawer>
  )
}

function ColumnRow({ column: c }: { column: SchemaColumn }) {
  return (
    <li className="flex gap-3 py-2">
      <div className="w-40 shrink-0">
        <p className="flex items-center gap-1 font-mono text-xs font-medium">
          {c.role === 'primary_key' && <KeyRound size={11} className="text-amber-500" />}
          {c.role === 'foreign_key' && <Link2 size={11} className="text-sky-500" />}
          {c.name}
        </p>
        <p className="font-mono text-[10px] text-zinc-400">{c.type}{c.references ? ` → ${c.references}` : ''}</p>
      </div>
      <p className="text-xs text-zinc-600 dark:text-zinc-400">{c.description}</p>
    </li>
  )
}
