import React from 'react'
import { useUiCustomization } from '@/contexts/UiCustomizationContext'

interface EditableButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  buttonKey: string
  defaultLabel: string
  icon?: React.ReactNode
  suffix?: React.ReactNode
  placeholderLabel?: string
}

export default function EditableButton({
  buttonKey,
  defaultLabel,
  icon,
  suffix,
  placeholderLabel = 'Add button',
  className,
  onClick,
  ...rest
}: EditableButtonProps) {
  const { getButton, isEditing, setDraftButton } = useUiCustomization()
  const { label, visible } = getButton(buttonKey, defaultLabel)

  if (!visible && !isEditing) return null

  if (!visible && isEditing) {
    return (
      <button
        type="button"
        onClick={() => setDraftButton(buttonKey, { visible: true })}
        className={className ?? 'px-4 py-2 rounded-lg border border-dashed border-slate-600 text-xs text-slate-300 hover:text-white'}
      >
        {placeholderLabel}
      </button>
    )
  }

  return (
    <div className="relative inline-flex">
      <button
        type="button"
        className={className}
        onClick={(event) => {
          if (isEditing) {
            event.preventDefault()
            event.stopPropagation()
            return
          }
          onClick?.(event)
        }}
        {...rest}
      >
        {icon}
        {isEditing ? (
          <input
            type="text"
            value={label}
            onChange={(e) => setDraftButton(buttonKey, { label: e.target.value })}
            className="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit"
          />
        ) : (
          <span>{label}</span>
        )}
        {suffix}
      </button>
      {isEditing && (
        <button
          type="button"
          onClick={() => setDraftButton(buttonKey, { visible: false })}
          className="absolute -top-2 -right-2 bg-slate-900 border border-slate-600 rounded-full w-5 h-5 text-[10px] text-slate-300 hover:text-white"
          aria-label="Hide button"
        >
          x
        </button>
      )}
    </div>
  )
}
