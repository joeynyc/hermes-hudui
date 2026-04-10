import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'

export type ThemeId = 'ai' | 'blade-runner' | 'fsociety' | 'anime' | 'hermes-white'

interface ThemeContextValue {
  theme: ThemeId
  setTheme: (t: ThemeId) => void
  scanlines: boolean
  setScanlines: (s: boolean) => void
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: 'ai',
  setTheme: () => {},
  scanlines: false,
  setScanlines: () => {},
})

export const THEMES: { id: ThemeId; label: string; icon: string }[] = [
  { id: 'ai', label: 'Neural Awakening', icon: '◆' },
  { id: 'blade-runner', label: 'Blade Runner', icon: '◈' },
  { id: 'fsociety', label: 'fsociety', icon: '▣' },
  { id: 'anime', label: 'Anime', icon: '◎' },
  { id: 'hermes-white', label: 'Hermes White', icon: '◇' },
]

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>(() => {
    return (localStorage.getItem('hud-theme') as ThemeId) || 'ai'
  })
  const [scanlines, setScanlinesState] = useState(() => {
    return localStorage.getItem('hud-scanlines') === 'true'
  })

  const setTheme = (t: ThemeId) => {
    setThemeState(t)
    localStorage.setItem('hud-theme', t)
  }

  const setScanlines = (s: boolean) => {
    setScanlinesState(s)
    localStorage.setItem('hud-scanlines', String(s))
  }

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  return (
    <ThemeContext.Provider value={{ theme, setTheme, scanlines, setScanlines }}>
      <div className={scanlines ? 'scanlines' : ''} style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {children}
      </div>
    </ThemeContext.Provider>
  )
}

export const useTheme = () => useContext(ThemeContext)
