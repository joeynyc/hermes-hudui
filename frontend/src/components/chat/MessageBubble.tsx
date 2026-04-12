import { useState } from 'react'
import { useLocale } from '../../lib/i18n'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import 'highlight.js/styles/atom-one-dark.css'

interface MessageBubbleProps {
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  isStreaming?: boolean
}

function CopyButton({ text }: { text: string }) {
  const { t } = useLocale()
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback for environments without clipboard API
      const el = document.createElement('textarea')
      el.value = text
      document.body.appendChild(el)
      el.select()
      document.execCommand('copy')
      document.body.removeChild(el)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 px-2 py-0.5 text-[11px] opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
      style={{
        background: copied ? 'var(--hud-success)' : 'var(--hud-bg-hover)',
        color: copied ? 'var(--hud-bg-deep)' : 'var(--hud-text-dim)',
        border: '1px solid var(--hud-border)',
      }}
    >
      {copied ? t('message.copied') : t('message.copyToClipboard')}
    </button>
  )
}

export default function MessageBubble({ role, content, isStreaming }: MessageBubbleProps) {
  const isUser = role === 'user'
  const isAssistant = role === 'assistant'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
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
        }}
      >
        {isUser ? (
          // User messages: plain text, preserve whitespace
          <span style={{ whiteSpace: 'pre-wrap' }}>{content}</span>
        ) : (
          // Assistant messages: full markdown rendering
          <div className="prose-hud">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
              components={{
                // Inline code — styled, no copy button
                code({ className, children, ...props }) {
                  const isBlock = className?.includes('language-')
                  if (isBlock) {
                    // Block code: just render the code element (pre wrapper handles copy)
                    return <code className={className} {...props}>{children}</code>
                  }
                  return (
                    <code
                      style={{
                        background: 'var(--hud-bg-deep)',
                        color: 'var(--hud-primary)',
                        padding: '1px 4px',
                        fontSize: '0.85em',
                        fontFamily: 'monospace',
                      }}
                      {...props}
                    >
                      {children}
                    </code>
                  )
                },
                // Pre block — wraps code block, provides copy button via group hover
                pre({ children, node, ...props }) {
                  // Extract raw text from AST for clipboard
                  const rawText: string = (() => {
                    const codeNode = (node as any)?.children?.[0]
                    if (codeNode?.type === 'element' && codeNode?.children?.[0]?.type === 'text') {
                      return codeNode.children[0].value ?? ''
                    }
                    return ''
                  })()

                  return (
                    <div className="relative group my-2">
                      <CopyButton text={rawText} />
                      <pre
                        style={{
                          background: 'var(--hud-bg-deep)',
                          border: '1px solid var(--hud-border)',
                          borderRadius: '2px',
                          padding: '0.75rem',
                          overflowX: 'auto',
                          fontSize: '13px',
                          margin: 0,
                        }}
                        {...props}
                      >
                        {children}
                      </pre>
                    </div>
                  )
                },
                // Style blockquotes
                blockquote({ children, ...props }) {
                  return (
                    <blockquote
                      style={{
                        borderLeft: '3px solid var(--hud-primary)',
                        paddingLeft: '0.75rem',
                        margin: '0.5rem 0',
                        color: 'var(--hud-text-dim)',
                        fontStyle: 'italic',
                      }}
                      {...props}
                    >
                      {children}
                    </blockquote>
                  )
                },
                // Style links
                a({ children, href, ...props }) {
                  return (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: 'var(--hud-primary)', textDecoration: 'underline' }}
                      {...props}
                    >
                      {children}
                    </a>
                  )
                },
                // Style tables
                table({ children, ...props }) {
                  return (
                    <div style={{ overflowX: 'auto', margin: '0.5rem 0' }}>
                      <table
                        style={{
                          borderCollapse: 'collapse',
                          width: '100%',
                          fontSize: '13px',
                        }}
                        {...props}
                      >
                        {children}
                      </table>
                    </div>
                  )
                },
                th({ children, ...props }) {
                  return (
                    <th
                      style={{
                        border: '1px solid var(--hud-border)',
                        padding: '4px 8px',
                        background: 'var(--hud-bg-surface)',
                        color: 'var(--hud-primary)',
                        textAlign: 'left',
                      }}
                      {...props}
                    >
                      {children}
                    </th>
                  )
                },
                td({ children, ...props }) {
                  return (
                    <td
                      style={{
                        border: '1px solid var(--hud-border)',
                        padding: '4px 8px',
                      }}
                      {...props}
                    >
                      {children}
                    </td>
                  )
                },
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}
        {isStreaming && (
          <span className="inline-block ml-1 animate-pulse" style={{ color: 'var(--hud-primary)' }}>
            ●
          </span>
        )}
      </div>
    </div>
  )
}
