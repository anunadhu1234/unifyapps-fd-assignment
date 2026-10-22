// Human labels for the LangGraph nodes (backend/agent/supervisor/supervisor.py).

export const STEP_LABELS: Record<string, string> = {
  receive_request: 'Received request',
  intent_detection: 'Understanding the request',
  scope_validation: 'Checking scope',
  schema_retrieval: 'Finding relevant tables',
  query_planner: 'Planning the query',
  plan_grounding: 'Matching to schema and stored values',
  sql_generation: 'Writing SQL',
  sql_validation: 'Validating SQL',
  sql_repair: 'Repairing SQL',
  sql_debugging: 'Debugging your SQL',
  sql_optimization: 'Optimizing and estimating cost',
  execute_query: 'Running the query',
  generate_explanation: 'Explaining the query',
  suggest_follow_ups: 'Suggesting follow-up questions',
  ask_clarification: 'Preparing a question',
  schema_answer: 'Answering from the schema',
  return_response: 'Done',
}

export function stepLabel(node: string): string {
  return STEP_LABELS[node] ?? node.replace(/_/g, ' ')
}

export const CHECK_LABELS: Record<string, string> = {
  syntax: 'Valid SQLite syntax',
  read_only: 'Read-only (no data changes)',
  tables: 'All tables exist',
  columns: 'All columns exist',
  values: 'Filter values are stored values',
  joins: 'Joins follow real relationships',
  engine: 'Compiles in SQLite',
  plan: 'Matches the query plan',
}

export const INTENT_LABELS: Record<string, string> = {
  generate_sql: 'New query',
  modify_previous: 'Follow-up',
  optimize_sql: 'Optimization',
  debug_sql: 'Debugging',
  explain_sql: 'Explanation',
  schema_question: 'Schema question',
  destructive: 'Destructive request',
  out_of_scope: 'Out of scope',
}
