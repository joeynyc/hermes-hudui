import { useEffect, useRef } from 'react'
import type { UIMessage } from 'ai'
import { isTextUIPart, isReasoningUIPart, isToolUIPart } from 'ai'
import MessageBubble from './MessageBubble'
import ToolCallCard from './ToolCallCard'
import ReasoningBlock from './ReasoningBlock'

interface MessageThreadProps {
  messages: UIMessage[]
  isStreaming: boolean
  onRegenerate?: (messageId: string) => void
}

export default function MessageThread({ messages, isStreaming, onRegenerate }: MessageThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex-1 overflow-y-auto p-2 space-y-1">
      {messages.length === 0 ? (
        <div className="h-full flex items-center justify-center">
          <div className="text-center" style={{ color: 'var(--hud-text-dim)' }}>
            <div className="text-[14px] mb-1">No messages yet</div>
            <div className="text-[12px]">Start a conversation below</div>
          </div>
        </div>
      ) : (
        messages.map((message, msgIndex) => {
          const isLastMessage = msgIndex === messages.length - 1
          const isStreamingThis = isStreaming && isLastMessage && message.role === 'assistant'

          return (
            <div key={message.id}>
              {message.parts.map((part, partIndex) => {
                if (isReasoningUIPart(part)) {
                  return <ReasoningBlock key={partIndex} content={part.text} />
                }
                if (isToolUIPart(part)) {
                  return <ToolCallCard key={partIndex} part={part} />
                }
                if (isTextUIPart(part) && part.text) {
                  return (
                    <MessageBubble
                      key={partIndex}
                      role={message.role as 'user' | 'assistant'}
                      content={part.text}
                      isStreaming={isStreamingThis && part.state === 'streaming'}
                    />
                  )
                }
                return null
              })}
              {isLastMessage && message.role === 'assistant' && !isStreaming && onRegenerate && (
                <div className="flex justify-start pl-1 mt-0.5">
                  <button
                    onClick={() => onRegenerate(message.id)}
                    className="px-2 py-0.5 text-[11px] cursor-pointer opacity-50 hover:opacity-100 transition-opacity"
                    style={{
                      color: 'var(--hud-text-dim)',
                      border: '1px solid var(--hud-border)',
                      background: 'transparent',
                    }}
                  >
                    ↻ Regenerate
                  </button>
                </div>
              )}
            </div>
          )
        })
      )}
      <div ref={bottomRef} />
    </div>
  )
}
