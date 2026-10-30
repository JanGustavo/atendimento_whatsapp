import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Chamados, { ChamadosVendedor } from './Chamados.jsx'
import { messageDay } from './dates.js'
import Interno from './Interno.jsx'
import Perfil from './Perfil.jsx'
import ModalImagem from './ModalImagem.jsx'
import { converterWebp } from './images.js'

const roleName = { gestor: 'Gestor', supervisor: 'Supervisor', colaborador: 'Colaborador' }
const stageName = {
  menu_setor: 'Escolhendo setor',
  menu_vendedor: 'Escolhendo vendedor',
  atribuida: 'Em atendimento',
  aviso_transferencia: 'Aguardando resposta',
  standby: 'Em espera',
  fora_expediente: 'Fora do expediente',
  encerrada: 'Encerrada',
}
const routeByPage = {
  inbox: '/atendimentos',
  manager: '/gestor',
  simulator: '/simulador',
  tickets: '/chamados',
  interno: '/interno',
  perfil: '/perfil',
}
const pageByRoute = Object.fromEntries(
  Object.entries(routeByPage).map(([page, route]) => [route, page]),
)

function allowedPage(page, role) {
  if (page === 'manager' || page === 'simulator') return role === 'gestor'
  if (page === 'tickets') return true
  return true
}

function initialPage(role) {
  const requested = pageByRoute[window.location.pathname]
  return requested && allowedPage(requested, role)
    ? requested
    : role === 'gestor'
      ? 'manager'
      : 'inbox'
}

async function getJSON(path) {
  const response = await fetch(path, { credentials: 'same-origin' })
  if (!response.ok) {
    const error = new Error(
      response.status === 401
        ? 'Sessão encerrada. Entre novamente.'
        : `Falha ao carregar (${response.status}).`,
    )
    error.status = response.status
    throw error
  }
  return response.json()
}

async function postForm(path, values) {
  const body = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null) body.set(key, String(value))
  })
  const response = await fetch(path, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
    body,
  })
  if (!response.ok) {
    let message = `Não foi possível concluir (${response.status}).`
    try {
      const data = await response.json()
      if (data.detail) message = typeof data.detail === 'string' ? data.detail : message
    } catch {
      /* Erros de rede sem corpo JSON. */
    }
    throw new Error(message)
  }
}

function time(value) {
  if (!value) return ''
  const date = new Date(value.endsWith('Z') ? value : `${value}Z`)
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleString('pt-BR', {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
      })
}

function initials(name = '') {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0].toUpperCase())
      .join('') || 'FG'
  )
}

function Brand({ compact = false }) {
  return (
    <div className={`brand ${compact ? 'brand-compact' : ''}`}>
      <img
        className="brand-logo"
        src="/static/fortgiro-logo.png"
        alt="FortGiro · Distribuidora de Autopeças"
      />
    </div>
  )
}

function Icon({ name, size = 19 }) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  }
  const paths = {
    inbox: (
      <>
        <path d="M4 5h16v11H4z" />
        <path d="M4 14h5l1.5 2h3L15 14h5v5H4z" />
      </>
    ),
    grid: (
      <>
        <rect x="3" y="3" width="8" height="8" rx="1" />
        <rect x="13" y="3" width="8" height="8" rx="1" />
        <rect x="3" y="13" width="8" height="8" rx="1" />
        <rect x="13" y="13" width="8" height="8" rx="1" />
      </>
    ),
    chat: (
      <>
        <path d="M4 5h16v12H9l-5 4z" />
        <path d="M8 9h8M8 13h5" />
      </>
    ),
    logout: (
      <>
        <path d="M10 4H5v16h5M14 8l4 4-4 4M8 12h10" />
      </>
    ),
    search: (
      <>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 5 5" />
      </>
    ),
    send: (
      <>
        <path d="m3 11 18-8-7 18-3-8z" />
        <path d="m11 13 10-10" />
      </>
    ),
    arrow: <path d="m5 12 14 0m-6-6 6 6-6 6" />,
    clip: <path d="m21.5 11.5-8.6 8.6a5 5 0 0 1-7.1-7.1l8.6-8.6a3.3 3.3 0 0 1 4.7 4.7l-8.6 8.6a1.7 1.7 0 0 1-2.4-2.4l7.9-7.9" />,
    fechar: <path d="M18 6 6 18M6 6l12 12" />,
    ticket: (
      <>
        <path d="M4 3h16v18l-4-2-4 2-4-2-4 2z" />
        <path d="M8 8h8M8 12h8" />
      </>
    ),
    users: (
      <>
        <circle cx="9" cy="8" r="3" />
        <path d="M3 20v-2a6 6 0 0 1 12 0v2M17 5a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5v1" />
      </>
    ),
  }
  return <svg {...common}>{paths[name]}</svg>
}

function Badge({ status, children }) {
  return (
    <span
      className={`badge badge-${status === 'aberta' ? 'open' : status === 'encerrada' ? 'closed' : 'neutral'}`}
    >
      {children || (status === 'aberta' ? 'Aberta' : 'Encerrada')}
    </span>
  )
}

function Login({ onLogin, busy, error }) {
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  return (
    <div className="login-layout">
      <aside className="login-art">
        <Brand />
        <div className="login-art-center">
          <div className="art-orbit art-orbit-one" />
          <div className="art-orbit art-orbit-two" />
          <p className="art-kicker">ATENDIMENTO QUE ACOMPANHA O SEU RITMO</p>
          <h1>
            Conexões que
            <br />
            <em>movem</em> negócios.
          </h1>
          <p className="art-description">
            Uma central simples para cada conversa, cada cliente e cada oportunidade.
          </p>
        </div>
        <div className="login-art-footer">FortGiro · Distribuidora de autopeças</div>
      </aside>
      <main className="login-main">
        <div className="login-box">
          <div className="login-mobile-brand">
            <Brand compact />
          </div>
          <div className="eyebrow">ÁREA DA EQUIPE</div>
          <h2>Bem-vindo de volta</h2>
          <p className="muted">Acesse sua central de atendimento.</p>
          <form
            onSubmit={(event) => {
              event.preventDefault()
              onLogin({ email, senha })
            }}
          >
            <label>
              Email
              <input
                autoComplete="username"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="seuemail@empresa.com"
                required
              />
            </label>
            <label>
              Senha
              <input
                autoComplete="current-password"
                type="password"
                value={senha}
                onChange={(event) => setSenha(event.target.value)}
                placeholder="Sua senha"
                required
              />
            </label>
            {error && (
              <div className="form-error" role="alert">
                {error}
              </div>
            )}
            <button className="button button-primary button-wide" disabled={busy}>
              {' '}
              {busy ? 'Entrando...' : 'Entrar na plataforma'} <Icon name="arrow" size={18} />
            </button>
          </form>
          <p className="login-footnote">Acesso exclusivo para a equipe FortGiro.</p>
        </div>
      </main>
    </div>
  )
}

