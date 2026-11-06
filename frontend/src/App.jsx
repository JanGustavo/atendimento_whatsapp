import React, { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Chamados, { ChamadosVendedor } from './Chamados.jsx'
import { messageDay, messageDateTime, readDateTime } from './dates.js'
import { formatPhone } from './phones.js'
import { copiarTexto } from './clipboard.js'
import Interno, { Icone, PAPEL_PAREDE_OPACIDADE, PAPEL_PAREDE_TOM, lerPapelParede, salvarPapelParede } from './Interno.jsx'
import Perfil from './Perfil.jsx'
import ModalImagem from './ModalImagem.jsx'
import { converterWebp } from './images.js'
import { feriadosNacionais } from './feriados.js'
import { requisitar as fetchApi, obterJSON as getJSON, enviarFormulario as postForm } from './api.js'

const roleName = { gestor: 'Gestor', supervisor: 'Supervisor', colaborador: 'Colaborador' }
const nomeDemonstracao = (tipo, id) => `${tipo} ${String(id || 1).padStart(2, '0')}`
const usuarioDemonstracao = usuario => usuario && ({ ...usuario, nome: nomeDemonstracao(({ gestor: 'Gestor', supervisor: 'Supervisor' })[usuario.role] || 'Colaborador', usuario.id), email: `usuario${usuario.id}@exemplo.test`, foto_url: null })
const conversaDemonstracao = conversa => conversa && ({ ...conversa, numero: nomeDemonstracao('Cliente', conversa.id), nome_contato: 'Contato fictício', foto_url: null, atribuido_nome: conversa.atribuido_id ? nomeDemonstracao('Colaborador', conversa.atribuido_id) : null })
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
const SETOR_ICONES = [
  ['equipe', 'Equipe'], ['vendas', 'Vendas/Compra'], ['estoque', 'Estoque'],
  ['garantia', 'Garantia'], ['devolucao', 'Devolução'],
  ['atendimento', 'Atendimento'], ['administracao', 'Administração'],
]

function SeletorIcone({ valor, onChange }) {
  const [aberto, setAberto] = useState(false)
  const ref = useRef(null)
  useEffect(() => {
    if (!aberto) return
    const fechar = evento => {
      if (evento.key === 'Escape' || (evento.type === 'pointerdown' && !ref.current?.contains(evento.target))) setAberto(false)
    }
    document.addEventListener('pointerdown', fechar)
    document.addEventListener('keydown', fechar)
    return () => { document.removeEventListener('pointerdown', fechar); document.removeEventListener('keydown', fechar) }
  }, [aberto])
  return <div className="manager-icon-picker" ref={ref}><span>Ícone</span>
    <button type="button" className="manager-icon-trigger" aria-label="Escolher ícone do setor" aria-expanded={aberto} onClick={() => setAberto(!aberto)}>
      <Icone nome={valor} tamanho={18} />{SETOR_ICONES.find(item => item[0] === valor)?.[1] || 'Equipe'} <span aria-hidden="true">⌄</span>
    </button>
    {aberto && <div className="manager-icon-menu" role="group" aria-label="Ícones do setor">
      {SETOR_ICONES.map(([id, nome]) => <button key={id} type="button" className={id === valor ? 'is-selected' : ''} aria-label={nome} aria-pressed={id === valor} title={nome} onClick={() => { onChange(id); setAberto(false) }}><Icone nome={id} tamanho={21} /><small>{nome}</small></button>)}
    </div>}
  </div>
}

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

function time(value) {
  return messageDateTime(value)
}

function initials(name = '') {
  const partes = name.split(/\s+/).filter(Boolean)
  const numero = partes.at(-1)?.match(/^0*(\d+)$/)
  if (numero) return `${partes[0]?.[0]?.toUpperCase() || 'C'}${numero[1]}`
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
    mic: <><rect x="9" y="2" width="6" height="13" rx="3" /><path d="M5 10a7 7 0 0 0 14 0M12 17v5m-4 0h8" /></>,
    copy: <><rect x="8" y="8" width="12" height="13" rx="2" /><path d="M16 8V5a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h2" /></>,
    options: <path d="m7 10 5 5 5-5" />,
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
    person: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
  }
  return <svg {...common}>{paths[name]}</svg>
}

