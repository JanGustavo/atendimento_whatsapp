import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { messageDay, messageHour } from './dates.js'
import { converterWebp } from './images.js'
import ModalImagem from './ModalImagem.jsx'

const BASE = '/api/interno'
const PAGINA = 50
const INTERVALO_MS = 3000
const JANELA_AGRUPAR_MS = 5 * 60 * 1000
const LIMITE_ORIGEM = 12 * 1024 * 1024

/* ───────────── API ───────────── */

async function leitura(url, signal) {
  const resposta = await fetch(url, { credentials: 'same-origin', signal })
  if (!resposta.ok) throw new Error('Não foi possível carregar o chat interno.')
  return resposta.json()
}

async function postar(url, init, mensagemPadrao) {
  const resposta = await fetch(url, { method: 'POST', credentials: 'same-origin', ...init })
  if (resposta.ok) return
  const corpo = await resposta.json().catch(() => ({}))
  throw new Error(typeof corpo.detail === 'string' ? corpo.detail : mensagemPadrao)
}

function rotasDe(grupo, colega) {
  if (grupo) return { mensagens: `grupos/${grupo.id}/mensagens`, imagens: `grupos/${grupo.id}/imagens` }
  if (colega) return { mensagens: `mensagens/${colega.id}`, imagens: `mensagens/${colega.id}/imagem` }
  return null
}

/* ───────────── utilidades ───────────── */

const iniciais = nome => (nome || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(parte => parte[0].toUpperCase()).join('')
const plural = (n, singular, pluralForma) => `${n} ${n === 1 ? singular : pluralForma}`
const proximos = (a, b) => { const dif = new Date(b) - new Date(a); return dif >= 0 && dif < JANELA_AGRUPAR_MS }

function mesclar(atuais, novas) {
  const ids = new Set(atuais.map(item => item.id))
  const extras = novas.filter(item => !ids.has(item.id))
  return extras.length ? [...atuais, ...extras].sort((a, b) => a.id - b.id) : atuais
}

/* ───────────── ícones ───────────── */

const ICONES = {
  estoque: <path d="M3 7 12 3l9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10" />,
  garantia: <path d="M12 2 20 5v6c0 5-3.5 8.5-8 11-4.5-2.5-8-6-8-11V5zM9 12l2 2 4-4" />,
  vendas: <path d="M3 4h8l10 10-7 7L4 11V4zM7.5 7.5h.01" />,
  equipe: <><circle cx="9" cy="8" r="3" /><path d="M3 20v-2a6 6 0 0 1 12 0v2M17 5a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5v1" /></>,
  clipe: <path d="m21 11.5-8.6 8.6a5 5 0 0 1-7.1-7.1l8.6-8.6a3.3 3.3 0 0 1 4.7 4.7l-8.6 8.6a1.7 1.7 0 0 1-2.4-2.4l7.9-7.9" />,
  enviar: <path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" />,
  buscar: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
  voltar: <path d="m15 18-6-6 6-6" />,
  seta: <path d="m9 6 6 6-6 6" />,
  fechar: <path d="M6 6l12 12M18 6 6 18" />,
  conversa: <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" />,
}

function Icone({ nome, tamanho = 20, className }) {
  return (
    <svg className={className} width={tamanho} height={tamanho} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICONES[nome]}
    </svg>
  )
}

function iconeDoSetor(nome = '') {
  const n = nome.toLowerCase()
  if (n.includes('estoque')) return 'estoque'
  if (n.includes('garantia')) return 'garantia'
  if (n.includes('venda')) return 'vendas'
  return 'equipe'
}

function Avatar({ nome, fotoUrl, grande }) {
  return <span className={grande ? 'conversation-avatar large' : 'conversation-avatar'} aria-hidden="true">{fotoUrl ? <img className="int-avatar-photo" src={fotoUrl} alt="" /> : iniciais(nome)}</span>
}

/* ───────────── dados ───────────── */