function MessageBubbles({ messages, simulator = false, onRetry, onImagem, currentUserId, busy = false }) {
  const bottom = React.useRef(null)
  const colado = useRef(true)
  const montado = useRef(false)
  const total = useRef(0)
  const ultima = messages[messages.length - 1]
  useEffect(() => {
    const cresceu = messages.length > total.current
    total.current = messages.length
    const propria = simulator ? ultima?.origem === 'cliente' : ultima?.origem === 'humano'
    if (cresceu && propria) colado.current = true
    if (!colado.current || !bottom.current) return
    bottom.current.scrollIntoView({ block: 'end', behavior: montado.current ? 'smooth' : 'auto' })
    montado.current = true
  }, [messages.length])
  if (!messages.length)
    return (
      <div className="empty-chat">
        <div className="empty-chat-icon">
          <Icon name="chat" size={28} />
        </div>
        <strong>Nenhuma mensagem ainda</strong>
        <span>As mensagens aparecerão aqui.</span>
      </div>
    )
  return (
    <div
      className="messages-scroll"
      onScroll={(event) => {
        const el = event.currentTarget
        colado.current = el.scrollHeight - el.scrollTop - el.clientHeight < 140
      }}
    >
      {messages.map((message, index) => {
        const outgoing = simulator ? message.origem === 'cliente' : message.origem === 'humano'
        const label =
          message.origem === 'cliente'
            ? 'Cliente'
            : message.origem === 'bot'
              ? 'Assistente'
              : 'Equipe'
        const dia = messageDay(message.criada_em)
        return (
          <React.Fragment key={message.id}>
            {(index === 0 || dia !== messageDay(messages[index - 1].criada_em)) && (
              <div className="day-divider">
                <span>{dia}</span>
              </div>
            )}
            <div className={`message-row ${outgoing ? 'message-outgoing' : ''}`}>
              <div className={`message-bubble ${outgoing ? 'message-bubble-outgoing' : ''}`}>
                <div className="message-label">{label}</div>
                {message.imagem_url && (
                  <button
                    type="button"
                    className="int-photo"
                    onClick={() => onImagem?.(message.imagem_url, 'Imagem da mensagem')}
                    aria-label="Ampliar imagem"
                    title="Ampliar imagem"
                  >
                    <img
                      src={message.imagem_url}
                      alt="Imagem da conversa. Clique para ampliar."
                      loading="lazy"
                      draggable="false"
                    />
                  </button>
                )}
                {message.texto && <div className="message-text">{message.texto}</div>}
                <time>
                  {time(message.criada_em)}
                  {!simulator && message.origem !== 'cliente' && (
                    <span
                      className={`delivery-status delivery-${message.envio_status || 'pendente'}`}
                    >
                      {' '}
                      ·{' '}
                      {{
                        pendente: 'Enviando',
                        enviada: '✓ Enviada',
                        entregue: '✓✓ Entregue',
                        lida: '✓✓ Lida',
                        falhou: 'Falhou',
                      }[message.envio_status] || 'Pendente'}
                      {message.lida_em ? ` às ${time(message.lida_em)}` : ''}
                    </span>
                  )}
                </time>
                {!simulator &&
                  message.origem === 'humano' &&
                  message.envio_status === 'falhou' &&
                  message.autor_id === currentUserId &&
                  onRetry && (
                    <button
                      className="retry-message"
                      disabled={busy}
                      onClick={() => onRetry(message.id)}
                    >
                      Reenviar
                    </button>
                  )}
              </div>
            </div>
          </React.Fragment>
        )
      })}
      <div ref={bottom} />
    </div>
  )
}

function AtendimentoTags({ conversa }) {
  const tipo = conversa.setor_ordem === 1 ? 'Vendas' : 'Supervisor'
  return (
    <span className="atendimento-tags">
      <span className="atendimento-tag setor-tag">{conversa.setor_nome || 'Escolhendo setor'}</span>
      {conversa.atribuido_nome && (
        <span className="atendimento-tag pessoa-tag">
          {tipo}: {conversa.atribuido_nome}
        </span>
      )}
    </span>
  )
}

const atendimentoFiltros = [
  { id: 'todas', nome: 'Todas' },
  { id: 'nao_lidas', nome: 'Não lidas' },
  { id: 'abertas', nome: 'Abertas' },
]

