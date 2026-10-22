import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { PromptInfo } from '../../api/types'
import { Badge } from '../ui/Badge'
import { Modal } from '../ui/Modal'
import { Collapsible } from '../ui/Section'
import { Spinner } from '../ui/Spinner'

/** Every prompt in the backend prompt library, with its version (dev mode). */
export function PromptsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [prompts, setPrompts] = useState<PromptInfo[] | null>(null)

  useEffect(() => {
    if (open && !prompts) api.getPrompts().then(setPrompts).catch(() => setPrompts([]))
  }, [open, prompts])

  return (
    <Modal open={open} onClose={onClose} title="Prompt library" wide>
      {!prompts ? (
        <div className="flex justify-center py-10 text-zinc-400"><Spinner /></div>
      ) : (
        <div className="space-y-2">
          {prompts.map((p) => (
            <Collapsible key={p.name} title={<span className="font-mono text-xs">{p.name}</span>} meta={<Badge>v{p.version}</Badge>}>
              <p className="mb-1 text-[11px] font-semibold text-zinc-500 uppercase">System</p>
              <pre className="mb-3 max-h-80 overflow-auto scrollbar-thin rounded-md bg-zinc-50 p-3 font-mono text-[11px] whitespace-pre-wrap dark:bg-zinc-900">{p.system}</pre>
              <p className="mb-1 text-[11px] font-semibold text-zinc-500 uppercase">User template</p>
              <pre className="max-h-60 overflow-auto scrollbar-thin rounded-md bg-zinc-50 p-3 font-mono text-[11px] whitespace-pre-wrap dark:bg-zinc-900">{p.user}</pre>
            </Collapsible>
          ))}
        </div>
      )}
    </Modal>
  )
}
