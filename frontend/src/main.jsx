import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import ChamadoPublico from './ChamadoPublico.jsx'
import './styles.css'

if ('serviceWorker' in navigator && location.protocol === 'https:') {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/contingencia-sw.js').catch(() => {})
  })
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {window.location.pathname === '/chamado' ? <ChamadoPublico /> : <App />}
  </React.StrictMode>,
)
