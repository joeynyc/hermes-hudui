import { useEffect, useRef } from 'react'
import { useLocale } from '../../lib/i18n'
import type { ChatMessage } from '../../hooks/useChat'
import MessageBubble from './MessageBubble'
import ToolCallCard from './ToolCallCard'
import ReasoningBlock from './ReasoningBlock'

interface MessageThreadProps {
  messages: ChatMessage[]
}

export default function MessageThread({ messages }: MessageThreadProps) {
  const { t } = useLocale()
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
            <div className="text-[14px] mb-1">{t('chat.noMessagesYet')}</div>
            <div className="text-[12px]">{t('chat.startConversationBelow')}</div>
          </div>
        </div>
      ) : (
        messages.map((message) => (
          <div key={message.id}>
            {/* Reasoning block (if assistant message has reasoning) */}
            {message.role === 'assistant' && message.reasoning && (
              <ReasoningBlock content={message.reasoning} />
            )}

            {/* Tool calls (if any) */}
            {message.toolCalls && message.toolCalls.length > 0 && (
              <div className="my-1">
                {message.toolCalls.map((tool) => (
                  <ToolCallCard key={tool.id} tool={tool} />
                ))}
              </div>
            )}

            {/* Main message bubble */}
            <MessageBubble
              role={message.role}
              content={message.content}
              isStreaming={message.isStreaming}
            />
          </div>
        ))
      )}
      <div ref={bottomRef} />
    </div>
  )
}