function AvatarContato({ nome, fotoUrl, grande = false }) {
  // Nomes do WhatsApp podem usar letras Unicode estilizadas sem glifos na fonte do painel.
  const iniciaisContato = nome?.normalize('NFKC').trim().split(/\s+/).filter(Boolean).slice(0, 2).map((parte) => parte[0].toUpperCase()).join('')
  return <span className={`contact-avatar${grande ? ' contact-avatar-large' : ''}`} aria-hidden="true">
    <span className="contact-avatar-fallback">{iniciaisContato || <Icon name="person" size={grande ? 25 : 20} />}</span>
    {fotoUrl && <img key={fotoUrl} src={fotoUrl} alt="" onError={(event) => { event.currentTarget.hidden = true }} />}
  </span>
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

function MessageBubbles({ messages, simulator = false, onRetry, onEdit, onDiscard, onImagem, currentUserId, contactName, contactPhoto, busy = false }) {
  const bottom = React.useRef(null)
  const [editId, setEditId] = useState(null)
  const [editText, setEditText] = useState('')
  const [menuId, setMenuId] = useState(null)
  const [copiaStatus, setCopiaStatus] = useState('')
  useEffect(() => { if (!copiaStatus) return undefined; const id = setTimeout(() => setCopiaStatus(''), 2400); return () => clearTimeout(id) }, [copiaStatus])
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
              <div className={`message-bubble ${outgoing ? 'message-bubble-outgoing' : ''}${!simulator && message.origem === 'cliente' ? ' wpp-bubble-with-avatar' : ''}`}>
                {!simulator && message.origem === 'cliente' && <span className="wpp-message-avatar"><AvatarContato nome={contactName} fotoUrl={contactPhoto} /></span>}
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
                {message.audio_url && <audio controls preload="metadata" src={message.audio_url} aria-label="Áudio da conversa" />}
                {editId === message.id ? (
                  <form className="failed-message-editor" onSubmit={async (event) => {
                    event.preventDefault()
                    if (await onEdit(message.id, editText)) setEditId(null)
                  }}>
                    <textarea aria-label="Editar mensagem com falha" value={editText} onChange={(event) => setEditText(event.target.value)} maxLength={4000} rows={3} required={!message.imagem_url} />
                    <div className="failed-message-actions">
                      <button type="submit" disabled={busy}>Salvar</button>
                      <button type="button" disabled={busy} onClick={() => setEditId(null)}>Cancelar</button>
                    </div>
                  </form>
                ) : message.texto && <div className="message-text">{message.texto}</div>}
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
                      {message.lida_em ? ` às ${readDateTime(message.lida_em)}` : ''}
                    </span>
                  )}
                </time>
                {!simulator && message.texto && editId !== message.id && <div className="int-message-options">
                  <button type="button" className="int-message-menu-trigger" aria-label="Opções da mensagem" aria-expanded={menuId === message.id} onClick={() => setMenuId(menuId === message.id ? null : message.id)}><Icon name="options" size={15} /></button>
                  {menuId === message.id && <div className="int-message-menu">
                    <button type="button" title="Copiar mensagem" aria-label="Copiar mensagem" onClick={async () => { const ok = await copiarTexto(message.texto); setCopiaStatus(ok ? 'Mensagem copiada.' : 'Não foi possível copiar.'); setMenuId(null) }}><Icon name="copy" size={17} /></button>
                  </div>}
                </div>}
                {!simulator &&
                  message.origem === 'humano' &&
                  message.envio_status === 'falhou' &&
                  message.autor_id === currentUserId &&
                  onRetry && editId !== message.id && (
                    <div className="failed-message-actions">
                      <button className="retry-message" disabled={busy} onClick={() => onRetry(message.id)}>Reenviar</button>
                      {!message.audio_url && !message.texto?.startsWith('Template: ') && <button className="retry-message" disabled={busy} onClick={() => { setEditId(message.id); setEditText(message.texto) }}>Editar</button>}
                      <button className="retry-message" disabled={busy} onClick={() => {
                        if (window.confirm('Descartar o registro local desta mensagem com falha? Em falhas de rede, confira o WhatsApp do cliente: ela pode ter sido entregue.')) onDiscard(message.id)
                      }}>Descartar</button>
                    </div>
                  )}
              </div>
            </div>
          </React.Fragment>
        )
      })}
      <div ref={bottom} />
      {copiaStatus && <div className="copy-feedback" role="status" onClick={() => setCopiaStatus('')}>{copiaStatus}</div>}
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
  { id: 'arquivadas', nome: 'Arquivadas' },
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
  onEdit,
  onDiscard,
  onClose,
  onArchive,
  onCreateContact,
  onSendAudio,
  onSendTemplate,
  onTransfer,
  onUploadPhoto,
  onImagem,
  papelParede,
  opacidadePapelParede,
  busy,
}) {
  const [draft, setDraft] = useState('')
  const [destino, setDestino] = useState('')
  const [filtro, setFiltro] = useState('todas')
  const [imagemWpp, setImagemWpp] = useState(null)
  const [novoContato, setNovoContato] = useState(false)
  const [contatoNome, setContatoNome] = useState('')
  const [contatoNumero, setContatoNumero] = useState('')
  const [contatoOptin, setContatoOptin] = useState(false)
  const [gravando, setGravando] = useState(false)
  const [segundosGravacao, setSegundosGravacao] = useState(0)
  const [anexosAbertos, setAnexosAbertos] = useState(false)
  const [previaWpp, setPreviaWpp] = useState(null)
  const destinoRef = useRef(null)
  const fotoRef = useRef(null)
  const arquivoWppRef = useRef(null)
  const audioWppRef = useRef(null)
  const gravadorRef = useRef(null)
  const cancelarGravacaoRef = useRef(false)
  const campoWppRef = useRef(null)
  // Sempre aponta para a conversa aberta agora: respostas assíncronas de outra conversa são ignoradas.
  const selectedIdRef = useRef(selectedId)
  selectedIdRef.current = selectedId
  useEffect(() => setDraft(''), [selectedId])
  useEffect(() => setDestino(''), [selectedId])
  useEffect(() => { setImagemWpp(null); setPreviaWpp(null) }, [selectedId])
  useEffect(() => setAnexosAbertos(false), [selectedId])
  useEffect(() => {
    if (!gravando) return undefined
    const intervalo = window.setInterval(() => setSegundosGravacao((valor) => valor + 1), 1000)
    return () => window.clearInterval(intervalo)
  }, [gravando])

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

  async function alternarGravacao() {
    if (gravadorRef.current) {
      gravadorRef.current.stop()
      return
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      window.alert('Gravação indisponível neste navegador. Anexe um arquivo MP3 ou OGG.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const tipo = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/webm'].find((item) => MediaRecorder.isTypeSupported(item))
      if (!tipo) { stream.getTracks().forEach((track) => { track.stop() }); window.alert('Formato de gravação não suportado. Anexe um arquivo MP3 ou OGG.'); return }
      const gravador = new MediaRecorder(stream, { mimeType: tipo })
      const partes = []
      const conversaId = selected.id
      gravador.ondataavailable = (event) => { if (event.data.size) partes.push(event.data) }
      gravador.onstop = async () => {
        stream.getTracks().forEach((track) => { track.stop() })
        gravadorRef.current = null
        setGravando(false)
        if (cancelarGravacaoRef.current) { cancelarGravacaoRef.current = false; return }
        if (!partes.length) return
        const mime = tipo.startsWith('audio/ogg') ? 'audio/ogg' : 'audio/webm'
        await onSendAudio(conversaId, new Blob(partes, { type: mime }))
      }
      gravadorRef.current = gravador
      cancelarGravacaoRef.current = false
      setSegundosGravacao(0)
      gravador.start()
      setGravando(true)
    } catch { window.alert('Não foi possível acessar o microfone. Confira a permissão do navegador.') }
  }

  function cancelarGravacao() {
    if (!gravadorRef.current) return
    cancelarGravacaoRef.current = true
    gravadorRef.current.stop()
  }

  // Só exibe o detalhe que pertence à conversa selecionada; um detalhe antigo nunca aparece.
  const temSelecao = selectedId !== null && selectedId !== undefined
  const atual = temSelecao && detail?.conversa?.id === selectedId ? detail : null
  const selected = atual?.conversa
  const janelaBloqueada = me.whatsapp_provider === 'meta' && atual?.janela_texto_aberta === false

  const contagens = useMemo(
    () => ({
      todas: conversations.filter((item) => !item.arquivada).length,
      nao_lidas: conversations.filter((item) => !item.arquivada && item.nao_lidas > 0).length,
      abertas: conversations.filter((item) => !item.arquivada && item.status === 'aberta').length,
      arquivadas: conversations.filter((item) => item.arquivada).length,
    }),
    [conversations],
  )
  const visiveis = useMemo(
    () =>
      filtro === 'arquivadas'
        ? conversations.filter((item) => item.arquivada)
        : filtro === 'nao_lidas'
          ? conversations.filter((item) => !item.arquivada && item.nao_lidas > 0)
          : filtro === 'abertas'
            ? conversations.filter((item) => !item.arquivada && item.status === 'aberta')
            : conversations.filter((item) => !item.arquivada),
    [conversations, filtro],
  )
  const mensagemVazia = search.trim()
    ? 'Nenhuma conversa encontrada para essa busca.'
    : filtro === 'nao_lidas'
      ? 'Nenhuma conversa com mensagens não lidas.'
      : filtro === 'abertas'
        ? 'Nenhuma conversa aberta no momento.'
        : filtro === 'arquivadas'
          ? 'Nenhuma conversa arquivada.'
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
          <div className="pane-title-row">
            <div className="eyebrow">CENTRAL</div>
            <div className="pane-title-line">
              <h2>{me.role === 'gestor' ? 'Conversas' : 'Meus atendimentos'}</h2>
              <span className="count-chip" title="Conversas neste filtro">{contagens[filtro]}</span>
            </div>
          </div>
          <button type="button" className="button button-soft novo-contato-botao" onClick={() => setNovoContato((valor) => !valor)} aria-label="Novo contato" title="Novo contato">+</button>
        </div>
        {novoContato && <form className="novo-contato-form" onSubmit={async (event) => {
          event.preventDefault()
          const id = await onCreateContact(contatoNome, contatoNumero, contatoOptin)
          if (id) { setNovoContato(false); setContatoNome(''); setContatoNumero(''); setContatoOptin(false); onSelect(id) }
        }}>
          <strong>Novo contato</strong>
          <input aria-label="Nome do contato" placeholder="Nome" required maxLength={120} value={contatoNome} onChange={(event) => setContatoNome(event.target.value)} />
          <input aria-label="Número do contato" placeholder="55 + DDD + número" required inputMode="tel" value={contatoNumero} onChange={(event) => setContatoNumero(event.target.value)} />
          <label><input type="checkbox" checked={contatoOptin} onChange={(event) => setContatoOptin(event.target.checked)} required /> Confirmo que o contato autorizou mensagens da empresa.</label>
          <small>{me.whatsapp_provider === 'meta' ? 'O primeiro envio usa um template aprovado pela Meta. Sem META_TEMPLATE_NOME, o contato será salvo sem envio.' : 'No simulador, o primeiro envio será registrado localmente.'}</small>
          <button className="button button-primary" disabled={busy}>Adicionar contato</button>
        </form>}
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
                    <AvatarContato nome={conversa.nome_contato} fotoUrl={conversa.foto_url} />
                    <span className="conversation-item-main">
                      <strong className="atendimento-numero">{formatPhone(conversa.numero)}</strong>
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
      <section className="chat-pane" aria-label="Conversa selecionada" style={papelParede ? {
        '--wpp-wallpaper': `linear-gradient(rgba(0,0,0,${opacidadePapelParede}),rgba(0,0,0,${opacidadePapelParede})), url("${papelParede}")`,
        '--wpp-wallpaper-size': 'cover',
      } : undefined}>
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
                <AvatarContato nome={selected.nome_contato} fotoUrl={selected.foto_url} grande />
                <div className="atendimento-titulo">
                  <h3>{formatPhone(selected.numero)}</h3>
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
                {stageName[selected.etapa] || selected.etapa}
              </span>
              {atual.mensagens.some((item) => item.origem === 'cliente') && (
                <span
                  className={`atendimento-chip ${atual.visualizada_pelo_atendente_em ? 'atendimento-chip-ok' : 'atendimento-chip-alerta'}`}
                >
                  {atual.visualizada_pelo_atendente_em
                    ? `Última mensagem vista pelo atendente em ${time(atual.visualizada_pelo_atendente_em)}`
                    : 'Cliente aguardando resposta'}
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
              contactName={selected.nome_contato}
              contactPhoto={selected.foto_url}
              onRetry={(messageId) => onRetry(selected.id, messageId)}
              onEdit={(messageId, texto) => onEdit(selected.id, messageId, texto)}
              onDiscard={(messageId) => onDiscard(selected.id, messageId)}
              onImagem={onImagem}
              busy={busy}
            />
            {selected.status === 'aberta' ? (
              <div className="chat-composer atendimento-composer">
                {janelaBloqueada && <div className="janela-meta-aviso" role="status">
                  <strong>Janela de resposta encerrada</strong>
                  <span>Atualizar o token não reabre as 24 horas. Peça ao cliente para enviar uma mensagem ou use um template aprovado pela Meta para retomar.</span>
                </div>}
                {gravando && <div role="status" className="gravacao-status"><span className="gravacao-ponto" />Gravando {String(Math.floor(segundosGravacao / 60)).padStart(2, '0')}:{String(segundosGravacao % 60).padStart(2, '0')}<button type="button" onClick={cancelarGravacao}>Cancelar</button><span>Toque no microfone verde para enviar.</span></div>}
                {selected.contato_optin && me.whatsapp_provider === 'meta' && (
                  <div className="template-contato-note">
                    <span>{me.meta_template_disponivel ? 'Contato com consentimento: use o template para iniciar ou retomar após 24 horas.' : 'Contato salvo. Configure um template aprovado da Meta para iniciar a conversa.'}</span>
                    {me.meta_template_disponivel && <button type="button" className="button button-soft" disabled={busy} onClick={() => onSendTemplate(selected.id)}>Enviar template</button>}
                  </div>
                )}
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
                  <input ref={audioWppRef} type="file" accept=".mp3,.ogg,audio/mpeg,audio/ogg" hidden onChange={async (event) => {
                    const arquivo = event.target.files?.[0]
                    event.target.value = ''
                    if (arquivo && selected) await onSendAudio(selected.id, arquivo)
                  }} />
                  <div className="anexo-menu-wrap">
                    <button type="button" className="int-icon-btn" onClick={() => setAnexosAbertos((valor) => !valor)} disabled={busy || janelaBloqueada || gravando} aria-label="Anexar arquivo" aria-expanded={anexosAbertos} title="Anexar arquivo"><Icon name="clip" size={20} /></button>
                    {anexosAbertos && <div className="anexo-menu" role="menu">
                      <button type="button" role="menuitem" onClick={() => { setAnexosAbertos(false); arquivoWppRef.current?.click() }}>Imagem</button>
                      <button type="button" role="menuitem" onClick={() => { setAnexosAbertos(false); audioWppRef.current?.click() }}>Áudio MP3/OGG</button>
                    </div>}
                  </div>
                  <textarea
                    ref={campoWppRef}
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.metaKey && draft.trim().toLowerCase() === '/transferir') {
                        event.preventDefault()
                        setDraft('')
                        destinoRef.current?.focus()
                        return
                      }
                      if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.metaKey && !event.nativeEvent.isComposing) {
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
                    disabled={janelaBloqueada || gravando}
                  />
                  {(draft.trim() || imagemWpp) && !gravando ? <button
                    className="button button-primary"
                    disabled={busy || janelaBloqueada || (!draft.trim() && !imagemWpp)}
                    title="Enviar resposta"
                  >
                    <Icon name="send" size={18} /><span>Enviar</span>
                  </button> : <button type="button" className={`atendimento-mic ${gravando ? 'gravando-audio' : ''}`} onClick={alternarGravacao} disabled={busy || janelaBloqueada} aria-label={gravando ? 'Parar e enviar gravação' : 'Gravar áudio'} title={gravando ? 'Parar e enviar gravação' : 'Gravar áudio'}><Icon name="mic" size={20} /></button>}
                </form>
                <small className="composer-hint" id="atendimento-dica">
                  Enter envia · Shift+Enter quebra linha · /transferir escolhe destino
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
                      className="button button-warning"
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
                    className="button button-danger atendimento-encerrar"
                    disabled={busy}
                    onClick={() => { if (window.confirm('Encerrar esta conversa?')) onClose(selected.id) }}
                  >
                    Encerrar conversa
                  </button>
                  <button type="button" className="button button-neutral" disabled={busy} onClick={() => onArchive(selected.id, !selected.arquivada)}>
                    {selected.arquivada ? 'Desarquivar' : 'Arquivar'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="closed-note" role="status">
                Esta conversa foi encerrada.
                <button type="button" className="text-button" disabled={busy} onClick={() => onArchive(selected.id, !selected.arquivada)}>
                  {selected.arquivada ? 'Desarquivar' : 'Arquivar'}
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  )
}

function UserEditor({ user, setoresInternos, onSave, onDelete, currentUserId, busy }) {
  const [value, setValue] = useState({ ...user, senha: '' })
  const [aberto, setAberto] = useState(false)
  return (
    <Fragment>
      <tr>
        <td><div className="manager-contact"><AvatarContato nome={value.nome} fotoUrl={value.foto_url} /><div><strong>{value.nome}</strong><small>Usuário #{user.id}</small></div></div></td>
        <td>{value.email}</td>
        <td>{roleName[value.role]}</td>
        <td>{setoresInternos.find(item => item.id === Number(value.setor_interno_id))?.nome || '—'}</td>
        <td><span className={`manager-state ${value.ativo ? 'is-active' : ''}`}>{value.ativo ? 'Ativo' : 'Inativo'}</span></td>
        <td><div className="manager-row-actions"><button type="button" className="button button-edit" aria-expanded={aberto} onClick={() => setAberto(!aberto)}>{aberto ? 'Fechar' : 'Editar'}</button><button type="button" className="button button-danger" disabled={busy || user.id === currentUserId} title={user.id === currentUserId ? 'Não é possível excluir sua própria conta' : 'Exclui apenas contas sem histórico; caso contrário, desative'} onClick={() => { if (window.confirm(`Excluir ${user.nome}? Contas com histórico devem ser desativadas para preservar a auditoria.`)) onDelete(user.id) }}>Excluir</button></div></td>
      </tr>
      {aberto && <tr className="manager-detail-row"><td colSpan="6"><form className="manager-edit-grid" onSubmit={async evento => {
        evento.preventDefault()
        if (await onSave(user.id, value)) { setValue({ ...value, senha: '' }); setAberto(false) }
      }}>
        <label>Nome<input value={value.nome} onChange={evento => setValue({ ...value, nome: evento.target.value })} required /></label>
        <label>Email de acesso<input type="email" value={value.email} onChange={evento => setValue({ ...value, email: evento.target.value })} required /></label>
        <label>Permissão<select value={value.role} onChange={evento => setValue({ ...value, role: evento.target.value })}><option value="colaborador">Colaborador</option><option value="supervisor">Supervisor</option><option value="gestor">Gestor</option></select></label>
        <label>Setor/equipe<select value={value.setor_interno_id || ''} onChange={evento => setValue({ ...value, setor_interno_id: evento.target.value })}><option value="">Sem setor</option>{setoresInternos.map(item => <option key={item.id} value={item.id}>{item.nome}</option>)}</select></label>
        <label>Redefinir senha<input type="password" placeholder="Deixe em branco para manter" minLength="8" value={value.senha} onChange={evento => setValue({ ...value, senha: evento.target.value })} /></label>
        <label className="switch-line"><input type="checkbox" checked={value.ativo} onChange={evento => setValue({ ...value, ativo: evento.target.checked })} />Ativo</label>
        <label className="switch-line"><input type="checkbox" checked={value.online} onChange={evento => setValue({ ...value, online: evento.target.checked })} />Disponível</label>
        <button className="button button-success" disabled={busy}>Salvar alterações</button>
      </form></td></tr>}
    </Fragment>
  )
}

function SectorEditor({ sector, users, onSave, busy }) {
  const [nome, setNome] = useState(sector.nome)
  const [responsavel, setResponsavel] = useState(sector.responsavel_id || '')
  const [icone, setIcone] = useState(sector.icone || 'equipe')
  const [ordem, setOrdem] = useState(sector.ordem)
  const [aberto, setAberto] = useState(false)
  useEffect(() => setOrdem(sector.ordem), [sector.ordem])
  return (
    <Fragment>
      <tr>
        <td><div className="manager-contact"><span className="manager-sector-icon"><Icone nome={icone} tamanho={20} /></span><div><strong>{nome}</strong><small>Opção {sector.ordem} do menu</small></div></div></td>
        <td><Icone nome={icone} tamanho={20} /></td>
        <td>{sector.ordem === 1 ? 'Distribuição entre vendedores' : users.find(item => item.id === Number(responsavel))?.nome || 'Sem responsável'}</td>
        <td><button type="button" className="button button-edit" aria-expanded={aberto} onClick={() => setAberto(!aberto)}>{aberto ? 'Fechar' : 'Editar'}</button></td>
      </tr>
      {aberto && <tr className="manager-detail-row"><td colSpan="4"><form className="manager-edit-grid" onSubmit={async evento => {
        evento.preventDefault()
        if (await onSave(sector.id, { nome, icone, ordem, responsavel_id: responsavel })) setAberto(false)
      }}>
        <label>Nome<input aria-label={`Nome do setor ${sector.ordem}`} value={nome} onChange={evento => setNome(evento.target.value)} required /></label>
        <label>Opção no menu<select aria-label={`Opção no menu para ${sector.nome}`} value={ordem} onChange={evento => setOrdem(Number(evento.target.value))}>{sector.ordem === 1 ? <option value={1}>1 · {sector.nome}</option> : [2, 3, 4].map(numero => <option key={numero} value={numero}>{numero} · {sector.nome}</option>)}</select></label>
        <SeletorIcone valor={icone} onChange={setIcone} />
        {sector.ordem !== 1 && <label>Responsável<select aria-label={`Responsável pelo setor ${sector.ordem}`} value={responsavel} onChange={evento => setResponsavel(evento.target.value)}><option value="">Selecionar supervisor</option>{users.filter(item => item.role === 'supervisor' && item.ativo).map(item => <option key={item.id} value={item.id}>{item.nome}</option>)}</select></label>}
        <button className="button button-primary" disabled={busy}>Salvar</button>
      </form></td></tr>}
    </Fragment>
  )
}

function InternalSectorEditor({ sector, membros, vinculados, onSave, onDelete, busy }) {
  const [nome, setNome] = useState(sector.nome)
  const [icone, setIcone] = useState(sector.icone || 'equipe')
  const [aberto, setAberto] = useState(false)
  return (
    <Fragment>
      <tr>
        <td><div className="manager-contact"><span className="manager-sector-icon"><Icone nome={icone} tamanho={20} /></span><div><strong>{nome}</strong><small>Equipe interna</small></div></div></td>
        <td><span className="manager-sector-icon" title={SETOR_ICONES.find(item => item[0] === icone)?.[1]}><Icone nome={icone} tamanho={20} /></span></td>
        <td>{membros} {membros === 1 ? 'membro ativo' : 'membros ativos'}</td>
        <td><span className={`manager-state ${membros >= 2 ? 'is-active' : ''}`}>{membros >= 2 ? 'Grupo ativo' : 'Grupo inativo'}</span></td>
        <td><div className="manager-row-actions"><button type="button" className="button button-edit" aria-expanded={aberto} onClick={() => setAberto(!aberto)}>{aberto ? 'Fechar' : 'Editar'}</button><button type="button" className="button button-danger" disabled={busy || sector.id === 1 || vinculados > 0} title={sector.id === 1 ? 'Vendas é necessário para a distribuição' : vinculados > 0 ? 'Transfira os usuários antes de excluir' : 'Excluir setor sem histórico'} onClick={() => { if (window.confirm(`Excluir o setor ${sector.nome}? Esta ação não pode ser desfeita.`)) onDelete(sector.id) }}>Excluir</button></div></td>
      </tr>
      {aberto && <tr className="manager-detail-row"><td colSpan="5"><form className="manager-edit-grid" onSubmit={async evento => {
        evento.preventDefault()
        if (await onSave(sector.id, { nome, icone })) setAberto(false)
      }}>
        <label>Nome<input aria-label={`Nome da equipe ${sector.nome}`} value={nome} onChange={evento => setNome(evento.target.value)} maxLength="80" required /></label>
        <SeletorIcone valor={icone} onChange={setIcone} />
        <button className="button button-primary" disabled={busy}>Salvar</button>
      </form></td></tr>}
    </Fragment>
  )
}

const DIAS_SEMANA = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']

function ConfiguracaoAutomacao({ agenda, onSave, busy }) {
  const [rascunho, setRascunho] = useState(agenda)
  const [editando, setEditando] = useState(false)
  const [novaData, setNovaData] = useState('')
  const [mostrarFeriados, setMostrarFeriados] = useState(false)
  const [anoFeriados, setAnoFeriados] = useState(new Date().getFullYear())
  const feriados = feriadosNacionais(anoFeriados)
  useEffect(() => { if (!editando && agenda) setRascunho(agenda) }, [agenda, editando])
  if (!rascunho) return <p>Carregando configuração...</p>
  const mudarDia = (indice, campo, valor) => {
    setEditando(true)
    setRascunho(atual => ({ ...atual, horarios: { ...atual.horarios, [indice]: { ...atual.horarios[indice], [campo]: valor } } }))
  }
  const mudarTexto = (campo, valor) => {
    setEditando(true)
    setRascunho(atual => ({ ...atual, [campo]: valor }))
  }
  return <section className="surface manager-section bot-settings">
    <div className="section-heading"><div><h2>Automação do atendimento</h2><p>Horários no fuso de São Paulo. Fora deles, o bot responde uma vez e retoma no próximo expediente.</p></div></div>
    <form onSubmit={async evento => {
      evento.preventDefault()
      if (await onSave({
        horarios: JSON.stringify(rascunho.horarios),
        dias_fechados: JSON.stringify(rascunho.dias_fechados),
        mensagem_fora_expediente: rascunho.mensagem_fora_expediente,
        mensagem_reabertura: rascunho.mensagem_reabertura,
        mensagem_standby: rascunho.mensagem_standby,
      })) setEditando(false)
    }}>
      <h3>Horários por dia</h3>
      <div className="bot-schedule">
        {DIAS_SEMANA.map((nome, indice) => {
          const periodo = rascunho.horarios[String(indice)]
          return <div className="bot-schedule-row" key={nome}>
            <strong>{nome}</strong>
            <label><input type="checkbox" checked={periodo.ativo} onChange={evento => mudarDia(indice, 'ativo', evento.target.checked)} /> Aberto</label>
            <label>Das <input type="time" value={periodo.inicio} onChange={evento => mudarDia(indice, 'inicio', evento.target.value)} disabled={!periodo.ativo} required /></label>
            <label>Até <input type="time" value={periodo.fim} onChange={evento => mudarDia(indice, 'fim', evento.target.value)} disabled={!periodo.ativo} required /></label>
          </div>
        })}
      </div>
      <h3>Dias fechados</h3>
      <p className="muted">Feriados ou pausas específicas. O dia inteiro fica fechado, mesmo que esteja aberto na semana.</p>
      <div className="bot-date-add"><input type="date" aria-label="Data fechada" value={novaData} onChange={evento => setNovaData(evento.target.value)} /><button type="button" className="button button-soft" disabled={!novaData} onClick={() => { setEditando(true); setRascunho(atual => ({ ...atual, dias_fechados: [...new Set([...atual.dias_fechados, novaData])].sort() })); setNovaData('') }}>Adicionar dia</button></div>
      <div className="bot-closed-dates">{rascunho.dias_fechados.map(data => <span key={data}>{data.split('-').reverse().join('/')} <button type="button" aria-label={`Remover ${data}`} onClick={() => { setEditando(true); setRascunho(atual => ({ ...atual, dias_fechados: atual.dias_fechados.filter(dia => dia !== data) })) }}>×</button></span>)}</div>
      <div className="bot-holidays-heading"><button type="button" className="button button-soft" aria-expanded={mostrarFeriados} onClick={() => setMostrarFeriados(!mostrarFeriados)}>{mostrarFeriados ? 'Ocultar calendário' : 'Ver feriados nacionais'}</button>{mostrarFeriados && <label>Ano <input type="number" min="2020" max="2100" value={anoFeriados} onChange={evento => setAnoFeriados(Number(evento.target.value))} /></label>}</div>
      {mostrarFeriados && <div className="bot-holidays"><p className="muted">Feriados nacionais do Brasil. Clique em uma data para marcar ou desmarcar o fechamento; depois salve a automação. Pontos facultativos e feriados locais não entram automaticamente.</p><div className="bot-holiday-grid">{feriados.map(({ data, nome }) => <button key={data} type="button" className={rascunho.dias_fechados.includes(data) ? 'is-closed' : ''} aria-pressed={rascunho.dias_fechados.includes(data)} onClick={() => { setEditando(true); setRascunho(atual => ({ ...atual, dias_fechados: atual.dias_fechados.includes(data) ? atual.dias_fechados.filter(dia => dia !== data) : [...atual.dias_fechados, data].sort() })) }}><strong>{data.split('-').reverse().slice(0, 2).join('/')}</strong><span>{nome}</span><small>{rascunho.dias_fechados.includes(data) ? 'Fechado' : 'Aberto'}</small></button>)}</div></div>}
      <h3>Mensagens automáticas</h3>
      <label>Fora do expediente<textarea value={rascunho.mensagem_fora_expediente} onChange={evento => mudarTexto('mensagem_fora_expediente', evento.target.value)} maxLength="600" required /></label>
      <label>Retorno ao expediente<textarea value={rascunho.mensagem_reabertura} onChange={evento => mudarTexto('mensagem_reabertura', evento.target.value)} maxLength="600" required /></label>
      <label>Sem atendente disponível<textarea value={rascunho.mensagem_standby} onChange={evento => mudarTexto('mensagem_standby', evento.target.value)} maxLength="600" required /></label>
      <button className="button button-primary" disabled={busy || !editando}>Salvar automação</button>
    </form>
  </section>
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
  onDeleteUser,
  currentUserId,
  onSaveSector,
  onCreateInternalSector,
  onSaveInternalSector,
  onDeleteInternalSector,
  onToggleSimulator,
  onSaveBot,
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
  const [newInternalIcone, setNewInternalIcone] = useState('equipe')
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
        <div className="stat-card">
          <span>Equipe de Vendas online</span>
          <strong>{online}</strong>
          <small>Disponíveis para distribuição</small>
        </div>
        <div className="stat-card">
          <span>WhatsApp</span>
          <strong className={`status-badge ${whatsappStatus?.status === 'conectado' || whatsappStatus?.status === 'simulado' ? 'status-badge-ok' : 'status-badge-error'}`}>{whatsappStatus?.status || 'Verificando'}</strong>
          <small>{whatsappStatus?.ultimo_evento_em ? `Última mensagem: ${time(whatsappStatus.ultimo_evento_em)}` : 'Nenhuma mensagem registrada'}</small>
        </div>
      </div>
      <div className="section-tabs">
        <button className={tab === 'conversas' ? 'active' : ''} onClick={() => setTab('conversas')}>Conversas</button>
        <button className={tab === 'equipe' ? 'active' : ''} onClick={() => setTab('equipe')}>Equipe</button>
        <button className={tab === 'setores' ? 'active' : ''} onClick={() => setTab('setores')}>Setores</button>
        <button className={tab === 'automacao' ? 'active' : ''} onClick={() => setTab('automacao')}>Automação</button>
      </div>
      {tab === 'automacao' && config?.simulador_disponivel && <div className="simulator-setting surface">
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
      </div>}
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
                        <div className="manager-contact">
                          <AvatarContato nome={conversa.nome_contato} fotoUrl={conversa.foto_url} />
                          <div>
                            <button className="table-link" onClick={() => onOpen(conversa.id)}>
                              {formatPhone(conversa.numero)}
                            </button>
                            <small>{conversa.nome_contato || 'Contato sem nome salvo'}</small>
                            <small>{time(conversa.criada_em)}</small>
                          </div>
                        </div>
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
                            className="button button-warning"
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
          <div className="table-wrap manager-list-table">
            <table><thead><tr><th>Usuário</th><th>Email</th><th>Permissão</th><th>Setor</th><th>Status</th><th>Ações</th></tr></thead><tbody>
              {users.map(item => <UserEditor key={item.id} user={item} setoresInternos={config?.setores_internos || []} onSave={onSaveUser} onDelete={onDeleteUser} currentUserId={currentUserId} busy={busy} />)}
            </tbody></table>
          </div>
        </section>
      )}
      {tab === 'setores' && (
          <section className="surface manager-section manager-sectors">
            <div className="section-heading">
              <div>
                <h2>Setores do WhatsApp</h2>
                <p>Os nomes aparecem no menu enviado ao cliente.</p>
              </div>
            </div>
            <div className="table-wrap manager-list-table">
              <table><thead><tr><th>Setor</th><th>Ícone</th><th>Distribuição</th><th>Ações</th></tr></thead><tbody>
                {sectors.map(item => <SectorEditor key={item.id} sector={item} users={users} onSave={onSaveSector} busy={busy} />)}
              </tbody></table>
            </div>
            <div className="section-heading manager-subheading">
              <div>
                <h2>Equipes internas</h2>
                <p>
                  Cadastre qualquer setor. Ao vincular dois membros ativos, o grupo aparece
                  automaticamente no chat interno.
                </p>
              </div>
            </div>
            <form
              className="create-internal-sector"
              onSubmit={async (event) => {
                event.preventDefault()
                if (await onCreateInternalSector({ nome: newInternalSector, icone: newInternalIcone })) {
                  setNewInternalSector('')
                  setNewInternalIcone('equipe')
                }
              }}
            >
              <label>Nome do setor<input
                aria-label="Nova equipe interna"
                placeholder="Nome do novo setor"
                value={newInternalSector}
                onChange={(event) => setNewInternalSector(event.target.value)}
                maxLength="80"
                required
              /></label>
              <SeletorIcone valor={newInternalIcone} onChange={setNewInternalIcone} />
              <button className="button button-primary" disabled={busy}>
                Adicionar setor
              </button>
            </form>
            <div className="table-wrap manager-list-table">
              <table><thead><tr><th>Equipe</th><th>Ícone</th><th>Pessoas</th><th>Grupo</th><th>Ações</th></tr></thead><tbody>
                {(config?.setores_internos || []).map(item => <InternalSectorEditor key={item.id} sector={item} membros={users.filter(pessoa => pessoa.ativo && pessoa.setor_interno_id === item.id).length} vinculados={users.filter(pessoa => pessoa.setor_interno_id === item.id).length} onSave={onSaveInternalSector} onDelete={onDeleteInternalSector} busy={busy} />)}
              </tbody></table>
            </div>
          </section>
      )}
      {tab === 'automacao' && <ConfiguracaoAutomacao agenda={config?.configuracao_bot} onSave={onSaveBot} busy={busy} />}
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
              <p>{formatPhone(chosen?.numero)}</p>
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
                    <small>{formatPhone(item.numero)}</small>
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
  const [modoApresentacao, setModoApresentacao] = useState(() => sessionStorage.getItem('fortgiro-apresentacao') === '1' || new URLSearchParams(location.search).get('apresentacao') === '1')
  const [imagemModal, setImagemModal] = useState(null)
  const [papelParede, setPapelParede] = useState(lerPapelParede)
  const [opacidadePapelParede, setOpacidadePapelParede] = useState(() => {
    const valor = Number(localStorage.getItem(PAPEL_PAREDE_OPACIDADE))
    return valor >= 0.35 && valor <= 0.8 ? valor : 0.55
  })
  const [tomPapelParede, setTomPapelParede] = useState(() => localStorage.getItem(PAPEL_PAREDE_TOM) === 'claro' ? 'claro' : 'escuro')
  const [page, setPage] = useState('inbox')
  const [conversations, setConversations] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [config, setConfig] = useState(null)
  const [whatsappStatus, setWhatsappStatus] = useState(null)
  const [emExpediente, setEmExpediente] = useState(null)
  const [simData, setSimData] = useState(null)
  const [chamados, setChamados] = useState([])
  const [chamadosAguardando, setChamadosAguardando] = useState(0)
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
  const meVisivel = modoApresentacao ? usuarioDemonstracao(me) : me
  const conversasVisiveis = modoApresentacao ? conversations.map(conversaDemonstracao) : conversations
  const detalheVisivel = modoApresentacao && detail ? {
    ...detail,
    conversa: conversaDemonstracao(detail.conversa),
    mensagens: detail.mensagens?.map(mensagem => ({ ...mensagem, texto: 'Mensagem de demonstração', imagem_url: null, audio_url: null })),
  } : detail
  const configuracaoVisivel = modoApresentacao && config ? { ...config, usuarios: config.usuarios?.map(usuarioDemonstracao) } : config
  const computadoresVisiveis = modoApresentacao ? computadores.map(pc => ({ ...pc, nome: nomeDemonstracao('Computador', pc.id), dono_nome: nomeDemonstracao('Colaborador', pc.dono_id) })) : computadores
  const chamadosVisiveis = modoApresentacao ? chamados.map(chamado => ({ ...chamado, computador_nome: nomeDemonstracao('Computador', chamado.computador_id), dono_nome: nomeDemonstracao('Colaborador', chamado.dono_id), descricao: 'O sistema não abre no computador.', solucao: chamado.solucao ? 'Sistema reiniciado e acesso confirmado.' : null, acessos: chamado.acessos?.map(acesso => ({ ...acesso, solicitante: 'Técnico', acesso_url: null })) || [] })) : chamados
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
        await fetchApi('/api/presenca', { method: 'POST', credentials: 'same-origin' })
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
      fetchApi(`/api/atendimentos/${selectedId}/leitura`, {
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
    if (!me) return
    const atualizar = () => getJSON('/api/operacao-status').then(dados => setEmExpediente(dados.em_expediente)).catch(() => setEmExpediente(null))
    atualizar()
    const intervalo = setInterval(atualizar, 60000)
    return () => clearInterval(intervalo)
  }, [me?.id])
  useEffect(() => {
    if (page !== 'manager') return
    refreshConfig()
    const configInterval = setInterval(refreshConfig, 10000)
    const refreshStatus = () =>
      getJSON('/api/gestor/whatsapp-status')
        .then(setWhatsappStatus)
        .catch(() => setWhatsappStatus({ status: 'desconectado' }))
    refreshStatus()
    const interval = setInterval(refreshStatus, 10000)
    return () => { clearInterval(interval); clearInterval(configInterval) }
  }, [page, refreshConfig])
  useEffect(() => {
    if (!me || me.role === 'colaborador') return
    let ativo = true
    const atualizar = async () => {
      try {
        const dados = await getJSON('/api/chamados/pendentes')
        if (ativo) setChamadosAguardando(dados.aguardando_resposta)
      } catch { /* Mantém a última contagem até a próxima consulta. */ }
    }
    atualizar()
    const intervalo = setInterval(atualizar, 3000)
    return () => { ativo = false; clearInterval(intervalo) }
  }, [me?.id, me?.role])

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
    if (modoApresentacao) { setError('Desative o modo apresentação para alterar dados.'); return false }
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
    if (modoApresentacao) { setError('Desative o modo apresentação para enviar mensagens.'); return false }
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const response = await fetchApi(path, {
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
              {me.role !== 'colaborador' && chamadosAguardando > 0 && (
                <span className="nav-count" aria-label={`${chamadosAguardando} chamados aguardando resposta`} title="Chamados aguardando resposta">{chamadosAguardando}</span>
              )}
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
          <div className={`sidebar-help ${emExpediente === false ? 'sidebar-help-fechado' : ''}`}>
            <span className="help-dot" />
            <span><strong>Central FortGiro</strong><small>{emExpediente === null ? 'Verificando expediente' : emExpediente ? 'Dentro do expediente' : 'Fora do expediente'}</small></span>
          </div>
          <div className="sidebar-user">
            <button
              type="button"
              className="user-avatar user-avatar-btn"
              onClick={() => meVisivel.foto_url && setImagemModal({ url: meVisivel.foto_url, titulo: meVisivel.nome })}
              disabled={!meVisivel.foto_url}
              title={meVisivel.foto_url ? 'Visualizar foto do perfil' : undefined}
              aria-label={meVisivel.foto_url ? 'Visualizar foto do perfil' : 'Foto do perfil'}
            >
              {meVisivel.foto_url ? <img className="int-avatar-photo" src={meVisivel.foto_url} alt="" /> : initials(meVisivel.nome)}
            </button>
            <span>
              <strong>{meVisivel.nome}</strong>
              <small>{roleName[meVisivel.role] || meVisivel.role}</small>
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
            <button type="button" className="demo-mode-toggle" onClick={() => { const novo = !modoApresentacao; sessionStorage.setItem('fortgiro-apresentacao', novo ? '1' : '0'); if (location.search) history.replaceState({}, '', location.pathname); setModoApresentacao(novo) }} aria-pressed={modoApresentacao}>Modo apresentação · {modoApresentacao ? 'Ligado' : 'Desligado'}</button>
            <span className="topbar-date">
              {messageDay(new Date().toISOString())}
            </span>
            <button
              type="button"
              className="topbar-avatar topbar-avatar-btn"
              onClick={() => meVisivel.foto_url && setImagemModal({ url: meVisivel.foto_url, titulo: meVisivel.nome })}
              disabled={!meVisivel.foto_url}
              title={meVisivel.foto_url ? 'Visualizar foto do perfil' : undefined}
              aria-label={meVisivel.foto_url ? 'Visualizar foto do perfil' : 'Foto do perfil'}
            >
              {meVisivel.foto_url ? <img className="int-avatar-photo" src={meVisivel.foto_url} alt="" /> : initials(meVisivel.nome)}
            </button>
            <button type="button" className="topbar-mobile-logout" onClick={logout} title="Sair" aria-label="Sair da conta">
              <Icon name="logout" />
              <span>Sair</span>
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
              {modoApresentacao ? 'Contato fictício' : avisoEvento.tipo === 'interno' ? avisoEvento.item.nome : formatPhone(avisoEvento.item.numero)}:{' '}
              {modoApresentacao ? 'Mensagem de demonstração' : avisoEvento.item.texto}
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
            me={meVisivel}
            papelParede={papelParede}
            opacidadePapelParede={opacidadePapelParede}
            conversations={conversasVisiveis}
            selectedId={selectedId}
            onSelect={(id) => {
              setSelectedId(id)
              setDetail(null)
              marcarLidas('whatsapp', id)
            }}
            detail={detalheVisivel}
            search={search}
            setSearch={setSearch}
            busy={busy || modoApresentacao}
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
            onSendAudio={(id, arquivo) => actionRaw(`/api/atendimentos/${id}/mensagens`, {
              method: 'POST', headers: { 'Content-Type': arquivo.type || (arquivo.name.toLowerCase().endsWith('.ogg') ? 'audio/ogg' : 'audio/mpeg') }, body: arquivo,
            }, 'Áudio enviado.')}
            onSendTemplate={(id) => action(`/api/atendimentos/${id}/template`, {}, 'Template enviado ao contato.')}
            onCreateContact={async (nome, numero, optin) => {
              setBusy(true); setError('')
              try {
                const body = new URLSearchParams({ nome, numero, optin: optin ? 'sim' : 'nao' })
                const resposta = await fetchApi('/api/atendimentos/novo-contato', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' }, body })
                const dados = await resposta.json()
                if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível iniciar o contato.')
                await refreshConversations()
                setNotice(dados.template_enviado ? 'Contato criado e template enviado.' : 'Contato salvo. Para iniciar no WhatsApp, configure um template aprovado pela Meta.')
                return dados.id
              } catch (falha) { setError(falha.message); return null }
              finally { setBusy(false) }
            }}
            onImagem={(url, titulo) => setImagemModal({ url, titulo: titulo || 'Imagem da mensagem' })}
            onRetry={(id, messageId) =>
              action(
                `/api/atendimentos/${id}/mensagens/${messageId}/reenviar`,
                {},
                'Mensagem reenviada.',
              )
            }
            onEdit={(id, messageId, texto) => actionRaw(
              `/api/atendimentos/${id}/mensagens/${messageId}`,
              { method: 'PATCH', headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' }, body: new URLSearchParams({ texto }) },
              'Mensagem com falha alterada para o próximo reenvio.',
            )}
            onDiscard={(id, messageId) => actionRaw(
              `/api/atendimentos/${id}/mensagens/${messageId}`,
              { method: 'DELETE' },
              'Registro local da mensagem com falha descartado.',
            )}
            onTransfer={(id, destino) =>
              action(
                `/api/atendimentos/${id}/transferir`,
                { destino },
                'Conversa transferida.',
                true,
              )
            }
            onUploadPhoto={async (id, arquivo) => {
              if (modoApresentacao) { setError('Desative o modo apresentação para alterar dados.'); return false }
              setBusy(true)
              setError('')
              try {
                const webp = await converterWebp(arquivo, 512)
                const resposta = await fetchApi(`/api/atendimentos/${id}/foto`, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'image/webp' }, body: webp })
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
            onArchive={(id, arquivar) => action(`/api/atendimentos/${id}/${arquivar ? 'arquivar' : 'desarquivar'}`, {}, arquivar ? 'Conversa arquivada.' : 'Conversa desarquivada.').then((ok) => {
              if (ok) { setSelectedId(null); setDetail(null) }
            })}
          />
        )}
        {page === 'manager' && (
          <Manager
            conversations={conversasVisiveis}
            config={configuracaoVisivel}
            whatsappStatus={whatsappStatus}
            vendorFilter={vendorFilter}
            setVendorFilter={setVendorFilter}
            busy={busy || modoApresentacao}
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
            onDeleteUser={(id) => actionRaw(`/api/gestor/usuarios/${id}`, { method: 'DELETE' }, 'Usuário excluído.')}
            currentUserId={me.id}
            onSaveSector={(id, values) =>
              action(`/api/gestor/setores/${id}`, values, 'Setor atualizado.')
            }
            onCreateInternalSector={(values) =>
              action('/api/gestor/setores-internos', values, 'Setor interno criado.')
            }
            onSaveInternalSector={(id, values) =>
              action(`/api/gestor/setores-internos/${id}`, values, 'Setor interno atualizado.')
            }
            onDeleteInternalSector={(id) => actionRaw(`/api/gestor/setores-internos/${id}`, { method: 'DELETE' }, 'Setor interno excluído.')}
            onToggleSimulator={(ativo) =>
              action(
                '/api/gestor/simulador',
                { ativo: ativo ? 'on' : 'off' },
                ativo ? 'Simulador ativado.' : 'Simulador desativado.',
              )
            }
            onSaveBot={(values) => action('/api/gestor/configuracao-bot', values, 'Automação atualizada.')}
          />
        )}
        {page === 'tickets' &&
          (me.role === 'colaborador' ? (
            <ChamadosVendedor
              modoApresentacao={modoApresentacao}
              chamados={chamadosVisiveis}
              computadores={computadoresVisiveis}
              busy={busy || modoApresentacao}
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
              modoApresentacao={modoApresentacao}
              me={meVisivel}
              chamados={chamadosVisiveis}
              computadores={computadoresVisiveis}
              usuarios={configuracaoVisivel?.usuarios || []}
              busy={busy || modoApresentacao}
              onRequest={(id) =>
                action(`/api/chamados/${id}/acessos`, {}, 'Solicitação de acesso registrada.')
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
            me={meVisivel}
            modoApresentacao={modoApresentacao}
            papelParede={papelParede}
            opacidadePapelParede={opacidadePapelParede}
            tomPapelParede={tomPapelParede}
            abrirColegaId={colegaAlvoId}
            onOpen={(id) => marcarLidas('interno', id)}
            onUnreadChange={setInternoNaoLidasTotal}
            onVisualizarImagem={(url, titulo) => setImagemModal({ url, titulo })}
          />
        )}
        {page === 'perfil' && (
          <Perfil
            me={meVisivel}
            somenteLeitura={modoApresentacao}
            papelParede={papelParede}
            opacidadePapelParede={opacidadePapelParede}
            tomPapelParede={tomPapelParede}
            onPapelParede={(valor) => { if (!salvarPapelParede(valor)) return false; setPapelParede(valor); return true }}
            onOpacidadePapelParede={(valor) => { localStorage.setItem(PAPEL_PAREDE_OPACIDADE, String(valor)); setOpacidadePapelParede(valor) }}
            onTomPapelParede={(valor) => { localStorage.setItem(PAPEL_PAREDE_TOM, valor); setTomPapelParede(valor) }}
            onVisualizarFoto={(url, titulo) => setImagemModal({ url, titulo })}
            onEnviarFoto={async (arquivo) => {
              const corpo = await converterWebp(arquivo, 512)
              const resposta = await fetchApi('/api/me/foto', {
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
