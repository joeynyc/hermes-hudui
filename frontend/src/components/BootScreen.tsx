import { useState, useEffect } from 'react'
import { useLocale } from '../lib/i18n'

const HERMES_ASCII = [
  ' ██╗  ██╗███████╗██████╗ ███╗   ███╗███████╗███████╗',
  ' ██║  ██║██╔════╝██╔══██╗████╗ ████║██╔════╝██╔════╝',
  ' ███████║█████╗  ██████╔╝██╔████╔██║█████╗  ███████╗',
  ' ██╔══██║██╔══╝  ██╔══██╗██║╚██╔╝██║██╔══╝  ╚════██║',
  ' ██║  ██║███████╗██║  ██║██║ ╚═╝ ██║███████╗███████║',
  ' ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝',
]

interface BootScreenProps {
  onComplete: () => void
}

export default function BootScreen({ onComplete }: BootScreenProps) {
  const { t } = useLocale()
  const [visibleLines, setVisibleLines] = useState(0)
  const [asciiVisible, setAsciiVisible] = useState(false)
  const [fadeOut, setFadeOut] = useState(false)
  const [skipped, setSkipped] = useState(false)

  const BOOT_LINES_KEYS = [
    'boot.title', '', 'boot.initConsciousness', 'boot.readStateDb',
    'boot.scanMemory', 'boot.indexSkills', 'boot.checkHealth',
    'boot.profileAgents', '', 'boot.quote', '', 'boot.systemsReady',
  ]

  useEffect(() => {
    const asciiTimer = setTimeout(() => setAsciiVisible(true), 200)
    const lineTimers = BOOT_LINES_KEYS.map((_, i) =>
      setTimeout(() => setVisibleLines(i + 1), 600 + i * 100)
    )
    const fadeTimer = setTimeout(() => setFadeOut(true), 600 + BOOT_LINES_KEYS.length * 100 + 400)
    const completeTimer = setTimeout(onComplete, 600 + BOOT_LINES_KEYS.length * 100 + 800)

    return () => {
      clearTimeout(asciiTimer)
      lineTimers.forEach(clearTimeout)
      clearTimeout(fadeTimer)
      clearTimeout(completeTimer)
    }
  }, [onComplete])

  const handleSkip = () => {
    if (!skipped) {
      setSkipped(true)
      onComplete()
    }
  }

  return (
    <div
      className="fixed inset-0 flex flex-col items-center justify-center z-50 transition-opacity duration-500 cursor-pointer select-none"
      style={{
        background: 'var(--hud-bg-deep)',
        opacity: fadeOut ? 0 : 1,
      }}
      onClick={handleSkip}
    >
      {/* ASCII logo */}
      <pre
        className="gradient-text text-[8px] sm:text-[13px] leading-tight mb-4 sm:mb-6 transition-opacity duration-300 text-center overflow-hidden"
        style={{
          opacity: asciiVisible ? 1 : 0,
          maxWidth: '90vw',
          whiteSpace: 'pre',
        }}
      >
        {HERMES_ASCII.join('\n')}
      </pre>

      {/* Boot text */}
      <div className="text-[13px] w-[90vw] max-w-[400px] px-4">
        {BOOT_LINES_KEYS.slice(0, visibleLines).map((key, i) => {
          const text = key === '' ? '' : t(key)
          const isQuote = key === 'boot.quote'
          const isReady = key === 'boot.systemsReady'
          const isTitle = key === 'boot.title'
          return (
            <div key={i} className="py-0.5" style={{
              color: isQuote ? 'var(--hud-accent)' :
                     isReady ? 'var(--hud-success)' :
                     isTitle ? 'var(--hud-primary)' :
                     'var(--hud-text-dim)',
              fontStyle: isQuote ? 'italic' : 'normal',
            }}>
              {text}
              {i === visibleLines - 1 && (
                <span className="animate-pulse" style={{ color: 'var(--hud-primary)' }}>█</span>
              )}
            </div>
          )
        })}
      </div>

      <div className="absolute bottom-6 text-[13px]" style={{ color: 'var(--hud-text-dim)' }}>
        {t('boot.tapToSkip')}
      </div>
    </div>
  )
}
