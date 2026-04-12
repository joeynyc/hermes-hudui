import { useState } from 'react'
import type { ToolCall } from '../../hooks/useChat'

interface ToolCallCardProps {
  tool: ToolCall
}

export default function ToolCallCard({ tool }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false)

  const isRunning = tool.status === 'running'
  const isError = tool.status === 'error'

  return (
    <div
      className="my-2 text-[12px]"
      style={{
        borderLeft: `2px solid ${isRunning ? 'var(--hud-warning)' : isError ? 'var(--hud-error)' : 'var(--hud-success)'}`,
        background: 'var(--hud-bg-surface)',
      }}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-2 py-1.5 flex items-center justify-between cursor-pointer text-left"
        style={{ color: 'var(--hud-text)' }}
      >
        <div className="flex items-center gap-2">
          <span
            style={{
              color: isRunning ? 'var(--hud-warning)' : isError ? 'var(--hud-error)' : 'var(--hud-success)',
            }}
          >
            {isRunning ? '▸' : isError ? '✗' : '✓'}
          </span>
          <span className="font-bold">{tool.name}</span>
          {isRunning && (
            <span className="animate-pulse" style={{ color: 'var(--hud-warning)' }}>
              running...
            </span>
          )}
        </div>
        <span style={{ color: 'var(--hud-text-dim)' }}>{expanded ? '▼' : '▶'}</span>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-2 pb-2 space-y-2">
          {/* Arguments */}
          <div>
            <div style={{ color: 'var(--hud-text-dim)' }} className="mb-0.5">
              arguments:
            </div>
            <pre
              className="p-1.5 overflow-x-auto text-[11px]"
              style={{
                background: 'var(--hud-bg-hover)',
                color: 'var(--hud-text)',
                fontFamily: 'monospace',
              }}
            >
              {JSON.stringify(tool.arguments, null, 2)}
            </pre>
          </div>

          {/* Result or Error */}
          {(tool.result || tool.error) && (
            <div>
              <div
                style={{
                  color: tool.error ? 'var(--hud-error)' : 'var(--hud-success)',
                }}
                className="mb-0.5"
              >
                {tool.error ? 'error:' : 'result:'}
              </div>
              <pre
                className="p-1.5 overflow-x-auto text-[11px]"
                style={{
                  background: 'var(--hud-bg-hover)',
                  color: 'var(--hud-text)',
                  fontFamily: 'monospace',
                }}
              >
                {tool.error || JSON.stringify(tool.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