function Inbox({
  me,
  conversations,
  selectedId,
  onSelect,
  detail,
  search,
  setSearch,
  onSend,
  onRetry,
  onClose,
  onTransfer,
  onUploadPhoto,
  onImagem,
  busy,
}) {
  const [draft, setDraft] = useState('')
  const [destino, setDestino] = useState('')
  const [filtro, setFiltro] = useState('todas')
  const [imagemWpp, setImagemWpp] = useState(null)
  const [previaWpp, setPreviaWpp] = useState(null)
  const destinoRef = useRef(null)
  const fotoRef = useRef(null)
  const arquivoWppRef = useRef(null)
  const campoWppRef = useRef(null)
  // Sempre aponta para a conversa aberta agora: respostas assíncronas de outra conversa são ignoradas.
  const selectedIdRef = useRef(selectedId)
  selectedIdRef.current = selectedId
  useEffect(() => setDraft(''), [selectedId])
  useEffect(() => setDestino(''), [selectedId])
  useEffect(() => { setImagemWpp(null); setPreviaWpp(null) }, [selectedId])

  useEffect(() => {
    if (!imagemWpp) { setPreviaWpp(null); return }
    const url = URL.createObjectURL(imagemWpp)
    setPreviaWpp(url)
    return () => URL.revokeObjectURL(url)
  }, [imagemWpp])

  useEffect(() => {
    const el = campoWppRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`
  }, [draft])

  function escolherImagemWpp(escolhida) {
    if (!escolhida) return
    if (!escolhida.type.startsWith('image/')) return
    setImagemWpp(escolhida)
  }

  function removerImagemWpp() {
    setImagemWpp(null)
    if (arquivoWppRef.current) arquivoWppRef.current.value = ''
  }

  // Só exibe o detalhe que pertence à conversa selecionada; um detalhe antigo nunca aparece.
  const temSelecao = selectedId !== null && selectedId !== undefined
  const atual = temSelecao && detail?.conversa?.id === selectedId ? detail : null
  const selected = atual?.conversa

  const contagens = useMemo(
    () => ({
      todas: conversations.length,
      nao_lidas: conversations.filter((item) => item.nao_lidas > 0).length,
      abertas: conversations.filter((item) => item.status === 'aberta').length,
    }),
    [conversations],
  )
  const visiveis = useMemo(
    () =>
      filtro === 'nao_lidas'
        ? conversations.filter((item) => item.nao_lidas > 0)
        : filtro === 'abertas'
          ? conversations.filter((item) => item.status === 'aberta')
          : conversations,
    [conversations, filtro],
  )
  const mensagemVazia = search.trim()
    ? 'Nenhuma conversa encontrada para essa busca.'
    : filtro === 'nao_lidas'
      ? 'Nenhuma conversa com mensagens não lidas.'
      : filtro === 'abertas'
        ? 'Nenhuma conversa aberta no momento.'
        : 'Nenhuma conversa encontrada.'

  async function enviar() {
    const texto = draft.trim()
    if ((!texto && !imagemWpp) || busy || !selected) return
    if (texto.toLowerCase() === '/transferir') {
      setDraft('')
      destinoRef.current?.focus()
      return
    }
    const alvo = selected.id
    if ((await onSend(alvo, texto, imagemWpp)) && selectedIdRef.current === alvo) {
      setDraft('')
      removerImagemWpp()
    }
  }
  const botaoVoltar = (
    <button
      type="button"
      className="atendimento-voltar"
      aria-label="Voltar para a lista de conversas"
      onClick={() => onSelect(null)}
    >
      <Icon name="arrow" size={18} />
    </button>
  )

  return (
    <div className={`inbox-layout atendimento-layout ${temSelecao ? 'atendimento-com-conversa' : ''}`}>
      <aside className="conversation-pane" aria-label="Conversas">
        <div className="pane-heading">
          <div>
            <div className="eyebrow">CENTRAL</div>
            <h2>{me.role === 'gestor' ? 'Conversas' : 'Meus atendimentos'}</h2>
          </div>
          <span className="count-chip" title="Total de conversas">
            {conversations.length}
          </span>
        </div>
        <div className="search-box" role="search">
          <Icon name="search" size={17} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Buscar número"
            aria-label="Buscar conversas"
          />
        </div>
        <div className="atendimento-filtros" role="group" aria-label="Filtrar conversas">
          {atendimentoFiltros.map((item) => (
            <button
              type="button"
              key={item.id}
              className={`atendimento-filtro ${filtro === item.id ? 'atendimento-filtro-ativo' : ''}`}
              aria-pressed={filtro === item.id}
              onClick={() => setFiltro(item.id)}
            >
              {item.nome}
              <span>{contagens[item.id]}</span>
            </button>
          ))}
        </div>
        {visiveis.length ? (
          <ul className="conversation-items atendimento-lista">
            {visiveis.map((conversa) => {
              const ativa = selectedId === conversa.id
              const naoLidas = conversa.nao_lidas > 0
              return (
                <li key={conversa.id}>
                  <button
                    type="button"
                    className={`conversation-item atendimento-item ${ativa ? 'selected' : ''} ${naoLidas ? 'atendimento-item-nova' : ''}`}
                    aria-current={ativa ? 'true' : undefined}
                    onClick={() => onSelect(conversa.id)}
                  >
                    <span className="conversation-avatar" aria-hidden="true">
                      {conversa.foto_url ? <img className="int-avatar-photo" src={conversa.foto_url} alt="" /> : (conversa.nome_contato?.trim().slice(0, 1).toUpperCase() || conversa.numero.slice(-2))}
                    </span>
                    <span className="conversation-item-main">
                      <strong className="atendimento-numero">{conversa.numero}</strong>
                      <small className="atendimento-contato">{conversa.nome_contato || 'Contato sem nome salvo'}</small>
                      <AtendimentoTags conversa={conversa} />
                      {conversa.etapa && stageName[conversa.etapa] && (
                        <small className="atendimento-item-etapa">{stageName[conversa.etapa]}</small>
                      )}
                    </span>
                    <span className="conversation-item-meta">
                      <time>{time(conversa.criada_em).split(',').pop()}</time>
                      {naoLidas ? (
                        <>
                          <b className="nav-count" aria-hidden="true">
                            {conversa.nao_lidas}
                          </b>
                          <span className="atendimento-sr">
                            {conversa.nao_lidas === 1
                              ? '1 mensagem não lida'
                              : `${conversa.nao_lidas} mensagens não lidas`}
                          </span>
                        </>
                      ) : (
                        <>
                          <i
                            aria-hidden="true"
                            className={
                              conversa.status === 'aberta'
                                ? 'status-dot'
                                : 'status-dot status-dot-muted'
                            }
                          />
                          <span className="atendimento-sr">
                            {conversa.status === 'aberta' ? 'Aberta' : 'Encerrada'}
                          </span>
                        </>
                      )}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        ) : (
          <div className="conversation-items">
            <div className="empty-list" role="status">
              {mensagemVazia}
            </div>
          </div>
        )}
      </aside>
      <section className="chat-pane" aria-label="Conversa selecionada">
        {!temSelecao ? (
          <div className="chat-placeholder">
            <div className="placeholder-mark">
              <Icon name="chat" size={42} />
            </div>
            <h2>Seu atendimento, em um só lugar.</h2>
            <p>Escolha uma conversa para acompanhar o histórico e responder.</p>
          </div>
        ) : !selected ? (
          <>
            <div className="chat-header atendimento-cabecalho">
              <div className="chat-person">
                {botaoVoltar}
                <strong>Abrindo conversa…</strong>
              </div>
            </div>
            <div className="chat-placeholder" role="status" aria-live="polite">
              <p>Carregando mensagens…</p>
            </div>
          </>
        ) : (
          <>
            <div className="chat-header atendimento-cabecalho">
              <div className="chat-person">
                {botaoVoltar}
                <div className="conversation-avatar large" aria-hidden="true">
                  {selected.foto_url ? <img className="int-avatar-photo" src={selected.foto_url} alt="" /> : (selected.nome_contato?.trim().slice(0, 1).toUpperCase() || selected.numero.slice(-2))}
                </div>
                <div className="atendimento-titulo">
                  <h3>{selected.numero}</h3>
                  <small className="atendimento-contato">{selected.nome_contato || 'Contato sem nome salvo'}</small>
                  <AtendimentoTags conversa={selected} />
                </div>
              </div>
              <input ref={fotoRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={async (event) => {
                const arquivo = event.target.files?.[0]
                event.target.value = ''
                if (arquivo) await onUploadPhoto(selected.id, arquivo)
              }} />
              <button type="button" className="atendimento-foto-botao" disabled={busy} onClick={() => fotoRef.current?.click()} title="Adicionar foto fornecida pelo cliente">{selected.foto_url ? 'Trocar foto' : 'Adicionar foto'}</button>
              <Badge status={selected.status} />
            </div>
            <div className="chat-stage atendimento-stage">
              <span className="atendimento-chip">
                Etapa: {stageName[selected.etapa] || selected.etapa}
              </span>
              {atual.mensagens.some((item) => item.origem === 'cliente') && (
                <span
                  className={`atendimento-chip ${atual.visualizada_pelo_atendente_em ? 'atendimento-chip-ok' : 'atendimento-chip-alerta'}`}
                >
                  {atual.visualizada_pelo_atendente_em
                    ? `Última mensagem vista pelo atendente em ${time(atual.visualizada_pelo_atendente_em)}`
                    : 'Última mensagem ainda não visualizada pelo atendente'}
                </span>
              )}
              {selected.timer_prazo_em && !selected.primeira_resposta_em && (
                <span className="atendimento-chip atendimento-chip-alerta">
                  Prazo: {time(selected.timer_prazo_em)}
                </span>
              )}
            </div>
            <MessageBubbles
              key={selected.id}
              messages={atual.mensagens}
              currentUserId={me.id}
              onRetry={(messageId) => onRetry(selected.id, messageId)}
              onImagem={onImagem}
              busy={busy}
            />
            {selected.status === 'aberta' ? (
              <div className="chat-composer atendimento-composer">
                {imagemWpp && (
                  <div className="int-attachment">
                    {previaWpp && <img src={previaWpp} alt="" />}
                    <span><strong>{imagemWpp.name}</strong><small>{Math.round(imagemWpp.size / 1024)} KB</small></span>
                    <button type="button" className="int-icon-btn small" onClick={removerImagemWpp} aria-label="Remover imagem">
                      <Icon name="fechar" size={16} />
                    </button>
                  </div>
                )}
                <form
                  onSubmit={(event) => {
                    event.preventDefault()
                    enviar()
                  }}
                >
                  <input
                    ref={arquivoWppRef}
                    type="file"
                    accept="image/*"
                    hidden
                    onChange={(e) => escolherImagemWpp(e.target.files?.[0])}
                  />
                  <button
                    type="button"
                    className="int-icon-btn"
                    onClick={() => arquivoWppRef.current?.click()}
                    disabled={busy}
                    aria-label="Anexar imagem"
                    title="Anexar imagem"
                  >
                    <Icon name="clip" size={20} />
                  </button>
                  <textarea
                    ref={campoWppRef}
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && draft.trim().toLowerCase() === '/transferir') {
                        event.preventDefault()
                        setDraft('')
                        destinoRef.current?.focus()
                        return
                      }
                      if (event.key === 'Enter' && (event.ctrlKey || event.shiftKey)) {
                        event.preventDefault()
                        if (!busy && (draft.trim() || imagemWpp)) event.currentTarget.form?.requestSubmit()
                      }
                    }}
                    placeholder="Escreva sua resposta..."
                    aria-label="Resposta ao cliente"
                    aria-describedby="atendimento-dica"
                    rows="1"
                    maxLength="4000"
                    required={!imagemWpp}
                  />
                  <button
                    className="button button-primary"
                    disabled={busy || (!draft.trim() && !imagemWpp)}
                    title="Enviar resposta"
                  >
                    <Icon name="send" size={18} /><span>Enviar</span>
                  </button>
                </form>
                <small className="composer-hint" id="atendimento-dica">
                  Ctrl+Enter ou Shift+Enter para enviar · /transferir para escolher destino
                </small>
                <div className="atendimento-acoes">
                  <div className="transfer-controls">
                    <label>
                      Transferir para{' '}
                      <select
                        ref={destinoRef}
                        value={destino}
                        onChange={(event) => setDestino(event.target.value)}
                      >
                        <option value="">Escolha um atendente ou setor</option>
                        {(atual.destinos || []).map((item) => (
                          <option key={item.valor} value={item.valor}>
                            {item.nome}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      className="button button-soft"
                      disabled={busy || !destino}
                      onClick={async () => {
                        const alvo = selected.id
                        if ((await onTransfer(alvo, destino)) && selectedIdRef.current === alvo)
                          setDestino('')
                      }}
                    >
                      Transferir
                    </button>
                  </div>
                  <button
                    type="button"
                    className="text-button atendimento-encerrar"
                    disabled={busy}
                    onClick={() => onClose(selected.id)}
                  >
                    Encerrar conversa
                  </button>
                </div>
              </div>
            ) : (
              <div className="closed-note" role="status">
                Esta conversa foi encerrada.
              </div>
            )}
          </>
        )}
      </section>
    </div>
  )
}

function UserEditor({ user, setoresInternos, onSave, busy }) {
  const [value, setValue] = useState({ ...user, senha: '' })
  return (
    <form
      className="user-row user-card"
      onSubmit={async (event) => {
        event.preventDefault()
        if (await onSave(user.id, value)) setValue({ ...value, senha: '' })
      }}
    >
      <div className="user-card-heading">
        <span className="user-avatar">{initials(value.nome)}</span>
        <div>
          <strong>{value.nome}</strong>
          <small>Usuário #{user.id}</small>
        </div>
      </div>
      <div className="user-card-fields">
        <label>
          Nome
          <input
            value={value.nome}
            onChange={(event) => setValue({ ...value, nome: event.target.value })}
            required
          />
        </label>
        <label>
          Email de acesso
          <input
            type="email"
            value={value.email}
            onChange={(event) => setValue({ ...value, email: event.target.value })}
            required
          />
        </label>
        <label>
          Permissão
          <select
            value={value.role}
            onChange={(event) => setValue({ ...value, role: event.target.value })}
          >
            <option value="colaborador">Colaborador</option>
            <option value="supervisor">Supervisor</option>
            <option value="gestor">Gestor</option>
          </select>
        </label>
        <label>
          Setor/equipe
          <select
            value={value.setor_interno_id || ''}
            onChange={(event) => setValue({ ...value, setor_interno_id: event.target.value })}
          >
            <option value="">Sem setor</option>
            {setoresInternos.map((item) => (
              <option key={item.id} value={item.id}>
                {item.nome}
              </option>
            ))}
          </select>
        </label>
        <label>
          Redefinir senha
          <input
            type="password"
            placeholder="Deixe em branco para manter"
            minLength="8"
            value={value.senha}
            onChange={(event) => setValue({ ...value, senha: event.target.value })}
          />
        </label>
      </div>
      <div className="user-card-actions">
        <label className="switch-line">
          <input
            type="checkbox"
            checked={value.ativo}
            onChange={(event) => setValue({ ...value, ativo: event.target.checked })}
          />
          <span>Ativo</span>
        </label>
        <label className="switch-line">
          <input
            type="checkbox"
            checked={value.online}
            onChange={(event) => setValue({ ...value, online: event.target.checked })}
          />
          <span>Online</span>
        </label>
        <button className="button button-soft" disabled={busy}>
          Salvar alterações
        </button>
      </div>
    </form>
  )
}

function SectorEditor({ sector, users, onSave, busy }) {
  const [nome, setNome] = useState(sector.nome)
  const [responsavel, setResponsavel] = useState(sector.responsavel_id || '')
  return (
    <form
      className="sector-row"
      onSubmit={(event) => {
        event.preventDefault()
        onSave(sector.id, { nome, responsavel_id: responsavel })
      }}
    >
      <span className="sector-number">{String(sector.ordem).padStart(2, '0')}</span>
      <input
        aria-label={`Nome do setor ${sector.ordem}`}
        value={nome}
        onChange={(event) => setNome(event.target.value)}
        required
      />
      <select
        aria-label={`Responsável pelo setor ${sector.ordem}`}
        value={responsavel}
        onChange={(event) => setResponsavel(event.target.value)}
        disabled={sector.ordem === 1}
      >
        <option value="">
          {sector.ordem === 1 ? 'Distribuição entre a equipe de Vendas' : 'Selecionar supervisor'}
        </option>
        {users
          .filter((item) => item.role === 'supervisor' && item.ativo)
          .map((item) => (
            <option key={item.id} value={item.id}>
              {item.nome}
            </option>
          ))}
      </select>
      <button className="button button-soft" disabled={busy}>
        Salvar
      </button>
    </form>
  )
}

function InternalSectorEditor({ sector, onSave, busy }) {
  const [nome, setNome] = useState(sector.nome)
  return (
    <form
      className="sector-row"
      onSubmit={(event) => {
        event.preventDefault()
        onSave(sector.id, { nome })
      }}
    >
      <span className="sector-number">#{sector.id}</span>
      <input
        aria-label={`Nome da equipe ${sector.nome}`}
        value={nome}
        onChange={(event) => setNome(event.target.value)}
        maxLength="80"
        required
      />
      <span className="muted">Grupo automático com 2 ou mais membros ativos</span>
      <button className="button button-soft" disabled={busy}>
        Salvar
      </button>
    </form>
  )
}

function Manager({
  conversations,
  config,
  whatsappStatus,
  vendorFilter,
  setVendorFilter,
  onOpen,
  onTransfer,
  onCreateUser,
  onSaveUser,
  onSaveSector,
  onCreateInternalSector,
  onSaveInternalSector,
  onToggleSimulator,
  busy,
}) {
  const [newUser, setNewUser] = useState({
    nome: '',
    email: '',
    senha: '',
    role: 'colaborador',
    setor_interno_id: 1,
  })
  const [newInternalSector, setNewInternalSector] = useState('')
  const [transfers, setTransfers] = useState({})
  const [tab, setTab] = useState('conversas')
  const users = config?.usuarios || []
  const sectors = config?.setores || []
  const open = conversations.filter((item) => item.status === 'aberta').length
  const waiting = conversations.filter(
    (item) => item.status === 'aberta' && !item.atribuido_id,
  ).length
  const online = users.filter(
    (item) =>
      item.role === 'colaborador' && item.setor_interno_id === 1 && item.ativo && item.online,
  ).length
  const visibleConversations = vendorFilter
    ? conversations.filter((item) => String(item.atribuido_id) === vendorFilter)
    : conversations
  return (
    <div className="manager-page">
      <div className="page-intro">
        <div>
          <div className="eyebrow">VISÃO GERAL</div>
          <h1>Gestão do atendimento</h1>
          <p>Acompanhe conversas, equipe e distribuição em tempo real.</p>
        </div>
        <div className="live-indicator">
          <span /> Atualização automática
        </div>
      </div>
      <div className="stat-grid">
        <div className="stat-card">
          <span>Conversas abertas</span>
          <strong>{open}</strong>
          <small>Em toda a operação</small>
        </div>
        <div className="stat-card">
          <span>Aguardando setor</span>
          <strong>{waiting}</strong>
          <small>Ainda sem responsável</small>
        </div>
        <div className="stat-card stat-card-gold">
          <span>Equipe de Vendas online</span>
          <strong>{online}</strong>
          <small>Disponíveis para distribuição</small>
        </div>
        <div className="stat-card">
          <span>WhatsApp</span>
          <strong>{whatsappStatus || 'Verificando'}</strong>
          <small>Estado da API</small>
        </div>
      </div>
      <div className="simulator-setting surface">
        <div>
          <strong>Simulador de WhatsApp</strong>
          <p className="muted">Oculto da navegação e sem envios quando desligado.</p>
        </div>
        <label className="switch-line">
          <input
            type="checkbox"
            checked={Boolean(config?.simulador_ativo)}
            onChange={(event) => onToggleSimulator(event.target.checked)}
            disabled={busy || !config}
          />
          <span>{config?.simulador_ativo ? 'Ativado' : 'Desativado'}</span>
        </label>
      </div>
      <div className="section-tabs">
        <button className={tab === 'conversas' ? 'active' : ''} onClick={() => setTab('conversas')}>
          Conversas
        </button>
        <button className={tab === 'equipe' ? 'active' : ''} onClick={() => setTab('equipe')}>
          Equipe
        </button>
        <button className={tab === 'setores' ? 'active' : ''} onClick={() => setTab('setores')}>
          Setores
        </button>
      </div>
      {tab === 'conversas' && (
        <section className="surface manager-section">
          <div className="section-heading">
            <div>
              <h2>Todas as conversas</h2>
              <p>Abra uma conversa ou transfira para outro atendente.</p>
            </div>
            <label className="filter-label">
              Atendente{' '}
              <select
                value={vendorFilter}
                onChange={(event) => setVendorFilter(event.target.value)}
              >
                <option value="">Todos</option>
                {users
                  .filter((item) => item.role !== 'gestor')
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.nome}
                    </option>
                  ))}
              </select>
            </label>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Cliente</th>
                  <th>Setor</th>
                  <th>Responsável</th>
                  <th>Status</th>
                  <th>Transferir</th>
                </tr>
              </thead>
              <tbody>
                {visibleConversations.map((conversa) => {
                  const options = conversa.setor_ordem
                    ? users.filter(
                        (item) =>
                          item.ativo &&
                          (conversa.setor_ordem === 1
                            ? item.role === 'colaborador' && item.setor_interno_id === 1
                            : item.role === 'supervisor') &&
                          item.id !== conversa.atribuido_id,
                      )
                    : []
                  return (
                    <tr key={conversa.id}>
                      <td>
                        <button className="table-link" onClick={() => onOpen(conversa.id)}>
                          {conversa.numero}
                        </button>
                        <small>{time(conversa.criada_em)}</small>
                      </td>
                      <td>{conversa.setor_nome || 'Escolhendo'}</td>
                      <td>{conversa.atribuido_nome || '—'}</td>
                      <td>
                        <Badge status={conversa.status} />
                      </td>
                      <td>
                        <div className="transfer-cell">
                          <select
                            value={transfers[conversa.id] || ''}
                            onChange={(event) =>
                              setTransfers({ ...transfers, [conversa.id]: event.target.value })
                            }
                          >
                            <option value="">Selecionar</option>
                            {options.map((item) => (
                              <option key={item.id} value={item.id}>
                                {item.nome}
                              </option>
                            ))}
                          </select>
                          <button
                            className="button button-soft"
                            disabled={
                              busy || !transfers[conversa.id] || conversa.status !== 'aberta'
                            }
                            onClick={() => onTransfer(conversa.id, transfers[conversa.id])}
                          >
                            Mover
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
                {!visibleConversations.length && (
                  <tr>
                    <td colSpan="5" className="empty-table">
                      Nenhuma conversa por enquanto.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {tab === 'equipe' && (
        <section className="surface manager-section">
          <div className="section-heading">
            <div>
              <h2>Equipe</h2>
              <p>Somente gestores podem criar e editar acessos.</p>
            </div>
            <span className="count-chip">{users.length} usuários</span>
          </div>
          <form
            className="create-user"
            onSubmit={async (event) => {
              event.preventDefault()
              if (await onCreateUser(newUser))
                setNewUser({
                  nome: '',
                  email: '',
                  senha: '',
                  role: 'colaborador',
                  setor_interno_id: 1,
                })
            }}
          >
            <input
              placeholder="Nome"
              value={newUser.nome}
              onChange={(event) => setNewUser({ ...newUser, nome: event.target.value })}
              required
            />
            <input
              type="email"
              placeholder="Email"
              value={newUser.email}
              onChange={(event) => setNewUser({ ...newUser, email: event.target.value })}
              required
            />
            <input
              type="password"
              placeholder="Senha (8+ caracteres)"
              minLength="8"
              value={newUser.senha}
              onChange={(event) => setNewUser({ ...newUser, senha: event.target.value })}
              required
            />
            <select
              value={newUser.role}
              onChange={(event) => setNewUser({ ...newUser, role: event.target.value })}
            >
              <option value="colaborador">Colaborador</option>
              <option value="supervisor">Supervisor</option>
              <option value="gestor">Gestor</option>
            </select>
            <select
              aria-label="Setor interno do novo usuário"
              value={newUser.setor_interno_id}
              onChange={(event) => setNewUser({ ...newUser, setor_interno_id: event.target.value })}
            >
              {(config?.setores_internos || []).map((item) => (
                <option key={item.id} value={item.id}>
                  {item.nome}
                </option>
              ))}
            </select>
            <button className="button button-primary" disabled={busy}>
              Criar usuário
            </button>
          </form>
          <div className="user-list">
            {users.map((item) => (
              <UserEditor
                key={item.id}
                user={item}
                setoresInternos={config?.setores_internos || []}
                onSave={onSaveUser}
                busy={busy}
              />
            ))}
          </div>
        </section>
      )}
      {tab === 'setores' && (
        <>
          <section className="surface manager-section">
            <div className="section-heading">
              <div>
                <h2>Setores do WhatsApp</h2>
                <p>Os nomes aparecem no menu enviado ao cliente.</p>
              </div>
            </div>
            <div className="sector-list">
              {sectors.map((item) => (
                <SectorEditor
                  key={item.id}
                  sector={item}
                  users={users}
                  onSave={onSaveSector}
                  busy={busy}
                />
              ))}
            </div>
          </section>
          <section className="surface manager-section">
            <div className="section-heading">
              <div>
                <h2>Equipes internas</h2>
                <p>
                  Cadastre qualquer setor. Ao vincular dois membros ativos, o grupo aparece
                  automaticamente no chat interno.
                </p>
              </div>
            </div>
            <form
              className="create-user"
              onSubmit={async (event) => {
                event.preventDefault()
                if (await onCreateInternalSector({ nome: newInternalSector }))
                  setNewInternalSector('')
              }}
            >
              <input
                aria-label="Nova equipe interna"
                placeholder="Nome do novo setor"
                value={newInternalSector}
                onChange={(event) => setNewInternalSector(event.target.value)}
                maxLength="80"
                required
              />
              <button className="button button-primary" disabled={busy}>
                Adicionar setor
              </button>
            </form>
            <div className="sector-list">
              {(config?.setores_internos || []).map((item) => (
                <InternalSectorEditor
                  key={item.id}
                  sector={item}
                  onSave={onSaveInternalSector}
                  busy={busy}
                />
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  )
}

function Simulator({ data, client, setClient, onSend, busy }) {
  const [draft, setDraft] = useState('')
  const chosen = data?.clientes?.find((item) => item.id === client)
  return (
    <div className="sim-page">
      <div className="page-intro">
        <div>
          <div className="eyebrow">AMBIENTE DE TESTE</div>
          <h1>Simulador</h1>
          <p>Teste o fluxo do bot com clientes fictícios antes de conectar o WhatsApp.</p>
        </div>
        <div className="demo-pill">SIMULADO</div>
      </div>
      <div className="sim-grid">
        <section className="surface sim-main">
          <div className="sim-header">
            <div className="sim-avatar">{chosen?.nome?.slice(-1) || '1'}</div>
            <div>
              <h2>{chosen?.nome || 'Cliente'}</h2>
              <p>{chosen?.numero || ''}</p>
            </div>
            <Badge status={data?.status || 'novo'}>
              {data?.status === 'encerrada' ? 'Encerrada' : 'Simulação ativa'}
            </Badge>
          </div>
          <div className="sim-conversation">
            <MessageBubbles messages={data?.mensagens || []} simulator />
          </div>
          <form
            className="sim-composer"
            onSubmit={async (event) => {
              event.preventDefault()
              if (!draft.trim()) return
              if (await onSend(client, draft.trim())) setDraft('')
            }}
          >
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Digite como se fosse o cliente..."
              maxLength="4000"
              required
            />
            <button className="button button-primary" disabled={busy || !draft.trim()}>
              <Icon name="send" size={18} />
              <span>Enviar</span>
            </button>
          </form>
        </section>
        <aside className="sim-side">
          <section className="surface sim-side-card">
            <div className="eyebrow">CLIENTE FICTÍCIO</div>
            <h3>Escolha um número</h3>
            <div className="client-list">
              {(data?.clientes || []).map((item) => (
                <button
                  key={item.id}
                  className={client === item.id ? 'active' : ''}
                  onClick={() => setClient(item.id)}
                >
                  <span className="mini-avatar">{item.nome.slice(-1)}</span>
                  <span>
                    <strong>{item.nome}</strong>
                    <small>{item.numero}</small>
                  </span>
                </button>
              ))}
            </div>
          </section>
          <section className="surface sim-side-card guide-card">
            <div className="eyebrow">ROTEIRO RÁPIDO</div>
            <h3>Como testar</h3>
            <ol>
              <li>Envie uma saudação para ver o menu.</li>
              <li>
                Escolha <strong>1</strong> para Vendas ou <strong>2–4</strong> para outro setor.
              </li>
              <li>
                Em Vendas, escolha um vendedor ou <strong>0</strong> para o próximo disponível.
              </li>
            </ol>
            <p>Depois da atribuição, o bot só volta a falar se o timer disparar.</p>
          </section>
        </aside>
      </div>
    </div>
  )
}

export default function App() {
  const [me, setMe] = useState(undefined)
  const [imagemModal, setImagemModal] = useState(null)
  const [page, setPage] = useState('inbox')
  const [conversations, setConversations] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [config, setConfig] = useState(null)
  const [whatsappStatus, setWhatsappStatus] = useState(null)
  const [simData, setSimData] = useState(null)
  const [chamados, setChamados] = useState([])
  const [computadores, setComputadores] = useState([])
  const [client, setClient] = useState('cliente1')
  const [search, setSearch] = useState('')
  const [vendorFilter, setVendorFilter] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [naoLidas, setNaoLidas] = useState({ whatsapp: [], interno: [] })
  const [internoNaoLidasTotal, setInternoNaoLidasTotal] = useState(0)
  const naoLidasRef = useRef({ whatsapp: [], interno: [] })
  const [avisoEvento, setAvisoEvento] = useState(null)
  const cursores = useRef({ whatsapp: 0, interno: 0 })
  const eventosProntos = useRef(false)
  const [colegaAlvoId, setColegaAlvoId] = useState(null)
  // Controle de respostas fora de ordem no polling: só a consulta mais recente, da conversa e da busca
  // atuais, pode atualizar a tela.
  const selectedIdRef = useRef(null)
  selectedIdRef.current = selectedId
  const paginaRef = useRef(page)
  paginaRef.current = page
  const buscaRef = useRef(search)
  buscaRef.current = search
  const listaSeq = useRef(0)
  const detalheSeq = useRef(0)

  useEffect(() => {
    getJSON('/api/me')
      .then((user) => {
        setMe(user)
        setPage(initialPage(user.role))
      })
      .catch(() => setMe(null))
  }, [])

  useEffect(() => {
    if (!me) return
    const batida = async () => {
      if (document.visibilityState !== 'visible') return
      try {
        await fetch('/api/presenca', { method: 'POST', credentials: 'same-origin' })
      } catch { /* A próxima consulta tenta novamente. */ }
    }
    batida()
    const intervalo = setInterval(batida, (me.presenca_intervalo_segundos || 30) * 1000)
    document.addEventListener('visibilitychange', batida)
    return () => { clearInterval(intervalo); document.removeEventListener('visibilitychange', batida) }
  }, [me?.id])

  useEffect(() => {
    if (!me) return
    let ativo = true
    const atualizar = async () => {
      try {
        const resumo = await getJSON('/api/interno/conversas')
        if (ativo) setInternoNaoLidasTotal(resumo.nao_lidas)
      } catch { /* Mantém o último contador até a próxima consulta. */ }
    }
    atualizar()
    const intervalo = setInterval(atualizar, 3000)
    return () => { ativo = false; clearInterval(intervalo) }
  }, [me?.id])

  useEffect(() => {
    if (!me) return
    let cancelado = false
    let consultando = false
    let intervalo
    const chave = `fortgiro-eventos-v2-${me.id}`
    async function iniciar() {
      if (cancelado) return
      try {
        const salvo = JSON.parse(localStorage.getItem(chave) || 'null')
        if (salvo) {
          cursores.current = salvo.cursores
          naoLidasRef.current = salvo.naoLidas || { whatsapp: [], interno: [] }
          setNaoLidas(naoLidasRef.current)
        } else {
          const inicio = await getJSON('/api/eventos?inicio=true')
          if (cancelado) return
          cursores.current = { whatsapp: inicio.ultimo_whatsapp, interno: inicio.ultimo_interno }
          naoLidasRef.current = { whatsapp: inicio.whatsapp, interno: inicio.interno }
          setNaoLidas(naoLidasRef.current)
          if (inicio.whatsapp.length || inicio.interno.length) {
            const recentes = inicio.interno.length ? inicio.interno : inicio.whatsapp
            setAvisoEvento({
              tipo: inicio.interno.length ? 'interno' : 'whatsapp',
              quantidade: inicio.whatsapp.length + inicio.interno.length,
              item: recentes.at(-1),
            })
          }
          localStorage.setItem(
            chave,
            JSON.stringify({ cursores: cursores.current, naoLidas: naoLidasRef.current }),
          )
        }
        eventosProntos.current = true
        await consultar()
        intervalo = setInterval(consultar, 3000)
      } catch {
        if (!cancelado) setTimeout(iniciar, 3000)
      }
    }
    async function consultar() {
      if (consultando || cancelado) return
      consultando = true
      try {
        const parametros = new URLSearchParams({
          whatsapp_apos: cursores.current.whatsapp,
          interno_apos: cursores.current.interno,
        })
        const dados = await getJSON(`/api/eventos?${parametros}`)
        if (cancelado) return
        cursores.current = { whatsapp: dados.ultimo_whatsapp, interno: dados.ultimo_interno }
        if (dados.whatsapp.length || dados.interno.length) {
          naoLidasRef.current = {
            whatsapp: [...naoLidasRef.current.whatsapp, ...dados.whatsapp],
            interno: [...naoLidasRef.current.interno, ...dados.interno],
          }
          setNaoLidas(naoLidasRef.current)
          const recentes = dados.interno.length ? dados.interno : dados.whatsapp
          setAvisoEvento({
            tipo: dados.interno.length ? 'interno' : 'whatsapp',
            quantidade: naoLidasRef.current.whatsapp.length + naoLidasRef.current.interno.length,
            item: recentes.at(-1),
          })
        }
      } catch {
        /* Sem conexão: a consulta seguinte usa os mesmos cursores. */
      } finally {
        consultando = false
      }
    }
    iniciar()
    return () => {
      cancelado = true
      clearInterval(intervalo)
      eventosProntos.current = false
    }
  }, [me?.id])

  useEffect(() => {
    if (!me || !eventosProntos.current) return
    const resumo = {
      whatsapp: naoLidas.whatsapp.map((item) => ({ id: item.id, conversa_id: item.conversa_id })),
      interno: naoLidas.interno.map((item) => ({ id: item.id, remetente_id: item.remetente_id })),
    }
    localStorage.setItem(
      `fortgiro-eventos-v2-${me.id}`,
      JSON.stringify({ cursores: cursores.current, naoLidas: resumo }),
    )
  }, [naoLidas, me?.id])

  useEffect(() => {
    if (!avisoEvento) return
    const prazo = setTimeout(() => setAvisoEvento(null), 8000)
    return () => clearTimeout(prazo)
  }, [avisoEvento])

  function marcarLidas(tipo, alvoId) {
    naoLidasRef.current = {
      ...naoLidasRef.current,
      [tipo]: naoLidasRef.current[tipo].filter((item) =>
        tipo === 'whatsapp' ? item.conversa_id !== alvoId : item.remetente_id !== alvoId,
      ),
    }
    setNaoLidas(naoLidasRef.current)
  }

  useEffect(() => {
    const voltar = () => {
      if (me) setPage(initialPage(me.role))
    }
    window.addEventListener('popstate', voltar)
    return () => window.removeEventListener('popstate', voltar)
  }, [me])

  const refreshConversations = useCallback(async () => {
    if (!me) return
    const seq = ++listaSeq.current
    const query = new URLSearchParams()
    if (paginaRef.current === 'inbox' && buscaRef.current.trim())
      query.set('q', buscaRef.current.trim())
    try {
      const dados = await getJSON(`/api/atendimentos?${query}`)
      if (seq === listaSeq.current) setConversations(dados)
    } catch (failure) {
      if (seq === listaSeq.current) setError(failure.message)
    }
  }, [me, page, search])

  const refreshDetail = useCallback(async () => {
    const id = selectedId
    if (!id || page !== 'inbox' || selectedIdRef.current !== id) return
    const seq = ++detalheSeq.current
    const vigente = () => seq === detalheSeq.current && selectedIdRef.current === id
    try {
      const dados = await getJSON(`/api/atendimentos/${id}`)
      if (vigente()) setDetail(dados)
    } catch (failure) {
      if (!vigente()) return
      setDetail(null)
      if (failure.status === 404) setSelectedId((current) => (current === id ? null : current))
      else setError(failure.message)
    }
  }, [selectedId, page])

  const refreshConfig = useCallback(async () => {
    if (me?.role !== 'gestor') return
    try {
      setConfig(await getJSON('/api/gestor/config'))
    } catch (failure) {
      setError(failure.message)
    }
  }, [me])

  const refreshTickets = useCallback(async () => {
    if (!me) return
    try {
      const meus = me.role === 'colaborador'
      const [lista, pcs] = await Promise.all([
        getJSON(meus ? '/api/meus-chamados' : '/api/chamados'),
        getJSON(meus ? '/api/meus-chamados/computadores' : '/api/computadores'),
      ])
      setChamados(lista)
      setComputadores(pcs)
    } catch (failure) {
      setError(failure.message)
    }
  }, [me])

  const refreshSimulator = useCallback(async () => {
    if (page !== 'simulator') return
    try {
      setSimData(await getJSON(`/api/simulador?cliente=${client}`))
    } catch (failure) {
      setError(failure.message)
    }
  }, [page, client])

  useEffect(() => {
    if (!me) return
    refreshConversations()
    const interval = setInterval(refreshConversations, 3000)
    return () => {
      clearInterval(interval)
      listaSeq.current++
    }
  }, [me, page, refreshConversations])
  useEffect(() => {
    if (!selectedId || page !== 'inbox') return
    refreshDetail()
    const interval = setInterval(refreshDetail, 3000)
    return () => {
      clearInterval(interval)
      detalheSeq.current++
    }
  }, [selectedId, page, refreshDetail])
  useEffect(() => {
    if (
      page === 'inbox' &&
      selectedId &&
      detail?.mensagens &&
      naoLidas.whatsapp.some((item) => item.conversa_id === selectedId)
    ) {
      marcarLidas('whatsapp', selectedId)
    }
  }, [page, selectedId, detail?.mensagens?.length, naoLidas.whatsapp.length])
  useEffect(() => {
    if (page !== 'inbox' || !selectedId || detail?.conversa?.id !== selectedId) return
    const confirmar = () => {
      if (document.visibilityState !== 'visible') return
      fetch(`/api/atendimentos/${selectedId}/leitura`, {
        method: 'POST',
        credentials: 'same-origin',
      })
        .then((resposta) => {
          if (resposta.ok) refreshConversations()
        })
        .catch(() => {})
    }
    confirmar()
    document.addEventListener('visibilitychange', confirmar)
    return () => document.removeEventListener('visibilitychange', confirmar)
  }, [page, selectedId, detail?.conversa?.id, detail?.mensagens?.length, refreshConversations])
  useEffect(() => {
    if (me?.role === 'gestor') refreshConfig()
  }, [me?.id, refreshConfig])
  useEffect(() => {
    if (me?.role === 'gestor' && page === 'simulator' && config && !config.simulador_ativo) {
      setPage('manager')
      window.history.replaceState({}, '', routeByPage.manager)
    }
  }, [me?.role, page, config?.simulador_ativo])
  useEffect(() => {
    if (page !== 'manager') return
    refreshConfig()
    const refreshStatus = () =>
      getJSON('/api/gestor/whatsapp-status')
        .then((data) => setWhatsappStatus(data.status))
        .catch(() => setWhatsappStatus('desconectado'))
    refreshStatus()
    const interval = setInterval(refreshStatus, 10000)
    return () => clearInterval(interval)
  }, [page, refreshConfig])
  useEffect(() => {
    if (page !== 'tickets') return
    refreshTickets()
    const interval = setInterval(refreshTickets, 3000)
    return () => clearInterval(interval)
  }, [page, refreshTickets])
  useEffect(() => {
    if (page !== 'simulator') return
    refreshSimulator()
    const interval = setInterval(refreshSimulator, 3000)
    return () => clearInterval(interval)
  }, [page, refreshSimulator])

  async function login(values) {
    setBusy(true)
    setError('')
    try {
      await postForm('/api/auth/login', values)
      const user = await getJSON('/api/me')
      setMe(user)
      const next = initialPage(user.role)
      setPage(next)
      window.history.replaceState({}, '', routeByPage[next])
    } catch {
      setError('Email ou senha inválidos.')
    } finally {
      setBusy(false)
    }
  }

  async function logout() {
    try {
      await postForm('/api/auth/logout', {})
    } catch {
      /* O estado local também é limpo. */
    }
    naoLidasRef.current = { whatsapp: [], interno: [] }
    setMe(null)
    setDetail(null)
    setConversations([])
    setNaoLidas(naoLidasRef.current)
    setAvisoEvento(null)
    setError('')
    window.history.replaceState({}, '', '/login')
  }

  async function action(path, values, success = 'Alterações salvas.', clearSelection = false) {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await postForm(path, values)
      setNotice(success)
      if (clearSelection) {
        setSelectedId(null)
        setDetail(null)
      }
      await Promise.all([
        refreshConversations(),
        clearSelection ? Promise.resolve() : refreshDetail(),
        refreshConfig(),
        refreshSimulator(),
        refreshTickets(),
      ])
      return true
    } catch (failure) {
      setError(failure.message)
      await Promise.all([refreshConversations(), refreshDetail(), refreshTickets()])
      return false
    } finally {
      setBusy(false)
    }
  }

  async function actionRaw(path, options, success = 'Alterações salvas.') {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const response = await fetch(path, {
        credentials: 'same-origin',
        ...options,
      })
      if (!response.ok) {
        let message = `Não foi possível concluir (${response.status}).`
        try {
          const data = await response.json()
          if (data.detail) message = typeof data.detail === 'string' ? data.detail : message
        } catch {}
        throw new Error(message)
      }
      setNotice(success)
      await Promise.all([
        refreshConversations(),
        refreshDetail(),
        refreshConfig(),
        refreshSimulator(),
        refreshTickets(),
      ])
      return true
    } catch (failure) {
      setError(failure.message)
      await Promise.all([refreshConversations(), refreshDetail(), refreshTickets()])
      return false
    } finally {
      setBusy(false)
    }
  }

  function navigate(next) {
    setPage(next)
    window.history.pushState({}, '', routeByPage[next])
    setError('')
    setNotice('')
  }
  function abrirAviso() {
    if (!avisoEvento) return
    if (avisoEvento.tipo === 'interno') {
      setColegaAlvoId(avisoEvento.item.remetente_id)
      marcarLidas('interno', avisoEvento.item.remetente_id)
      navigate('interno')
    } else {
      setSelectedId(avisoEvento.item.conversa_id)
      setDetail(null)
      marcarLidas('whatsapp', avisoEvento.item.conversa_id)
      navigate('inbox')
    }
    setAvisoEvento(null)
  }
  const headerTitle = useMemo(
    () =>
      page === 'manager'
        ? 'Gestão'
        : page === 'simulator'
          ? 'Simulador'
          : page === 'tickets'
            ? 'Chamados'
            : page === 'interno'
              ? 'Chat interno'
              : page === 'perfil'
                ? 'Minha conta'
                : 'Atendimentos',
    [page],
  )

  if (me === undefined)
    return (
      <div className="loading-screen">
        <Brand compact />
        <div className="loading-bar" />
      </div>
    )
  if (me === null) return <Login onLogin={login} busy={busy} error={error} />

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-top">
          <Brand />
          <div className="sidebar-caption">PAINEL DE CONTROLE</div>
          <nav aria-label="Navegação principal">
            <button className={page === 'inbox' ? 'active' : ''} onClick={() => navigate('inbox')}>
              <Icon name="inbox" />
              Atendimentos
              {conversations.reduce((total, item) => total + (item.nao_lidas || 0), 0) > 0 && (
                <span className="nav-count">
                  {conversations.reduce((total, item) => total + (item.nao_lidas || 0), 0)}
                </span>
              )}
            </button>
            <button
              className={page === 'tickets' ? 'active' : ''}
              onClick={() => navigate('tickets')}
            >
              <Icon name="ticket" />
              Chamados
            </button>
            <button
              className={page === 'interno' ? 'active' : ''}
              onClick={() => navigate('interno')}
            >
              <Icon name="chat" />
              Chat interno
              {internoNaoLidasTotal > 0 && (
                <span className="nav-count">{internoNaoLidasTotal}</span>
              )}
            </button>
            <button
              className={page === 'perfil' ? 'active' : ''}
              onClick={() => navigate('perfil')}
            >
              <Icon name="users" />
              Minha conta
            </button>
            {me.role === 'gestor' && (
              <>
                <button
                  className={page === 'manager' ? 'active' : ''}
                  onClick={() => navigate('manager')}
                >
                  <Icon name="grid" />
                  Visão do gestor
                </button>
                {config?.simulador_ativo && (
                  <button
                    className={page === 'simulator' ? 'active' : ''}
                    onClick={() => navigate('simulator')}
                  >
                    <Icon name="chat" />
                    Simulador
                  </button>
                )}
              </>
            )}
          </nav>
        </div>
        <div className="sidebar-bottom">
          <div className="sidebar-help">
            <span className="help-dot" />
            Central FortGiro <small>Atendimento em operação</small>
          </div>
          <div className="sidebar-user">
            <button
              type="button"
              className="user-avatar user-avatar-btn"
              onClick={() => me.foto_url && setImagemModal({ url: me.foto_url, titulo: me.nome })}
              disabled={!me.foto_url}
              title={me.foto_url ? 'Visualizar foto do perfil' : undefined}
              aria-label={me.foto_url ? 'Visualizar foto do perfil' : 'Foto do perfil'}
            >
              {me.foto_url ? <img className="int-avatar-photo" src={me.foto_url} alt="" /> : initials(me.nome)}
            </button>
            <span>
              <strong>{me.nome}</strong>
              <small>{roleName[me.role] || me.role}</small>
            </span>
            <button onClick={logout} title="Sair" aria-label="Sair">
              <Icon name="logout" />
            </button>
          </div>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            FortGiro <span>/</span> <strong>{headerTitle}</strong>
          </div>
          <div className="topbar-right">
            <span className="topbar-date">
              {new Date().toLocaleDateString('pt-BR', { day: '2-digit', month: 'long' })}
            </span>
            <button
              type="button"
              className="topbar-avatar topbar-avatar-btn"
              onClick={() => me.foto_url && setImagemModal({ url: me.foto_url, titulo: me.nome })}
              disabled={!me.foto_url}
              title={me.foto_url ? 'Visualizar foto do perfil' : undefined}
              aria-label={me.foto_url ? 'Visualizar foto do perfil' : 'Foto do perfil'}
            >
              {me.foto_url ? <img className="int-avatar-photo" src={me.foto_url} alt="" /> : initials(me.nome)}
            </button>
          </div>
        </header>
        {avisoEvento && (
          <button className="event-toast" onClick={abrirAviso}>
            <strong>
              {avisoEvento.quantidade}{' '}
              {avisoEvento.quantidade === 1 ? 'nova mensagem' : 'novas mensagens'}
            </strong>
            <span>
              {avisoEvento.tipo === 'interno' ? avisoEvento.item.nome : avisoEvento.item.numero}:{' '}
              {avisoEvento.item.texto}
            </span>
            <small>Clique para abrir</small>
          </button>
        )}
        {(error || notice) && (
          <div className={`toast ${error ? 'toast-error' : 'toast-success'}`} role="status">
            {error || notice}
            <button
              onClick={() => {
                setError('')
                setNotice('')
              }}
            >
              ×
            </button>
          </div>
        )}
        {page === 'inbox' && (
          <Inbox
            me={me}
            conversations={conversations}
            selectedId={selectedId}
            onSelect={(id) => {
              setSelectedId(id)
              setDetail(null)
              marcarLidas('whatsapp', id)
            }}
            detail={detail}
            search={search}
            setSearch={setSearch}
            busy={busy}
            onSend={async (id, texto, imagem) => {
              if (imagem) {
                try {
                  const webp = await converterWebp(imagem)
                  const query = texto ? `?${new URLSearchParams({ texto })}` : ''
                  return await actionRaw(
                    `/api/atendimentos/${id}/mensagens${query}`,
                    {
                      method: 'POST',
                      headers: { 'Content-Type': 'image/webp' },
                      body: webp,
                    },
                    'Resposta enviada.',
                  )
                } catch (falha) {
                  setError(falha.message)
                  return false
                }
              }
              return action(`/api/atendimentos/${id}/mensagens`, { texto }, 'Resposta enviada.')
            }}
            onImagem={(url, titulo) => setImagemModal({ url, titulo: titulo || 'Imagem da mensagem' })}
            onRetry={(id, messageId) =>
              action(
                `/api/atendimentos/${id}/mensagens/${messageId}/reenviar`,
                {},
                'Mensagem reenviada.',
              )
            }
            onTransfer={(id, destino) =>
              action(
                `/api/atendimentos/${id}/transferir`,
                { destino },
                'Conversa transferida.',
                true,
              )
            }
            onUploadPhoto={async (id, arquivo) => {
              setBusy(true)
              setError('')
              try {
                const webp = await converterWebp(arquivo, 512)
                const resposta = await fetch(`/api/atendimentos/${id}/foto`, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'image/webp' }, body: webp })
                if (!resposta.ok) throw new Error('Não foi possível salvar a foto do contato.')
                await Promise.all([refreshConversations(), refreshDetail()])
                setNotice('Foto do contato salva pela equipe.')
              } catch (falha) {
                setError(falha.message)
              } finally {
                setBusy(false)
              }
            }}
            onClose={(id) =>
              action(`/api/atendimentos/${id}/encerrar`, {}, 'Conversa encerrada.').then((ok) => {
                if (ok) {
                  setSelectedId(null)
                  setDetail(null)
                }
              })
            }
          />
        )}
        {page === 'manager' && (
          <Manager
            conversations={conversations}
            config={config}
            whatsappStatus={whatsappStatus}
            vendorFilter={vendorFilter}
            setVendorFilter={setVendorFilter}
            busy={busy}
            onOpen={(id) => {
              setSelectedId(id)
              setDetail(null)
              marcarLidas('whatsapp', id)
              navigate('inbox')
            }}
            onTransfer={(id, usuario_id) =>
              action(
                `/api/gestor/conversas/${id}/transferir`,
                { usuario_id },
                'Conversa transferida.',
              )
            }
            onCreateUser={(values) => action('/api/gestor/usuarios', values, 'Usuário criado.')}
            onSaveUser={(id, values) =>
              action(
                `/api/gestor/usuarios/${id}`,
                {
                  nome: values.nome,
                  email: values.email,
                  role: values.role,
                  ativo: values.ativo ? 'on' : '',
                  online: values.online ? 'on' : '',
                  senha: values.senha,
                  setor_interno_id: values.setor_interno_id,
                },
                'Usuário atualizado.',
              )
            }
            onSaveSector={(id, values) =>
              action(`/api/gestor/setores/${id}`, values, 'Setor atualizado.')
            }
            onCreateInternalSector={(values) =>
              action('/api/gestor/setores-internos', values, 'Setor interno criado.')
            }
            onSaveInternalSector={(id, values) =>
              action(`/api/gestor/setores-internos/${id}`, values, 'Setor interno atualizado.')
            }
            onToggleSimulator={(ativo) =>
              action(
                '/api/gestor/simulador',
                { ativo: ativo ? 'on' : 'off' },
                ativo ? 'Simulador ativado.' : 'Simulador desativado.',
              )
            }
          />
        )}
        {page === 'tickets' &&
          (me.role === 'colaborador' ? (
            <ChamadosVendedor
              chamados={chamados}
              computadores={computadores}
              busy={busy}
              onCreate={(values) =>
                action(
                  '/api/meus-chamados',
                  values,
                  'Chamado aberto. A equipe de suporte já pode vê-lo.',
                )
              }
            />
          ) : (
            <Chamados
              me={me}
              chamados={chamados}
              computadores={computadores}
              usuarios={config?.usuarios || []}
              busy={busy}
              onRequest={(id) =>
                action(`/api/chamados/${id}/acessos`, {}, 'Acesso remoto simulado e registrado.')
              }
              onClose={(id, solucao) =>
                action(
                  `/api/chamados/${id}/fechar`,
                  { solucao },
                  'Chamado fechado com solução registrada.',
                )
              }
              onCreateComputer={(values) =>
                action('/api/computadores', values, 'Computador cadastrado.')
              }
            />
          ))}
        {page === 'interno' && (
          <Interno
            me={me}
            abrirColegaId={colegaAlvoId}
            onOpen={(id) => marcarLidas('interno', id)}
            onUnreadChange={setInternoNaoLidasTotal}
            onVisualizarImagem={(url, titulo) => setImagemModal({ url, titulo })}
          />
        )}
        {page === 'perfil' && (
          <Perfil
            me={me}
            onVisualizarFoto={(url, titulo) => setImagemModal({ url, titulo })}
            onEnviarFoto={async (arquivo) => {
              const corpo = await converterWebp(arquivo, 512)
              const resposta = await fetch('/api/me/foto', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'image/webp' },
                body: corpo,
              })
              if (!resposta.ok) throw new Error('Não foi possível enviar a foto.')
              const dados = await resposta.json()
              setMe((anterior) => ({ ...anterior, foto_url: dados.foto_url }))
              return true
            }}
          />
        )}
        {page === 'simulator' && config?.simulador_ativo && (
          <Simulator
            data={simData}
            client={client}
            setClient={setClient}
            busy={busy}
            onSend={(cliente, texto) =>
              action('/api/simulador', { cliente, texto }, 'Mensagem enviada no simulador.')
            }
          />
        )}
      </main>
      {imagemModal && (
        <ModalImagem
          url={imagemModal.url}
          titulo={imagemModal.titulo}
          alt={imagemModal.alt}
          onFechar={() => setImagemModal(null)}
        />
      )}
    </div>
  )
}