function useSetores(onErro) {
  const [setores, setSetores] = useState([])
  useEffect(() => {
    let ativo = true
    const atualizar = () => leitura(`${BASE}/setores`)
      .then(novos => ativo && setSetores(atuais => (JSON.stringify(atuais) === JSON.stringify(novos) ? atuais : novos)))
      .catch(falha => ativo && onErro(falha.message))
    atualizar()
    const id = setInterval(atualizar, INTERVALO_MS)
    return () => { ativo = false; clearInterval(id) }
  }, [onErro])
  return setores
}

function useMensagens(caminho, onErro) {
  const [mensagens, setMensagens] = useState([])
  const [temAnteriores, setTemAnteriores] = useState(false)
  const ciclo = useRef(0)
  const requisicao = useRef(null)
  const requisicaoAnteriores = useRef(null)
  const primeiroId = useRef(null)
  const primeiraCarga = useRef(true)
  const buscandoAnteriores = useRef(false)

  const atualizar = useCallback(async (forcado = false) => {
    if (!caminho) return
    const cicloAtual = ciclo.current
    if (requisicao.current) {
      if (!forcado) return
      requisicao.current.abort()
      requisicao.current = null
    }
    const controlador = new AbortController()
    requisicao.current = controlador
    try {
      const novas = await leitura(`${BASE}/${caminho}`, controlador.signal)
      if (ciclo.current !== cicloAtual) return
      if (primeiraCarga.current) {
        primeiraCarga.current = false
        primeiroId.current = novas[0]?.id ?? null
        setTemAnteriores(novas.length === PAGINA)
        setMensagens(novas)
      } else {
        setMensagens(atuais => mesclar(atuais, novas))
      }
    } catch (falha) {
      if (falha.name !== 'AbortError' && ciclo.current === cicloAtual) onErro(falha.message)
    } finally {
      if (requisicao.current === controlador) requisicao.current = null
    }
  }, [caminho, onErro])

  useEffect(() => {
    ciclo.current += 1
    const cicloAtual = ciclo.current
    requisicao.current?.abort()
    requisicao.current = null
    requisicaoAnteriores.current?.abort()
    requisicaoAnteriores.current = null
    setMensagens([])
    setTemAnteriores(false)
    primeiroId.current = null
    primeiraCarga.current = true
    buscandoAnteriores.current = false
    if (!caminho) return
    atualizar(true)
    const id = setInterval(() => atualizar(false), INTERVALO_MS)
    return () => {
      clearInterval(id)
      if (ciclo.current === cicloAtual) {
        requisicao.current?.abort()
        requisicao.current = null
        requisicaoAnteriores.current?.abort()
        requisicaoAnteriores.current = null
      }
    }
  }, [caminho, atualizar])

  const carregarAnteriores = useCallback(async () => {
    if (!caminho || !temAnteriores || !primeiroId.current || buscandoAnteriores.current) return false
    buscandoAnteriores.current = true
    const cicloAtual = ciclo.current
    const controlador = new AbortController()
    requisicaoAnteriores.current = controlador
    try {
      const antigas = await leitura(`${BASE}/${caminho}?antes=${primeiroId.current}`, controlador.signal)
      if (ciclo.current !== cicloAtual) return false
      setTemAnteriores(antigas.length === PAGINA)
      if (!antigas.length) return false
      primeiroId.current = antigas[0].id
      setMensagens(atuais => mesclar(atuais, antigas))
      return true
    } catch (falha) {
      if (falha.name !== 'AbortError' && ciclo.current === cicloAtual) onErro(falha.message)
      return false
    } finally {
      if (requisicaoAnteriores.current === controlador) requisicaoAnteriores.current = null
      buscandoAnteriores.current = false
    }
  }, [caminho, temAnteriores, onErro])

  return { mensagens, temAnteriores, atualizar, carregarAnteriores }
}

/* ───────────── diretório (coluna esquerda) ───────────── */

