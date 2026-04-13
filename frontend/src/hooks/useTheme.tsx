import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'

export type ThemeId = 'ai' | 'blade-runner' | 'fsociety' | 'anime'

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

export const THEMES: { id: ThemeId; labelKey: string; icon: string }[] = [
  { id: 'ai', labelKey: 'theme.neuralAwakening', icon: '◆' },
  { id: 'blade-runner', labelKey: 'theme.bladeRunner', icon: '◈' },
  { id: 'fsociety', labelKey: 'theme.fsociety', icon: '▣' },
  { id: 'anime', labelKey: 'theme.anime', icon: '◎' },
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
