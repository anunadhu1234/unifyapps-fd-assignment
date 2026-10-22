// A small SQL tokenizer for syntax highlighting — no highlighting library needed.

export type TokenKind = 'keyword' | 'function' | 'string' | 'number' | 'comment' | 'operator' | 'punct' | 'ident' | 'space'

export interface Token {
  kind: TokenKind
  text: string
}

const KEYWORDS = new Set(
  `select from where and or not in is null as on join left right inner outer full cross natural using group by
   order having limit offset distinct union all intersect except case when then else end with recursive asc desc
   between like ilike exists any some true false over partition rows range preceding following current row window
   interval date time timestamp cast filter nulls first last escape glob collate`
    .split(/\s+/)
    .filter(Boolean),
)

const FUNCTIONS = new Set(
  `count sum avg min max round abs coalesce ifnull nullif length lower upper substr substring trim replace instr
   strftime julianday date datetime printf total group_concat string_agg row_number rank dense_rank lag lead
   ntile first_value last_value extract to_char date_trunc concat`
    .split(/\s+/)
    .filter(Boolean),
)

const PATTERN =
  /(--[^\n]*|\/\*[\s\S]*?\*\/)|('(?:[^']|'')*')|("(?:[^"]|"")*"|`[^`]*`)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)|(\s+)|(<>|!=|<=|>=|\|\||[=<>+\-*/%])|([(),.;])/g

export function tokenizeSql(sql: string): Token[] {
  const tokens: Token[] = []
  let last = 0
  for (const m of sql.matchAll(PATTERN)) {
    if (m.index! > last) tokens.push({ kind: 'ident', text: sql.slice(last, m.index) })
    const [text, comment, str, quoted, num, word, space, op] = m
    let kind: TokenKind = 'punct'
    if (comment) kind = 'comment'
    else if (str) kind = 'string'
    else if (quoted) kind = 'ident'
    else if (num) kind = 'number'
    else if (word) {
      const lower = word.toLowerCase()
      const next = sql.slice(m.index! + word.length).trimStart()[0]
      kind = KEYWORDS.has(lower) ? 'keyword' : FUNCTIONS.has(lower) && next === '(' ? 'function' : 'ident'
    } else if (space) kind = 'space'
    else if (op) kind = 'operator'
    tokens.push({ kind, text })
    last = m.index! + text.length
  }
  if (last < sql.length) tokens.push({ kind: 'ident', text: sql.slice(last) })
  return tokens
}

export const TOKEN_CLASS: Record<TokenKind, string> = {
  keyword: 'text-brand-600 dark:text-brand-300 font-medium',
  function: 'text-sky-700 dark:text-sky-300',
  string: 'text-emerald-700 dark:text-emerald-300',
  number: 'text-amber-700 dark:text-amber-300',
  comment: 'text-zinc-400 italic',
  operator: 'text-rose-600 dark:text-rose-300',
  punct: 'text-zinc-500 dark:text-zinc-400',
  ident: 'text-zinc-800 dark:text-zinc-200',
  space: '',
}
