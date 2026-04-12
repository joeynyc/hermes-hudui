import { useState, useRef, useEffect } from 'react'
import { useLocale } from '../../lib/i18n'

interface ComposerProps {
  onSend: (message: string) => void
  onCancel?: () => void
  isStreaming: boolean
  model: string
  disabled?: boolean
}

export default function Composer({ onSend, onCancel, isStreaming, model, disabled }: ComposerProps) {
  const { t } = useLocale()
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = () => {
    const trimmed = input.trim()
    if (!trimmed || isStreaming || disabled) return

    onSend(trimmed)
    setInput('')

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`
    }
  }, [input])

  return (
    <div
      className="border-t px-2 py-1.5"
      style={{
        borderColor: 'var(--hud-border)',
        background: 'var(--hud-bg-surface)',
      }}
    >
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={disabled ? t('chat.chatNotAvailable') : t('chat.composerPlaceholder')}
          disabled={isStreaming || disabled}
          rows={1}
          className="flex-1 px-2 py-1.5 text-[13px] resize-none outline-none"
          style={{
            background: 'var(--hud-bg-panel)',
            color: 'var(--hud-text)',
            border: '1px solid var(--hud-border)',
            minHeight: '32px',
            maxHeight: '120px',
          }}
        />
        {isStreaming ? (
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-[13px] font-bold cursor-pointer"
            style={{
              background: 'var(--hud-error)',
              color: 'var(--hud-bg-deep)',
              border: 'none',
              minHeight: '32px',
            }}
            title={t('chat.composerStop')}
          >
            ■ {t('chat.composerStop')}
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!input.trim() || disabled}
            className="px-3 py-1.5 text-[13px] font-bold cursor-pointer disabled:opacity-40"
            style={{
              background: 'var(--hud-primary)',
              color: 'var(--hud-bg-deep)',
              border: 'none',
              minHeight: '32px',
            }}
          >
            {t('chat.composerSend')}
          </button>
        )}
      </div>
      <div
        className="mt-1 text-[11px] flex justify-between"
        style={{ color: 'var(--hud-text-dim)' }}
      >
        <span>{model !== 'unknown' ? model : ''}</span>
        <span style={{ color: isStreaming ? 'var(--hud-warning)' : 'var(--hud-text-dim)' }}>
          {isStreaming ? t('chat.streaming') : t('chat.enterToSend')}
        </span>
      </div>
    </div>
  )
}
