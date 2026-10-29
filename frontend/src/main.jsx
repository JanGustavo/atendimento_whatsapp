import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import ChamadoPublico from './ChamadoPublico.jsx'
import './styles.css'

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {window.location.pathname === '/chamado' ? <ChamadoPublico /> : <App />}
  </React.StrictMode>,
)
