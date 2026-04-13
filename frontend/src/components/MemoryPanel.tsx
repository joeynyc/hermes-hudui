import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import Panel, { CapacityBar } from './Panel'
import { useTranslation } from '../i18n'

async function memoryApi(method: string, body: Record<string, string>) {
  const res = await fetch('/api/memory', {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

function MemoryEntry({
  entry,
  target,
  onMutate,
}: {
  entry: any
  target: string
  onMutate: () => void
}) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const startEdit = () => {
    setEditText(entry.text)
    setEditing(true)
    setError('')
  }

  const cancelEdit = () => {
    setEditing(false)
    setError('')
  }

  const saveEdit = async () => {
    const trimmed = editText.trim()
    if (!trimmed || trimmed === entry.text) {
      cancelEdit()
      return
    }
    setBusy(true)
    setError('')
    try {
      await memoryApi('PUT', { target, old_text: entry.text, content: trimmed })
      setEditing(false)
      onMutate()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const deleteEntry = async () => {
    if (!confirming) {
      setConfirming(true)
      return
    }
    setBusy(true)
    setError('')
    try {
      await memoryApi('DELETE', { target, old_text: entry.text })
      onMutate()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
      setConfirming(false)
    }
  }

  return (
    <div
      className="text-[13px] py-1.5 px-2 group"
      style={{ background: 'var(--hud-bg-panel)', borderLeft: '2px solid var(--hud-border)' }}
    >
      <div className="flex justify-between mb-0.5">
        <span className="uppercase tracking-wider text-[13px] font-bold" style={{ color: 'var(--hud-primary)' }}>
          {entry.category}
        </span>
        <span className="flex items-center gap-1.5">
          {!editing && (
            <span className="opacity-0 group-hover:opacity-100 flex gap-1">
              <button
                onClick={startEdit}
                className="text-[11px] cursor-pointer px-1"
                style={{ color: 'var(--hud-primary)' }}
                disabled={busy}
              >
                {t('memory.edit')}
              </button>
              <button
                onClick={deleteEntry}
                onMouseLeave={() => setConfirming(false)}
                className="text-[11px] cursor-pointer px-1"
                style={{ color: 'var(--hud-error, #f44)' }}
                disabled={busy}
              >
                {confirming ? t('memory.confirmDelete') : t('memory.delete')}
              </button>
            </span>
          )}
          <span style={{ color: 'var(--hud-text-dim)' }}>{entry.char_count}c</span>
        </span>
      </div>

      {editing ? (
        <div>
          <textarea
            value={editText}
            onChange={e => setEditText(e.target.value)}
            className="w-full text-[13px] p-1.5 outline-none resize-y"
            style={{
              background: 'var(--hud-bg-deep)',
              border: '1px solid var(--hud-border)',
              color: 'var(--hud-text)',
              minHeight: '60px',
            }}
            autoFocus
          />
          <div className="flex gap-1 mt-1">
            <button
              onClick={saveEdit}
              disabled={busy}
              className="text-[11px] px-2 py-0.5 cursor-pointer"
              style={{ background: 'var(--hud-primary)', color: 'var(--hud-bg-deep)', border: 'none' }}
            >
              {busy ? '...' : t('memory.save')}
            </button>
            <button
              onClick={cancelEdit}
              disabled={busy}
              className="text-[11px] px-2 py-0.5 cursor-pointer"
              style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text-dim)', border: '1px solid var(--hud-border)' }}
            >
              {t('memory.cancel')}
            </button>
          </div>
          {error && <div className="text-[11px] mt-1" style={{ color: 'var(--hud-error, #f44)' }}>{error}</div>}
        </div>
      ) : (
        <div style={{ color: 'var(--hud-text)' }}>{entry.text}</div>
      )}
    </div>
  )
}

function AddEntryForm({ target, onMutate }: { target: string; onMutate: () => void }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async () => {
    const trimmed = text.trim()
    if (!trimmed) return
    setBusy(true)
    setError('')
    try {
      await memoryApi('POST', { target, content: trimmed })
      setText('')
      setOpen(false)
      onMutate()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="w-full text-[11px] py-1 mt-1 cursor-pointer"
        style={{ color: 'var(--hud-text-dim)', border: '1px dashed var(--hud-border)', background: 'transparent' }}
      >
        + {t('memory.addNew')}
      </button>
    )
  }

  return (
    <div className="mt-1">
      <textarea
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder={t('memory.addNew')}
        className="w-full text-[13px] p-1.5 outline-none resize-y"
        style={{
          background: 'var(--hud-bg-deep)',
          border: '1px solid var(--hud-border)',
          color: 'var(--hud-text)',
          minHeight: '50px',
        }}
        autoFocus
      />
      <div className="flex gap-1 mt-1">
        <button
          onClick={submit}
          disabled={busy || !text.trim()}
          className="text-[11px] px-2 py-0.5 cursor-pointer disabled:opacity-40"
          style={{ background: 'var(--hud-primary)', color: 'var(--hud-bg-deep)', border: 'none' }}
        >
          {busy ? '...' : t('memory.add')}
        </button>
        <button
          onClick={() => { setOpen(false); setText(''); setError('') }}
          className="text-[11px] px-2 py-0.5 cursor-pointer"
          style={{ background: 'var(--hud-bg-hover)', color: 'var(--hud-text-dim)', border: '1px solid var(--hud-border)' }}
        >
          {t('memory.cancel')}
        </button>
      </div>
      {error && <div className="text-[11px] mt-1" style={{ color: 'var(--hud-error, #f44)' }}>{error}</div>}
    </div>
  )
}

function MemoryEntries({ entries, target, onMutate }: { entries: any[]; target: string; onMutate: () => void }) {
  const { t } = useTranslation()
  if (!entries?.length) return <div className="text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>{t('memory.empty')}</div>

  return (
    <div className="space-y-1.5">
      {entries.map((e: any) => (
        <MemoryEntry key={e.text} entry={e} target={target} onMutate={onMutate} />
      ))}
    </div>
  )
}

export default function MemoryPanel() {
  const { t } = useTranslation()
  const { data, isLoading, mutate } = useApi('/memory', 30000)

  if (isLoading && !data) {
    return <Panel title={t('memory.title')} className="col-span-full"><div className="glow text-[13px] animate-pulse">{t('memory.loading')}</div></Panel>
  }

  const { memory, user } = data

  return (
    <>
      <Panel title={t('memory.title')} className="col-span-1">
        <CapacityBar value={memory?.total_chars || 0} max={memory?.max_chars || 2200} label="CAPACITY" />
        <div className="text-[13px] my-2" style={{ color: 'var(--hud-text-dim)' }}>
          {memory?.entry_count || 0} entries · {Object.entries(memory?.count_by_category || {}).map(([k,v]) => `${k}(${v})`).join(' ')}
        </div>
        <MemoryEntries entries={memory?.entries || []} target="memory" onMutate={mutate} />
        <AddEntryForm target="memory" onMutate={mutate} />
      </Panel>

      <Panel title="User Profile" className="col-span-1">
        <CapacityBar value={user?.total_chars || 0} max={user?.max_chars || 1375} label="CAPACITY" />
        <div className="text-[13px] my-2" style={{ color: 'var(--hud-text-dim)' }}>
          {user?.entry_count || 0} entries
        </div>
        <MemoryEntries entries={user?.entries || []} target="user" onMutate={mutate} />
        <AddEntryForm target="user" onMutate={mutate} />
      </Panel>
    </>
  )
}
