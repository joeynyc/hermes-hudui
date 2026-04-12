interface MessageBubbleProps {
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  isStreaming?: boolean
}

export default function MessageBubble({ role, content, isStreaming }: MessageBubbleProps) {
  const isUser = role === 'user'
  const isAssistant = role === 'assistant'

  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}
    >
      <div
        className="max-w-[85%] px-3 py-2 text-[14px] leading-relaxed"
        style={{
          background: isUser
            ? 'var(--hud-primary)'
            : isAssistant
              ? 'var(--hud-bg-panel)'
              : 'var(--hud-bg-surface)',
          color: isUser ? 'var(--hud-bg-deep)' : 'var(--hud-text)',
          borderLeft: isUser
            ? 'none'
            : isAssistant
              ? '2px solid var(--hud-primary)'
              : '2px solid var(--hud-text-dim)',
          whiteSpace: 'pre-wrap',
        }}
      >
        {content}
        {isStreaming && (
          <span className="inline-block ml-1 animate-pulse" style={{ color: 'var(--hud-primary)' }}>
            ●
          </span>
        )}
      </div>
    </div>
  )
}
