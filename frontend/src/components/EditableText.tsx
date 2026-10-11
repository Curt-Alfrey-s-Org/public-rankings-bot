import { useEffect, useState } from 'react'
import { useUiCustomization } from '@/contexts/UiCustomizationContext'

interface EditableTextProps {
  textKey: string
  defaultText: string
  className?: string
  inputClassName?: string
}

export default function EditableText({ textKey, defaultText, className, inputClassName }: EditableTextProps) {
  const { getText, isEditing, setDraftText } = useUiCustomization()
  const value = getText(textKey, defaultText)
  const [draft, setDraft] = useState(value)

  useEffect(() => {
    setDraft(value)
  }, [value])

  if (!isEditing) {
    return <span className={className}>{value}</span>
  }

  return (
    <input
      type="text"
      value={draft}
      onChange={(e) => {
        const next = e.target.value
        setDraft(next)
        setDraftText(textKey, next)
      }}
      className={inputClassName ?? 'bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit w-full'}
    />
  )
}