function Diretorio({ setores, conversas, aberto, onAlternar, colegaId, grupoId, onPessoa, onGrupo }) {
  const [busca, setBusca] = useState('')
  const termo = busca.trim().toLowerCase()
  const totalOnline = setores.reduce((soma, setor) => soma + setor.pessoas.filter(p => p.ativo && p.online).length, 0)

  const visiveis = useMemo(() => setores
    .map(setor => {
      const porSetor = setor.nome.toLowerCase().includes(termo)
      const pessoas = !termo || porSetor ? setor.pessoas : setor.pessoas.filter(p => p.nome.toLowerCase().includes(termo))
      return { setor, pessoas }
    })
    .filter(({ setor, pessoas }) => !termo || pessoas.length || setor.nome.toLowerCase().includes(termo)), [setores, termo])

  return (
    <aside className="conversation-pane" aria-label="Equipe">
      <div className="pane-heading">
        <h2>Equipe</h2>
        <span className="count-chip">{totalOnline} online</span>
      </div>
      <label className="search-box">
        <Icone nome="buscar" tamanho={16} />
        <input type="search" value={busca} onChange={e => setBusca(e.target.value)} placeholder="Buscar pessoa ou setor" aria-label="Buscar pessoa ou setor" />
      </label>

      <div className="conversation-items">
        {conversas.length > 0 && <section className="int-recents"><h3>Conversas recentes</h3>
          {conversas.map(item => <button type="button" key={`${item.tipo}-${item.alvo_id}`}
            className={`conversation-item int-person${(item.tipo === 'grupo' ? grupoId === item.alvo_id : colegaId === item.alvo_id) ? ' selected' : ''}`}
            onClick={() => (item.tipo === 'grupo'
              ? onGrupo(setores.find(setor => setor.id === item.alvo_id) || { id: item.alvo_id, nome: item.nome })
              : onPessoa(setores.flatMap(setor => setor.pessoas).find(pessoa => pessoa.id === item.alvo_id) || { id: item.alvo_id, nome: item.nome, foto_url: item.foto_url, ativo: true }))}>
            {item.tipo === 'grupo'
              ? <span className="conversation-avatar" aria-hidden="true"><Icone nome="equipe" tamanho={18} /></span>
              : <Avatar nome={item.nome} fotoUrl={item.foto_url} />}
            <span className="conversation-item-main"><strong>{item.tipo === 'grupo' ? `Grupo · ${item.nome}` : item.nome}</strong>
              <small className="int-preview">{item.ultimo_remetente ? `${item.ultimo_remetente}: ` : ''}{item.ultima_previa || 'Conversa sem mensagens'}</small></span>
            <span className="conversation-item-meta">{item.ultima_em && <time>{messageHour(item.ultima_em)}</time>}
              {item.nao_lidas > 0 && <b className="nav-count">{item.nao_lidas > 99 ? '99+' : item.nao_lidas}</b>}</span>
          </button>)}
        </section>}
        {visiveis.map(({ setor, pessoas }) => {
          const expandido = Boolean(termo) || aberto === setor.id
          const online = setor.pessoas.filter(p => p.ativo && p.online).length
          return (
            <section key={setor.id}>
              <button type="button" className="int-sector-button" aria-expanded={expandido} onClick={() => onAlternar(setor.id)}>
                <span className="int-sector-icon"><Icone nome={iconeDoSetor(setor.nome)} tamanho={18} /></span>
                <span className="int-sector-text">
                  <strong>{setor.nome}</strong>
                  <small>{online} online · {plural(setor.total_pessoas, 'pessoa', 'pessoas')}</small>
                </span>
                <Icone nome="seta" tamanho={16} className="int-chevron" />
              </button>

              {expandido && (
                <ul className="int-people">
                  {setor.grupo_ativo && (
                    <li>
                      <button type="button" className={grupoId === setor.id ? 'conversation-item int-person selected' : 'conversation-item int-person'} onClick={() => onGrupo(setor)}>
                        <span className="conversation-avatar" aria-hidden="true"><Icone nome={iconeDoSetor(setor.nome)} tamanho={18} /></span>
                        <span className="conversation-item-main"><strong>Grupo · {setor.nome}</strong><small>Todos os membros ativos</small></span>
                      </button>
                    </li>
                  )}
                  {pessoas.map(pessoa => {
                    const estaOnline = pessoa.ativo && pessoa.online
                    return (
                      <li key={pessoa.id}>
                        <button type="button" disabled={!pessoa.ativo} className={colegaId === pessoa.id ? 'conversation-item int-person selected' : 'conversation-item int-person'} onClick={() => onPessoa(pessoa)}>
                          <Avatar nome={pessoa.nome} fotoUrl={pessoa.foto_url} />
                          <span className="conversation-item-main">
                            <strong>{pessoa.nome}</strong>
                            <small>{!pessoa.ativo ? 'Inativo' : estaOnline ? 'Online' : 'Offline'}</small>
                          </span>
                          <span className="conversation-item-meta"><span className={estaOnline ? 'status-dot' : 'status-dot status-dot-muted'} /></span>
                        </button>
                      </li>
                    )
                  })}
                  {!pessoas.length && !setor.grupo_ativo && <li className="empty-list">Nenhum usuário encontrado.</li>}
                </ul>
              )}
            </section>
          )
        })}
        {termo && !visiveis.length && <p className="empty-list">Ninguém encontrado para “{busca.trim()}”.</p>}
      </div>
    </aside>
  )
}

