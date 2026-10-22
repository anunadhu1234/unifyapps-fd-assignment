import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { copyText } from '../../lib/download'
import { Button } from './Button'
import { IconButton } from './IconButton'
import { useToast } from './Toast'

export function CopyButton({ text, label = 'Copy', compact, successMessage = 'Copied to clipboard' }: {
  text: string
  label?: string
  compact?: boolean
  successMessage?: string
}) {
  const [copied, setCopied] = useState(false)
  const toast = useToast()

  const copy = async () => {
    if (await copyText(text)) {
      setCopied(true)
      toast.success(successMessage)
      setTimeout(() => setCopied(false), 1500)
    } else {
      toast.error('Could not access the clipboard.')
    }
  }

  const icon = copied ? <Check size={14} className="text-emerald-600" /> : <Copy size={14} />
  if (compact) return <IconButton label={label} icon={icon} size="sm" onClick={copy} />
  return (
    <Button size="sm" icon={icon} onClick={copy}>
      {copied ? 'Copied' : label}
    </Button>
  )
}
