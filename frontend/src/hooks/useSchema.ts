import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { SchemaSummary } from '../api/types'

let cache: SchemaSummary | null = null

/** Database summary (tables, relationships, metrics, suggested questions) — fetched once per page load. */
export function useSchema() {
  const [schema, setSchema] = useState<SchemaSummary | null>(cache)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (cache) return
    api
      .getSchema()
      .then((s) => {
        cache = s
        setSchema(s)
      })
      .catch(() => setError('Could not load the database schema.'))
  }, [])

  return { schema, error }
}
