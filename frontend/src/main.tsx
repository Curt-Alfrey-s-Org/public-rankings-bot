import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import '@alfa-ai/chat-widget/styles.css'
import './index.css'

// Stale deploy: old lazy chunk hashes 404; reload once so the browser fetches fresh index.html (Vite manual pattern).
window.addEventListener('vite:preloadError', (event: Event) => {
  event.preventDefault()
  const key = '__vite_chunk_reload__'
  const last = Number(sessionStorage.getItem(key) || '0')
  if (Date.now() - last > 10_000) {
    sessionStorage.setItem(key, String(Date.now()))
    window.location.reload()
  }
})

// Suppress React Router Future Flag Warning since we've enabled the flags
const originalWarn = console.warn
console.warn = (...args) => {
  if (args[0]?.includes?.('React Router Future Flag Warning')) {
    return // Suppress this specific warning
  }
  originalWarn.apply(console, args)
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
