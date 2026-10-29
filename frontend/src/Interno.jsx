import { Fragment, useEffect, useRef, useState } from 'react'
import { messageDay, messageHour } from './dates.js'

function SetorIcon({ nome }) {
  const comum = { width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' }
  if (nome.toLowerCase().includes('estoque')) return <svg {...comum}><path d="M3 7 12 3l9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10"/></svg>
  if (nome.toLowerCase().includes('garantia')) return <svg {...comum}><path d="M12 2 20 5v6c0 5-3.5 8.5-8 11-4.5-2.5-8-6-8-11V5zM9 12l2 2 4-4"/></svg>
  if (nome.toLowerCase().includes('venda')) return <svg {...comum}><path d="M3 4h8l10 10-7 7L4 11V4zM7.5 7.5h.01"/></svg>
  return <svg {...comum}><circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2M17 5a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5v1"/></svg>
}

async function leitura(url) {
  const resposta = await fetch(url, { credentials: 'same-origin' })
  if (!resposta.ok) throw new Error('Não foi possível carregar o chat interno.')
  return resposta.json()
}

export default function Interno({ me, abrirColegaId, onOpen }) {
  const [setores, setSetores] = useState([])
  const [aberto, setAberto] = useState(null)
  const [colega, setColega] = useState(null)
  const [mensagens, setMensagens] = useState([])
  const [texto, setTexto] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [temAnteriores, setTemAnteriores] = useState(false)
  const rolagem = useRef(null)
  const primeiroId = useRef(null)
  const carregando = useRef(false)
  const ultimoVisivel = useRef(null)
  const colegaAtual = setores.flatMap(setor => setor.pessoas).find(pessoa => pessoa.id === colega?.id) || colega

  useEffect(() => {
    const atualizar = () => leitura('/api/interno/setores').then(setSetores).catch(falha => setErro(falha.message))
    atualizar()
    const intervalo = setInterval(atualizar, 3000)
    return () => clearInterval(intervalo)
  }, [])

  useEffect(() => {
    if (!colega) return
    setMensagens([]); setTemAnteriores(false); primeiroId.current = null; ultimoVisivel.current = null
    const atualizar = () => leitura(`/api/interno/mensagens/${colega.id}`).then(novas => {
      setMensagens(anteriores => {
        if (!anteriores.length) {
          setTemAnteriores(novas.length === 50)
          primeiroId.current = novas[0]?.id || null
          return novas
        }
        const ids = new Set(anteriores.map(item => item.id))
        return [...anteriores, ...novas.filter(item => !ids.has(item.id))].sort((a, b) => a.id - b.id)
      })
    }).catch(falha => setErro(falha.message))
    atualizar()
    const intervalo = setInterval(atualizar, 3000)
    return () => clearInterval(intervalo)
  }, [colega?.id])
  useEffect(() => {
    const ultimo = mensagens.at(-1)?.id
    if (ultimo && ultimo !== ultimoVisivel.current) {
      ultimoVisivel.current = ultimo
      requestAnimationFrame(() => { if (rolagem.current) rolagem.current.scrollTop = rolagem.current.scrollHeight })
    }
  }, [mensagens.at(-1)?.id])
  async function carregarAnteriores() {
    if (!colega || !temAnteriores || !primeiroId.current || carregando.current) return
    carregando.current = true
    const area = rolagem.current
    const altura = area?.scrollHeight || 0
    try {
      const antigas = await leitura(`/api/interno/mensagens/${colega.id}?antes=${primeiroId.current}`)
      setTemAnteriores(antigas.length === 50)
      if (antigas.length) {
        primeiroId.current = antigas[0].id
        setMensagens(atuais => {
          const ids = new Set(atuais.map(item => item.id))
          return [...antigas.filter(item => !ids.has(item.id)), ...atuais]
        })
        requestAnimationFrame(() => { if (area) area.scrollTop += area.scrollHeight - altura })
      }
    } catch (falha) { setErro(falha.message) }
    finally { carregando.current = false }
  }
  useEffect(() => {
    if (colega && mensagens.length) onOpen(colega.id)
  }, [colega?.id, mensagens.length])

  useEffect(() => {
    if (!abrirColegaId || !setores.length) return
    const pessoa = setores.flatMap(setor => setor.pessoas).find(item => item.id === abrirColegaId)
    if (pessoa) {
      setColega(pessoa)
      const setor = setores.find(item => item.pessoas.some(usuario => usuario.id === pessoa.id))
      setAberto(setor?.id || null)
      onOpen(pessoa.id)
    }
  }, [abrirColegaId, setores.length])

  async function enviar(evento) {
    evento.preventDefault()
    if (!colega || !texto.trim() || enviando) return
    setEnviando(true); setErro('')
    try {
      const resposta = await fetch(`/api/interno/mensagens/${colega.id}`, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
        body: new URLSearchParams({ texto: texto.trim() }),
      })
      if (!resposta.ok) throw new Error('Não foi possível enviar a mensagem.')
      setTexto('')
      const novas = await leitura(`/api/interno/mensagens/${colega.id}`)
      setMensagens(atuais => [...atuais, ...novas.filter(item => !atuais.some(atual => atual.id === item.id))].sort((a, b) => a.id - b.id))
    } catch (falha) { setErro(falha.message) }
    finally { setEnviando(false) }
  }

  return <div className="interno-page">
    <div className="page-intro"><div><div className="eyebrow">EQUIPE</div><h1>Chat interno</h1><p>Converse com a equipe sem usar o WhatsApp. Colegas offline também recebem mensagens.</p></div><span className="demo-pill">INTERNO</span></div>
    {erro && <div className="toast toast-error" role="alert">{erro}</div>}
    <div className="interno-grid">
      <aside className="surface interno-directory"><h2>Setores</h2><p className="muted">Abra um setor para ver todos os usuários cadastrados.</p>
        {setores.map(setor => <div key={setor.id} className="interno-sector">
          <button className="interno-sector-button" onClick={() => setAberto(aberto === setor.id ? null : setor.id)} aria-expanded={aberto === setor.id}>
            <span className="interno-sector-title"><span className="interno-sector-icon"><SetorIcon nome={setor.nome}/></span><span>{setor.nome}<small>{setor.pessoas.length} pessoas</small></span></span><span aria-hidden="true">{aberto === setor.id ? '▾' : '▸'}</span>
          </button>
          {aberto === setor.id && <div className="interno-people">{setor.pessoas.length ? setor.pessoas.map(pessoa =>
            <button key={pessoa.id} className={colega?.id === pessoa.id ? 'selected' : ''} disabled={!pessoa.ativo} onClick={() => { setColega(pessoa); setMensagens([]); setErro(''); onOpen(pessoa.id) }}>
              <span className={pessoa.ativo && pessoa.online ? 'status-dot' : 'status-dot status-dot-muted'} />
              <span>{pessoa.nome}<small>{!pessoa.ativo ? 'Inativo' : pessoa.online ? 'Online' : 'Offline'}</small></span>
            </button>) : <small>Nenhum usuário neste setor.</small>}</div>}
        </div>)}
      </aside>
      <section className="surface interno-chat">
        {!colega ? <div className="chat-placeholder"><h2>Escolha um colega</h2><p>Abra um setor e selecione alguém da equipe.</p></div> : <>
          <header><h2>{colega.nome}</h2><span className={colegaAtual?.online ? 'badge badge-open' : 'badge badge-closed'}>{colegaAtual?.online ? 'Online' : 'Offline'}</span></header>
          <div className="interno-messages" ref={rolagem} onScroll={evento => { if (evento.currentTarget.scrollTop < 40) carregarAnteriores() }}>
            {temAnteriores && <button className="older-messages" onClick={carregarAnteriores}>Carregar mensagens anteriores</button>}
            {mensagens.length ? mensagens.map((mensagem, index) => <Fragment key={mensagem.id}>
            {(index === 0 || messageDay(mensagem.criada_em) !== messageDay(mensagens[index - 1].criada_em)) && <div className="day-divider"><span>{messageDay(mensagem.criada_em)}</span></div>}
            <div className={mensagem.remetente_id === me.id ? 'interno-message mine' : 'interno-message'}>
              <strong>{mensagem.remetente_id === me.id ? 'Você' : colega.nome}</strong>
              <p>{mensagem.texto}</p><time>{messageHour(mensagem.criada_em)}</time>
            </div></Fragment>) : <p className="muted">Nenhuma mensagem nesta conversa.</p>}</div>
          <form onSubmit={enviar}><input value={texto} onChange={evento => setTexto(evento.target.value)} placeholder="Escreva uma mensagem interna..." maxLength="4000" required /><button className="button button-primary" disabled={enviando || !texto.trim()}>Enviar</button></form>
        </>}
      </section>
    </div>
  </div>
}
