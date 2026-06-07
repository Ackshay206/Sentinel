import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import CallerApp from './CallerApp.tsx'

// ?caller=1 → the phone's caller-mic page; otherwise the victim dashboard.
const isCaller = new URLSearchParams(window.location.search).has('caller')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isCaller ? <CallerApp /> : <App />}
  </StrictMode>,
)
