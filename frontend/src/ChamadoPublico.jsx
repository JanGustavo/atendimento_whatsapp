import React, { useEffect, useState } from 'react'
import { fetchApi } from './api.js'

const token = new URLSearchParams(window.location.search).get('token') || ''

export default function ChamadoPublico() {
  const [computadores, setComputadores] = useState([])
  const [computador, setComputador] = useState('')
  const [descricao, setDescricao] = useState('')
  const [erro, setErro] = useState('')
  const [chamado, setChamado] = useState(null)
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    fetchApi(`/api/chamado/computadores?token=${encodeURIComponent(token)}`, { cache: 'no-store' })
      .then(async (resposta) => {
        if (!resposta.ok)
          throw new Error(
            resposta.status === 403
              ? 'Atalho inválido. Peça um novo link à administração.'
              : 'Não foi possível carregar os computadores.',
          )
        return resposta.json()
      })
      .then((lista) => {
        setComputadores(lista)
        setComputador(String(lista[0]?.id || ''))
      })
      .catch((falha) => setErro(falha.message))
  }, [])

  async function enviar(evento) {
    evento.preventDefault()
    setErro('')
    setEnviando(true)
    const dados = new URLSearchParams({
      token,
      computador_id: computador,
      descricao: descricao.trim(),
    })
    try {
      const resposta = await fetchApi('/api/chamado', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: dados,
      })
      const resultado = await resposta.json()
      if (!resposta.ok) throw new Error(resultado.detail || 'Não foi possível abrir o chamado.')
      setChamado(resultado.id)
      setDescricao('')
    } catch (falha) {
      setErro(falha.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="public-ticket-layout">
      <main className="public-ticket-card">
        <img src="/static/fortgiro-logo.png" alt="FortGiro" />
        <div className="eyebrow">SUPORTE INTERNO</div>
        <h1>Precisa de ajuda?</h1>
        <p>Descreva o problema para a equipe de suporte.</p>
        {chamado && (
          <div className="public-ticket-success" role="status">
            Chamado #{chamado} registrado. A equipe já pode acompanhá-lo.
          </div>
        )}
        {erro && (
          <div className="form-error" role="alert">
            {erro}
          </div>
        )}
        <form onSubmit={enviar}>
          <label>
            Computador
            <select
              value={computador}
              onChange={(evento) => setComputador(evento.target.value)}
              required
              disabled={!computadores.length}
            >
              {computadores.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.nome}
                </option>
              ))}
            </select>
          </label>
          <label>
            O que aconteceu?
            <textarea
              value={descricao}
              onChange={(evento) => setDescricao(evento.target.value)}
              minLength="3"
              maxLength="4000"
              rows="5"
              required
              placeholder="Explique o problema para facilitar o atendimento"
            />
          </label>
          <button className="button button-primary" disabled={enviando || !computadores.length}>
            {enviando ? 'Enviando...' : 'Abrir chamado'}
          </button>
        </form>
      </main>
    </div>
  )
}
