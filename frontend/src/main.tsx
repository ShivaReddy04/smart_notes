import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Self-hosted Inter (variable) — one import, all weights, no CDN. The font
// family it registers ('Inter Variable') is the first choice in --font-sans.
import '@fontsource-variable/inter/index.css'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
