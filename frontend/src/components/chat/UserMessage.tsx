import type { UserMessage as UserMessageModel } from '../../types/chat'

export function UserMessage({ message }: { message: UserMessageModel }) {
  const looksLikeSql = /\b(select|with)\b[\s\S]+\bfrom\b/i.test(message.text) && message.text.includes('\n')
  return (
    <div className="animate-fade-in flex justify-end">
      <div className="shadow-bubble max-w-[80%] rounded-2xl rounded-br-md bg-gradient-to-r from-brand-600 to-brand-800 px-5 py-3 text-[15px] leading-relaxed text-white ring-1 ring-white/10">
        <p className={looksLikeSql ? 'font-mono text-[12.5px] whitespace-pre-wrap' : 'whitespace-pre-wrap'}>
          {message.text}
        </p>
      </div>
    </div>
  )
}
