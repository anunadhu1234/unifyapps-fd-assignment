// Shapes returned by the backend API (see backend/agent/narrative/return_response.py).

export type ResponseType = 'sql' | 'answer' | 'clarification' | 'refusal' | 'error'

export type Intent =
  | 'generate_sql'
  | 'modify_previous'
  | 'optimize_sql'
  | 'debug_sql'
  | 'explain_sql'
  | 'schema_question'
  | 'destructive'
  | 'out_of_scope'

export interface Finding {
  severity: 'error' | 'warning'
  code: string
  message: string
  hint?: string
}

export interface QueryResults {
  columns: string[]
  rows: unknown[][]
  row_count: number
  total_rows: number | null
  truncated: boolean
  ms: number | null
  error: string | null
}

export interface IndexRecommendation {
  ddl: string
  reason: string
  table?: string
  columns?: string[]
}

export type CostLevel = 'low' | 'medium' | 'high'

export interface CostEstimate {
  level: CostLevel
  score: number
  full_scans: string[]
  index_lookups: string[]
  temp_sorts: number
  plan: string[]
  recommendations: IndexRecommendation[]
}

export interface Explanation {
  summary: string
  steps: string[]
  text: string
}

export interface Optimization {
  mode: 'generated' | 'user'
  index_recommendations: IndexRecommendation[]
  original_sql?: string
  optimized_sql?: string
  accepted?: boolean
  rejected_reason?: string | null
  already_optimal?: boolean
  summary?: string
  changes?: { change: string; reason: string }[]
  removed_joins?: string[]
  cost_before?: CostEstimate | null
  cost_after?: CostEstimate | null
}

export interface DebugInfo {
  original_sql: string
  issues: { problem: string; why_incorrect: string }[]
  summary: string
  validator_findings: Finding[]
  changed: boolean
}

export interface Validation {
  ok: boolean
  checks_passed: string[]
  warnings: Finding[]
  errors: Finding[]
  attempts: number
}

export interface PipelineStepSummary {
  node: string
  ms: number | null
  ok: boolean
}

export interface LLMCall {
  step: string
  model: string
  tier: string
  route_reason: string
  ms: number
  ok: boolean
  input_tokens: number | null
  output_tokens: number | null
  cost_usd: number | null
  error: string | null
  served_by: string | null
  retried: boolean
}

export interface TraceEvent {
  node: string
  ms: number
  ok: boolean
  error?: string
  [key: string]: unknown
}

export interface ValidationAttempt {
  attempt: number
  origin: string
  sql: string
  ok: boolean
  findings: Finding[]
  checks_passed: string[]
}

export interface DevInfo {
  input_check: Record<string, unknown> | null
  intent: Record<string, unknown> | null
  standalone_question: string | null
  retrieval: Record<string, unknown> | null
  plan: Record<string, unknown> | null
  grounded_plan: Record<string, unknown> | null
  validation_history: ValidationAttempt[] | null
  failure: { node: string; kind: string; message: string } | null
  trace: TraceEvent[]
  llm_calls: LLMCall[]
  totals: {
    llm_calls: number
    input_tokens: number
    output_tokens: number
    cost_usd: number | null
    llm_ms: number
    pipeline_ms: number
  }
}

export interface FollowUpSuggestion {
  kind: 'drill_down' | 'refine' | 'related'
  question: string
}

export interface AgentResponse {
  request_id: string
  type: ResponseType
  intent: Intent | null
  message: string
  sql: string | null
  dialects: Record<string, string> | null
  explanation: Explanation | null
  answer: string | null
  results: QueryResults | null
  suggestions: FollowUpSuggestion[]
  cost: CostEstimate | null
  validation: Validation | null
  assumptions: string[]
  mappings: string[]
  optimization: Optimization | null
  debug: DebugInfo | null
  clarification: { question: string; options: string[]; request?: string } | null
  refusal: { reason: string; message: string } | null
  pipeline: PipelineStepSummary[]
  dev?: DevInfo
}

export interface ThreadSummary {
  thread_id: string
  title: string
  created_at: string
  updated_at: string
  turns: number
}

export interface Turn {
  request_id: string
  question: string
  created_at: string
  response: AgentResponse
}

export interface SchemaColumn {
  name: string
  type: string
  role: string
  description: string
  references: string | null
}

export interface SchemaSummary {
  database: string
  dialect: string
  as_of_date: string
  tables: { name: string; description: string; row_count: number; columns: SchemaColumn[] }[]
  relationships: { join: string; description: string }[]
  metrics: { name: string; description: string }[]
  suggested_questions: string[]
}

export interface PromptInfo {
  name: string
  version: string
  system: string
  user: string
}

export type StreamEvent =
  | { event: 'start'; thread_id: string }
  | { event: 'node'; node: string; ok: boolean; ms: number | null; detail: Record<string, unknown> }
  | { event: 'token'; node: string; text: string }
  | { event: 'response'; thread_id: string; response: AgentResponse }
  | { event: 'error'; message: string }

export type Role = 'normal' | 'dev'

export interface User {
  username: string
  role: Role
  display_name: string
}

export interface LoginResponse {
  token: string
  expires_at: string
  user: User
}

/** One question in the developer's run history. */
export interface RunSummary {
  request_id: string
  thread_id: string
  thread_title: string
  question: string
  created_at: string
  type: ResponseType | null
  intent: Intent | null
  rows: number | null
  attempts: number | null
  llm_calls: number
  input_tokens: number
  output_tokens: number
  cost_usd: number | null
  llm_ms: number
  pipeline_ms: number
  models: string[]
}

export interface RunHistory {
  runs: RunSummary[]
  summary: { runs: number; input_tokens: number; output_tokens: number; llm_calls: number; avg_pipeline_ms: number }
}