/* ───────────── conversa (coluna direita) ───────────── */

function CabecalhoChat({ grupo, colega, onVoltar, onImagem }) {
  const online = Boolean(colega?.ativo && colega?.online)
  const membros = grupo ? grupo.membros_ativos : 0
  return (
    <header className="chat-header">
      <div className="chat-person">
        <button type="button" className="int-back" onClick={onVoltar} aria-label="Voltar para a lista"><Icone nome="voltar" /></button>
        {grupo
          ? <span className="conversation-avatar large" aria-hidden="true"><Icone nome={iconeDoSetor(grupo.nome)} /></span>
          : (
            <button
              type="button"
              className="int-avatar-btn"
              onClick={() => colega?.foto_url && onImagem?.(colega.foto_url, colega.nome)}
              disabled={!colega?.foto_url}
              title={colega?.foto_url ? `Visualizar foto de ${colega.nome}` : undefined}
              aria-label={colega?.foto_url ? `Visualizar foto de ${colega.nome}` : undefined}
            >
              <Avatar nome={colega.nome} fotoUrl={colega.foto_url} grande />
            </button>
          )}
        <div>
          <h3>{grupo ? `Grupo · ${grupo.nome}` : colega.nome}</h3>
          <p>{grupo ? plural(membros, 'membro ativo', 'membros ativos') : online ? 'Disponível agora' : 'Vê as mensagens quando voltar'}</p>
        </div>
      </div>
      {grupo
        ? <span className="badge badge-neutral">Setor</span>
        : <span className={online ? 'badge badge-open' : 'badge badge-closed'}>{online ? 'Online' : 'Offline'}</span>}
    </header>
  )
}

