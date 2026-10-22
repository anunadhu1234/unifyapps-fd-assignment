import { cn } from '../../lib/cn'

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={cn(
        'inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent',
        className,
      )}
    />
  )
}

export function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1" aria-label="Working">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-400"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  )
}
