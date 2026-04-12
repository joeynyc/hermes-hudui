import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { LocaleProvider } from './lib/i18n'

// Set default theme before render to avoid flash
if (!document.documentElement.getAttribute('data-theme')) {
  document.documentElement.setAttribute('data-theme', localStorage.getItem('hud-theme') || 'ai')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LocaleProvider>
      <App />
    </LocaleProvider>
  </StrictMode>,
)