function ListaMensagens({ mensagens, meId, ehGrupo, temAnteriores, onAnteriores, onImagem }) {
  const area = useRef(null)
  const pertoDoFim = useRef(true)
  const ultimoId = useRef(null)
  const ultima = mensagens.at(-1)
  const ultimaId = ultima?.id
  const ultimaRemetente = ultima?.remetente_id

  // rola para o fim só quando o usuário já está embaixo, ou quando ele mesmo enviou
  useEffect(() => {
    if (!ultimaId || ultimaId === ultimoId.current) return
    const primeira = ultimoId.current === null
    ultimoId.current = ultimaId
    if (primeira || pertoDoFim.current || ultimaRemetente === meId) {
      requestAnimationFrame(() => { if (area.current) area.current.scrollTop = area.current.scrollHeight })
    }
  }, [ultimaId, ultimaRemetente, meId])

  async function carregarAnteriores() {
    const el = area.current
    if (!el) return
    const altura = el.scrollHeight
    if (await onAnteriores()) requestAnimationFrame(() => { el.scrollTop += el.scrollHeight - altura })
  }

  function aoRolar(evento) {
    const el = evento.currentTarget
    pertoDoFim.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120
    if (el.scrollTop < 40 && temAnteriores && mensagens.length > 0) carregarAnteriores()
  }

  return (
    <div className="messages-scroll" ref={area} onScroll={aoRolar} role="log" aria-live="polite">
      {temAnteriores && (
        <div className="int-older-wrap">
          <button type="button" className="older-messages" onClick={carregarAnteriores}>Carregar mensagens anteriores</button>
        </div>
      )}
      {!mensagens.length && (
        <div className="empty-chat">
          <span className="empty-chat-icon"><Icone nome="conversa" tamanho={24} /></span>
          <strong>Nenhuma mensagem ainda</strong>
          <span>Comece a conversa.</span>
        </div>
      )}
      {mensagens.map((mensagem, indice) => {
        const anterior = mensagens[indice - 1]
        const novoDia = !anterior || messageDay(mensagem.criada_em) !== messageDay(anterior.criada_em)
        const minha = mensagem.remetente_id === meId
        const continua = !novoDia && anterior.remetente_id === mensagem.remetente_id && proximos(anterior.criada_em, mensagem.criada_em)
        return (
          <Fragment key={mensagem.id}>
            {novoDia && <div className="day-divider"><span>{messageDay(mensagem.criada_em)}</span></div>}
            <div className={`message-row${minha ? ' message-outgoing' : ''}${continua ? ' int-cont' : ''}`}>
              <div className={minha ? 'message-bubble message-bubble-outgoing' : 'message-bubble'}>
                {!minha && ehGrupo && !continua && <div className="message-label">{mensagem.remetente_nome}</div>}
                {mensagem.texto && <div className="message-text">{mensagem.texto}</div>}
                {mensagem.imagem_url && (
                  <button
                    type="button"
                    className="int-photo"
                    onClick={() => onImagem(mensagem.imagem_url, mensagem.remetente_nome ? `Imagem de ${mensagem.remetente_nome}` : 'Imagem enviada')}
                    aria-label="Ampliar imagem"
                    title="Ampliar imagem"
                  >
                    <img
                      src={mensagem.imagem_url}
                      alt="Imagem enviada no chat. Clique para ampliar."
                      loading="lazy"
                      draggable="false"
                    />
                  </button>
                )}
                <time>{messageHour(mensagem.criada_em)}</time>
              </div>
            </div>
          </Fragment>
        )
      })}
    </div>
  )
}

