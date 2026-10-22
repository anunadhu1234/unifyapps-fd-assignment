import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '../../lib/cn'

/** Markdown from the model, rendered safely (react-markdown never injects raw HTML). */
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn('prose-chat', className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  )
}
