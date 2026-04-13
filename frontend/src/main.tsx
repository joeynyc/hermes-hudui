import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { I18nProvider } from './i18n'

// Set default theme before render to avoid flash
if (!document.documentElement.getAttribute('data-theme')) {
  document.documentElement.setAttribute('data-theme', localStorage.getItem('hud-theme') || 'ai')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nProvider>
      <App />
    </I18nProvider>
  </StrictMode>,
)