function Composer({ rotas, destino, onEnviado, onErro }) {
  const [texto, setTexto] = useState('')
  const [imagem, setImagem] = useState(null)
  const [previa, setPrevia] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const campo = useRef(null)
  const arquivo = useRef(null)

  useEffect(() => {
    if (!imagem) { setPrevia(null); return }
    const url = URL.createObjectURL(imagem)
    setPrevia(url)
    return () => URL.revokeObjectURL(url)
  }, [imagem])

  useEffect(() => {
    const el = campo.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`
  }, [texto])

  function escolherImagem(escolhida) {
    if (!escolhida) return
    if (!escolhida.type.startsWith('image/')) return onErro('Escolha um arquivo de imagem.')
    if (escolhida.size > LIMITE_ORIGEM) return onErro('Escolha uma imagem de até 12 MB.')
    onErro('')
    setImagem(escolhida)
  }

  function removerImagem() {
    setImagem(null)
    if (arquivo.current) arquivo.current.value = ''
  }

  function aoColar(evento) {
    const colada = [...evento.clipboardData.files].find(item => item.type.startsWith('image/'))
    if (colada) { evento.preventDefault(); escolherImagem(colada) }
  }

  async function enviar(evento) {
    evento?.preventDefault()
    const conteudo = texto.trim()
    if (enviando || (!conteudo && !imagem)) return
    setEnviando(true); onErro('')
    try {
      if (imagem) {
        const webp = await converterWebp(imagem)
        const params = conteudo ? `?${new URLSearchParams({ texto: conteudo })}` : ''
        await postar(`${BASE}/${rotas.imagens}${params}`, { headers: { 'Content-Type': 'image/webp' }, body: webp }, 'Não foi possível enviar a imagem.')
        removerImagem()
        if (conteudo) setTexto('')
      } else if (conteudo) {
        await postar(`${BASE}/${rotas.mensagens}`, {
          headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
          body: new URLSearchParams({ texto: conteudo }),
        }, 'Não foi possível enviar a mensagem.')
        setTexto('')
      }
      await onEnviado()
    } catch (falha) {
      onErro(falha.message)
    } finally {
      setEnviando(false)
    }
  }

  function aoTeclar(evento) {
    if (evento.key === 'Enter' && !evento.shiftKey && !evento.nativeEvent.isComposing) enviar(evento)
  }

  return (
    <div className="chat-composer">
      {imagem && (
        <div className="int-attachment">
          {previa && <img src={previa} alt="" />}
          <span><strong>{imagem.name}</strong><small>{Math.round(imagem.size / 1024)} KB · será convertida para WebP</small></span>
          <button type="button" className="int-icon-btn small" onClick={removerImagem} aria-label="Remover imagem"><Icone nome="fechar" tamanho={16} /></button>
        </div>
      )}
      <form onSubmit={enviar}>
        <input ref={arquivo} type="file" accept="image/*" hidden onChange={e => escolherImagem(e.target.files?.[0])} />
        <button type="button" className="int-icon-btn" onClick={() => arquivo.current?.click()} disabled={enviando} aria-label="Anexar imagem" title="Anexar imagem"><Icone nome="clipe" /></button>
        <textarea ref={campo} rows="1" value={texto} maxLength="4000" placeholder={`Mensagem para ${destino}`} aria-label="Mensagem"
          onChange={e => setTexto(e.target.value)} onKeyDown={aoTeclar} onPaste={aoColar} />
        <button type="submit" className="button button-primary" disabled={enviando || (!texto.trim() && !imagem)}>
          <Icone nome="enviar" tamanho={16} /><span>{enviando ? 'Enviando…' : 'Enviar'}</span>
        </button>
      </form>
      <small className="composer-hint">Enter envia · Shift+Enter quebra a linha · imagens até 12 MB, enviadas em WebP (máx. 2 MB)</small>
    </div>
  )
}

/* ───────────── conversa ativa ───────────── */

function Conversa({ rotas, grupo, colega, me, onVoltar, onImagem, onErro, atualizarConversas, onOpen }) {
  const { mensagens, temAnteriores, atualizar, carregarAnteriores } = useMensagens(rotas.mensagens, onErro)
  const ultimaMensagemId = mensagens.at(-1)?.id

  // marca como lida enquanto a conversa está aberta
  useEffect(() => {
    if (colega && mensagens.length) onOpen?.(colega.id)
  }, [colega?.id, mensagens.length, onOpen])

  useEffect(() => {
    if (!rotas || !mensagens.length) return
    const tipo = grupo ? 'grupo' : 'direta'
    const alvoId = grupo?.id || colega?.id
    postar(`${BASE}/conversas/${tipo}/${alvoId}/leitura`, {}, 'Não foi possível marcar como lida.')
      .then(atualizarConversas)
      .catch(() => {})
  }, [rotas.mensagens, ultimaMensagemId, grupo, colega, atualizarConversas])

  return (
    <>
      <CabecalhoChat grupo={grupo} colega={colega} onVoltar={onVoltar} onImagem={onImagem} />
      <ListaMensagens
        mensagens={mensagens}
        meId={me.id}
        ehGrupo={Boolean(grupo)}
        temAnteriores={temAnteriores}
        onAnteriores={carregarAnteriores}
        onImagem={onImagem}
      />
      <Composer
        rotas={rotas}
        destino={grupo ? `Grupo · ${grupo.nome}` : colega.nome}
        onEnviado={() => atualizar(true)}
        onErro={onErro}
      />
    </>
  )
}

/* ───────────── página ───────────── */

export default function Interno({ me, abrirColegaId, onOpen, onUnreadChange, onVisualizarImagem }) {
  const [erro, setErro] = useState('')
  const [aberto, setAberto] = useState(null)
  const [colegaSel, setColegaSel] = useState(null)
  const [grupoSel, setGrupoSel] = useState(null)
  const [imagemAberta, setImagemAberta] = useState(null)
  const [conversas, setConversas] = useState([])

  const abrirImagem = useCallback((url, titulo) => {
    if (!url) return
    if (onVisualizarImagem) {
      onVisualizarImagem(url, titulo)
    } else {
      setImagemAberta({ url, titulo })
    }
  }, [onVisualizarImagem])

  const atualizarConversas = useCallback(() => leitura(`${BASE}/conversas`)
    .then(dados => { setConversas(dados.conversas); onUnreadChange?.(dados.nao_lidas) })
    .catch(falha => setErro(falha.message)), [onUnreadChange])
  useEffect(() => {
    atualizarConversas()
    const id = setInterval(atualizarConversas, INTERVALO_MS)
    return () => clearInterval(id)
  }, [atualizarConversas])

  const setores = useSetores(setErro)
  const pessoas = useMemo(() => setores.flatMap(setor => setor.pessoas), [setores])
  // versão atualizada (online/offline) do item selecionado
  const colega = colegaSel && (pessoas.find(p => p.id === colegaSel.id) || colegaSel)
  const grupo = grupoSel && (setores.find(s => s.id === grupoSel.id) || grupoSel)
  const rotas = rotasDe(grupo, colega)

  function selecionarPessoa(pessoa) {
    if (!pessoa) return
    setGrupoSel(null); setColegaSel(pessoa); setErro('')
    onOpen(pessoa.id)
  }
  function selecionarGrupo(setor) {
    if (!setor) return
    setColegaSel(null); setGrupoSel(setor); setErro('')
  }
  function voltar() {
    setColegaSel(null); setGrupoSel(null); setErro('')
  }

  // abre direto numa conversa (ex.: vindo de uma notificação)
  useEffect(() => {
    if (!abrirColegaId || !setores.length) return
    const pessoa = pessoas.find(item => item.id === abrirColegaId)
    if (!pessoa) return
    selecionarPessoa(pessoa)
    setAberto(setores.find(setor => setor.pessoas.some(usuario => usuario.id === pessoa.id))?.id ?? null)
  }, [abrirColegaId, setores.length])

  return (
    <>
      {erro && <div className="toast toast-error" role="alert">{erro}</div>}

      <div className={rotas ? 'inbox-layout int-layout has-chat' : 'inbox-layout int-layout'}>
        <Diretorio
          setores={setores} conversas={conversas} aberto={aberto} colegaId={colegaSel?.id} grupoId={grupoSel?.id}
          onAlternar={id => setAberto(atual => (atual === id ? null : id))}
          onPessoa={selecionarPessoa} onGrupo={selecionarGrupo}
        />
        <section className="chat-pane" aria-label="Conversa">
          {!rotas ? (
            <div className="chat-placeholder">
              <span className="placeholder-mark"><Icone nome="conversa" tamanho={34} /></span>
              <h2>Escolha uma conversa</h2>
              <p>Abra um setor e selecione o grupo ou alguém da equipe.</p>
            </div>
          ) : (
            <Conversa
              key={rotas.mensagens}
              rotas={rotas}
              grupo={grupo}
              colega={colega}
              me={me}
              onVoltar={voltar}
              onImagem={abrirImagem}
              onErro={setErro}
              atualizarConversas={atualizarConversas}
              onOpen={onOpen}
            />
          )}
        </section>
      </div>

      {!onVisualizarImagem && imagemAberta && (
        <ModalImagem
          url={imagemAberta.url}
          titulo={imagemAberta.titulo}
          onFechar={() => setImagemAberta(null)}
        />
      )}
    </>
  )
}
