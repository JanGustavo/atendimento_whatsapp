import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { messageDay, messageHour } from './dates.js'
import { converterWebp } from './images.js'
import ModalImagem from './ModalImagem.jsx'
import { requisitar as fetchApi } from './api.js'
import { copiarTexto } from './clipboard.js'

const BASE = '/api/interno'
const PAGINA = 50
const INTERVALO_MS = 3000
const JANELA_AGRUPAR_MS = 5 * 60 * 1000
const LIMITE_ORIGEM = 12 * 1024 * 1024
export const PAPEL_PAREDE_STORAGE = 'fortgiro.papel-parede'
export const PAPEL_PAREDE_OPACIDADE = 'fortgiro.papel-parede.opacidade'
export const PAPEL_PAREDE_TOM = 'fortgiro.papel-parede.tom'
const PAPEL_PAREDE_TAMANHO_MAX_MB = 12

/* ───────────── API ───────────── */

async function leitura(url, signal) {
  const resposta = await fetchApi(url, { credentials: 'same-origin', signal })
  if (!resposta.ok) throw new Error('Não foi possível carregar o chat interno.')
  return resposta.json()
}

async function postar(url, init, mensagemPadrao) {
  const resposta = await fetchApi(url, { method: 'POST', credentials: 'same-origin', ...init })
  if (resposta.ok) return
  const corpo = await resposta.json().catch(() => ({}))
  throw new Error(typeof corpo.detail === 'string' ? corpo.detail : mensagemPadrao)
}

async function apagar(url) {
  const resposta = await fetchApi(url, { method: 'DELETE', credentials: 'same-origin' })
  if (resposta.ok) return
  const corpo = await resposta.json().catch(() => ({}))
  throw new Error(typeof corpo.detail === 'string' ? corpo.detail : 'Não foi possível apagar a mensagem.')
}

async function editar(url, texto) {
  const resposta = await fetchApi(url, {
    method: 'PATCH', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
    body: new URLSearchParams({ texto }),
  })
  if (resposta.ok) return
  const corpo = await resposta.json().catch(() => ({}))
  throw new Error(typeof corpo.detail === 'string' ? corpo.detail : 'Não foi possível editar a mensagem.')
}

function rotasDe(grupo, colega) {
  if (grupo) return { mensagens: `grupos/${grupo.id}/mensagens`, imagens: `grupos/${grupo.id}/imagens`, audios: `grupos/${grupo.id}/audios`, apagar: id => `grupos/${grupo.id}/mensagens/${id}` }
  if (colega) return { mensagens: `mensagens/${colega.id}`, imagens: `mensagens/${colega.id}/imagem`, audios: `mensagens/${colega.id}/audio`, apagar: id => `mensagens/${colega.id}/${id}` }
  return null
}

/* ───────────── utilidades ───────────── */

const iniciais = nome => {
  const partes = (nome || '?').split(/\s+/).filter(Boolean)
  const numero = partes.at(-1)?.match(/^0*(\d+)$/)
  return numero ? `${partes[0]?.[0]?.toUpperCase() || 'C'}${numero[1]}` : partes.slice(0, 2).map(parte => parte[0].toUpperCase()).join('')
}
const nomeApresentacao = pessoa => `${({ gestor: 'Gestor', supervisor: 'Supervisor' })[pessoa.role] || 'Colaborador'} ${pessoa.id}`
const plural = (n, singular, pluralForma) => `${n} ${n === 1 ? singular : pluralForma}`
const proximos = (a, b) => { const dif = new Date(b) - new Date(a); return dif >= 0 && dif < JANELA_AGRUPAR_MS }

function mesclar(atuais, novas) {
  const porId = new Map(atuais.map(item => [item.id, item]))
  for (const item of novas) porId.set(item.id, item)
  return [...porId.values()].sort((a, b) => a.id - b.id)
}

export function lerPapelParede(chave = PAPEL_PAREDE_STORAGE) {
  try {
    const valor = window.localStorage.getItem(chave) || ''
    return /^data:image\/(png|jpeg|webp);base64,/i.test(valor) ? valor : ''
  } catch {
    return ''
  }
}

export function salvarPapelParede(valor, chave = PAPEL_PAREDE_STORAGE) {
  try {
    if (valor) window.localStorage.setItem(chave, valor)
    else window.localStorage.removeItem(chave)
    return true
  } catch {
    return false
  }
}

function desenharRecorte(canvas, imagem, zoom, horizontal, vertical) {
  const proporcao = canvas.width / canvas.height
  const larguraBase = Math.min(imagem.naturalWidth, imagem.naturalHeight * proporcao)
  const largura = larguraBase / zoom
  const altura = largura / proporcao
  const esquerda = (imagem.naturalWidth - largura) * (horizontal + 1) / 2
  const topo = (imagem.naturalHeight - altura) * (vertical + 1) / 2
  const contexto = canvas.getContext('2d')
  contexto.clearRect(0, 0, canvas.width, canvas.height)
  contexto.drawImage(imagem, esquerda, topo, largura, altura, 0, 0, canvas.width, canvas.height)
}

export function PapelParede({ valor, opacidade, tom, onChange, onOpacidade, onTom }) {
  const arquivo = useRef(null)
  const previa = useRef(null)
  const imagemRef = useRef(null)
  const [fonte, setFonte] = useState('')
  const [versaoImagem, setVersaoImagem] = useState(0)
  const [zoom, setZoom] = useState(1)
  const [horizontal, setHorizontal] = useState(0)
  const [vertical, setVertical] = useState(0)
  const [erro, setErro] = useState('')

  useEffect(() => {
    imagemRef.current = null
    if (!fonte) return undefined
    const imagem = new Image()
    imagem.onload = () => { imagemRef.current = imagem; setVersaoImagem(atual => atual + 1) }
    imagem.onerror = () => setErro('Não foi possível abrir a imagem.')
    imagem.src = fonte
    return () => { imagem.onload = null; imagem.onerror = null }
  }, [fonte])

  useEffect(() => {
    if (previa.current && imagemRef.current) desenharRecorte(previa.current, imagemRef.current, zoom, horizontal, vertical)
  }, [fonte, versaoImagem, zoom, horizontal, vertical])

  function iniciarRecorte(origem) {
    setZoom(1); setHorizontal(0); setVertical(0); setErro(''); setFonte(origem)
  }

  function escolherArquivo(evento) {
    const imagem = evento.target.files?.[0]
    evento.target.value = ''
    if (!imagem) return
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(imagem.type)) {
      setErro('Escolha uma imagem PNG, JPG ou WebP.')
      return
    }
    if (imagem.size > PAPEL_PAREDE_TAMANHO_MAX_MB * 1024 * 1024) {
      setErro(`A imagem original deve ter até ${PAPEL_PAREDE_TAMANHO_MAX_MB} MB.`)
      return
    }
    const leitor = new FileReader()
    leitor.onload = () => iniciarRecorte(typeof leitor.result === 'string' ? leitor.result : '')
    leitor.onerror = () => setErro('Não foi possível ler a imagem escolhida.')
    leitor.readAsDataURL(imagem)
  }

  function aplicarRecorte() {
    if (!imagemRef.current) return
    const canvas = document.createElement('canvas')
    canvas.width = 1200; canvas.height = 675
    desenharRecorte(canvas, imagemRef.current, zoom, horizontal, vertical)
    if (onChange(canvas.toDataURL('image/webp', 0.82))) { setFonte(''); setErro('') }
    else setErro('Não foi possível salvar a imagem neste navegador.')
  }

  return (
    <section className="surface perfil-card perfil-papel-parede">
      <h2>Papel de parede dos chats</h2>
      <p className="muted">Escolha e recorte uma imagem para Atendimentos e Chat interno. Ela fica somente neste navegador.</p>
      <input ref={arquivo} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={escolherArquivo} />
      <div className="perfil-wallpaper-actions">
        <button type="button" className="button button-soft" onClick={() => arquivo.current?.click()}>Escolher imagem</button>
        {valor && !fonte && <button type="button" className="button button-soft" onClick={() => iniciarRecorte(valor)}>Recortar imagem atual</button>}
        {valor && <button type="button" className="button button-soft" onClick={() => { onChange(''); setFonte('') }}>Remover imagem</button>}
      </div>
      <div className="wallpaper-preview" aria-label="Prévia do papel de parede" style={!fonte && valor ? { backgroundImage: `url("${valor}")` } : undefined}>
        {fonte && <canvas ref={previa} width="480" height="270" aria-label="Área de recorte" />}
        <div className="wallpaper-preview-shade" style={{ backgroundColor: tom === 'claro' ? `rgba(255,255,255,${opacidade})` : `rgba(0,0,0,${opacidade})` }} />
        <div className="wallpaper-preview-bubbles"><span>Mensagem recebida <small>10:30</small></span><span>Resposta enviada <small>10:31</small></span></div>
      </div>
      {fonte && <div className="wallpaper-crop-controls">
        <label>Zoom: {Math.round(zoom * 100)}%<input type="range" min="1" max="3" step="0.05" value={zoom} onChange={evento => setZoom(Number(evento.target.value))} /></label>
        <label>Posição horizontal<input type="range" min="-1" max="1" step="0.01" value={horizontal} onChange={evento => setHorizontal(Number(evento.target.value))} /></label>
        <label>Posição vertical<input type="range" min="-1" max="1" step="0.01" value={vertical} onChange={evento => setVertical(Number(evento.target.value))} /></label>
        <div className="perfil-wallpaper-actions"><button type="button" className="button button-primary" disabled={!imagemRef.current} onClick={aplicarRecorte}>Aplicar recorte</button><button type="button" className="button button-soft" onClick={() => setFonte('')}>Cancelar</button></div>
      </div>}
      <fieldset className="wallpaper-tone"><legend>Camada de contraste</legend><label><input type="radio" name="wallpaper-tone" checked={tom !== 'claro'} onChange={() => onTom('escuro')} /> Escura</label><label><input type="radio" name="wallpaper-tone" checked={tom === 'claro'} onChange={() => onTom('claro')} /> Clara</label></fieldset>
      <label className="wallpaper-opacity-control">Intensidade da camada: {Math.round(opacidade * 100)}% <input type="range" min="0.35" max="0.8" step="0.05" value={opacidade} onChange={evento => onOpacidade(Number(evento.target.value))} /></label>
      {erro && <p role="alert" className="form-error">{erro}</p>}
    </section>
  )
}

/* ───────────── ícones ───────────── */

const ICONES = {
  estoque: <path d="M3 7 12 3l9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10" />,
  garantia: <path d="M12 2 20 5v6c0 5-3.5 8.5-8 11-4.5-2.5-8-6-8-11V5zM9 12l2 2 4-4" />,
  devolucao: <><path d="M4 7h11a5 5 0 0 1 0 10H7" /><path d="m8 3-4 4 4 4" /></>,
  atendimento: <><path d="M3 12a9 9 0 0 1 18 0" /><path d="M3 12v5a2 2 0 0 0 2 2h2v-7H3zm18 0v7h-4v-7h4zM17 19a5 5 0 0 1-5 3" /></>,
  administracao: <><path d="M3 20h18M5 20V6l7-3 7 3v14M9 9h1m4 0h1M9 13h1m4 0h1" /></>,
  vendas: <path d="M3 4h8l10 10-7 7L4 11V4zM7.5 7.5h.01" />,
  equipe: <><circle cx="9" cy="8" r="3" /><path d="M3 20v-2a6 6 0 0 1 12 0v2M17 5a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5v1" /></>,
  clipe: <path d="m21 11.5-8.6 8.6a5 5 0 0 1-7.1-7.1l8.6-8.6a3.3 3.3 0 0 1 4.7 4.7l-8.6 8.6a1.7 1.7 0 0 1-2.4-2.4l7.9-7.9" />,
  mic: <><rect x="9" y="2" width="6" height="13" rx="3" /><path d="M5 10a7 7 0 0 0 14 0M12 17v5m-4 0h8" /></>,
  enviar: <path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" />,
  buscar: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
  voltar: <path d="m15 18-6-6 6-6" />,
  seta: <path d="m9 6 6 6-6 6" />,
  fechar: <path d="M6 6l12 12M18 6 6 18" />,
  conversa: <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" />,
  opcoes: <path d="m7 10 5 5 5-5" />,
  editar: <><path d="M4 20h4l11-11a2 2 0 0 0-4-4L4 16v4zM13 7l4 4" /></>,
  apagar: <><path d="M4 7h16M10 4h4M6 7l1 13h10l1-13M10 11v6m4-6v6" /></>,
  copiar: <><rect x="8" y="8" width="12" height="13" rx="2" /><path d="M16 8V5a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h2" /></>,
}

export function Icone({ nome, tamanho = 20, className }) {
  return (
    <svg className={className} width={tamanho} height={tamanho} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICONES[nome] || ICONES.equipe}
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

  const marcarApagada = id => setMensagens(atuais => atuais.map(item => item.id === id
    ? { ...item, texto: '', imagem_url: null, audio_url: null, apagada: true }
    : item))
  return { mensagens, temAnteriores, atualizar, carregarAnteriores, marcarApagada }
}

/* ───────────── diretório (coluna esquerda) ───────────── */

function Diretorio({ setores, conversas, aberto, onAlternar, colegaId, grupoId, onPessoa, onGrupo }) {
  const [busca, setBusca] = useState('')
  const [aba, setAba] = useState('recentes')
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
      <div className="int-directory-tabs" role="tablist" aria-label="Listas do chat interno">
        <button type="button" role="tab" aria-selected={aba === 'recentes'} className={aba === 'recentes' ? 'active' : ''} onClick={() => setAba('recentes')}>Recentes</button>
        <button type="button" role="tab" aria-selected={aba === 'equipe'} className={aba === 'equipe' ? 'active' : ''} onClick={() => setAba('equipe')}>Equipe</button>
      </div>

      <div className="conversation-items">
        {aba === 'recentes' && (conversas.length > 0 ? <section className="int-recents"><h3>Conversas recentes</h3>
          {conversas.map(item => <button type="button" key={`${item.tipo}-${item.alvo_id}`}
            className={`conversation-item int-person${(item.tipo === 'grupo' ? grupoId === item.alvo_id : colegaId === item.alvo_id) ? ' selected' : ''}`}
            onClick={() => (item.tipo === 'grupo'
              ? onGrupo(setores.find(setor => setor.id === item.alvo_id) || { id: item.alvo_id, nome: item.nome })
              : onPessoa(setores.flatMap(setor => setor.pessoas).find(pessoa => pessoa.id === item.alvo_id) || { id: item.alvo_id, nome: item.nome, foto_url: item.foto_url, ativo: true }))}>
            {item.tipo === 'grupo'
              ? <span className="conversation-avatar" aria-hidden="true"><Icone nome={setores.find(setor => setor.id === item.alvo_id)?.icone || 'equipe'} tamanho={18} /></span>
              : <Avatar nome={item.nome} fotoUrl={item.foto_url} />}
            <span className="conversation-item-main"><strong>{item.tipo === 'grupo' ? `Grupo · ${item.nome}` : item.nome}</strong>
              <small className="int-preview">{item.ultimo_remetente ? `${item.ultimo_remetente}: ` : ''}{item.ultima_previa || 'Conversa sem mensagens'}</small></span>
            <span className="conversation-item-meta">{item.ultima_em && <time>{messageHour(item.ultima_em)}</time>}
              {item.nao_lidas > 0 && <b className="nav-count">{item.nao_lidas > 99 ? '99+' : item.nao_lidas}</b>}</span>
          </button>)}
        </section> : <p className="empty-list">Nenhuma conversa recente.</p>)}
        {aba === 'equipe' && visiveis.map(({ setor, pessoas }) => {
          const expandido = Boolean(termo) || aberto === setor.id
          const online = setor.pessoas.filter(p => p.ativo && p.online).length
          return (
            <section key={setor.id}>
              <button type="button" className="int-sector-button" aria-expanded={expandido} onClick={() => onAlternar(setor.id)}>
                <span className="int-sector-icon"><Icone nome={setor.icone || iconeDoSetor(setor.nome)} tamanho={18} /></span>
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
                        <span className="conversation-avatar" aria-hidden="true"><Icone nome={setor.icone || iconeDoSetor(setor.nome)} tamanho={18} /></span>
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
        {aba === 'equipe' && termo && !visiveis.length && <p className="empty-list">Ninguém encontrado para “{busca.trim()}”.</p>}
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
          ? <span className="conversation-avatar large" aria-hidden="true"><Icone nome={grupo.icone || iconeDoSetor(grupo.nome)} /></span>
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

function ListaMensagens({ mensagens, meId, nomeRemetente, fotoRemetente, ehGrupo, temAnteriores, onAnteriores, onImagem, onApagar, onEditar, somenteLeitura }) {
  const area = useRef(null)
  const [menuId, setMenuId] = useState(null)
  const [copiaStatus, setCopiaStatus] = useState('')
  useEffect(() => { if (!copiaStatus) return undefined; const id = setTimeout(() => setCopiaStatus(''), 2400); return () => clearTimeout(id) }, [copiaStatus])
  const [editandoId, setEditandoId] = useState(null)
  const [textoEditado, setTextoEditado] = useState('')
  const [salvando, setSalvando] = useState(false)
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
              <div className={`${minha ? 'message-bubble message-bubble-outgoing' : 'message-bubble'}${!minha && !continua && ehGrupo ? ' int-bubble-with-author' : ''}`}>
                {!minha && !continua && ehGrupo && <div className="int-message-author"><Avatar
                  nome={ehGrupo ? mensagem.remetente_nome : nomeRemetente}
                  fotoUrl={ehGrupo ? mensagem.remetente_foto_url : fotoRemetente}
                /></div>}
                {!minha && !continua && ehGrupo && <div className="message-label">{mensagem.remetente_nome}</div>}
                {editandoId === mensagem.id ? <form className="int-edit-form" onSubmit={async evento => {
                  evento.preventDefault()
                  if (!textoEditado.trim() || salvando) return
                  setSalvando(true)
                  try { if (await onEditar(mensagem.id, textoEditado.trim())) setEditandoId(null) }
                  finally { setSalvando(false) }
                }}>
                  <textarea value={textoEditado} onChange={evento => setTextoEditado(evento.target.value)} maxLength="4000" rows="3" aria-label="Editar mensagem" autoFocus />
                  <div><button type="button" onClick={() => setEditandoId(null)} disabled={salvando}>Cancelar</button><button type="submit" disabled={salvando || !textoEditado.trim()}>Salvar</button></div>
                </form> : mensagem.apagada ? <div className="message-text int-deleted">Mensagem apagada</div> : mensagem.texto && <div className="message-text">{mensagem.texto}</div>}
                {mensagem.audio_url && <audio controls preload="metadata" src={mensagem.audio_url} aria-label="Áudio do chat interno" />}
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
                <time>{messageHour(mensagem.criada_em)}{mensagem.editada_em && ' · editada'}</time>
                {!mensagem.apagada && editandoId !== mensagem.id && (mensagem.texto || (minha && !somenteLeitura)) && <div className="int-message-options">
                  <button type="button" className="int-message-menu-trigger" aria-label="Opções da mensagem" aria-expanded={menuId === mensagem.id} onClick={() => setMenuId(menuId === mensagem.id ? null : mensagem.id)}><Icone nome="opcoes" tamanho={16} /></button>
                  {menuId === mensagem.id && <div className="int-message-menu">
                    {mensagem.texto && <button type="button" title="Copiar mensagem" aria-label="Copiar mensagem" onClick={async () => { const ok = await copiarTexto(mensagem.texto); setCopiaStatus(ok ? 'Mensagem copiada.' : 'Não foi possível copiar.'); setMenuId(null) }}><Icone nome="copiar" tamanho={16} /></button>}
                    {minha && !somenteLeitura && !mensagem.imagem_url && !mensagem.audio_url && <button type="button" title="Editar mensagem" aria-label="Editar mensagem" onClick={() => { setEditandoId(mensagem.id); setTextoEditado(mensagem.texto); setMenuId(null) }}><Icone nome="editar" tamanho={16} /></button>}
                    {minha && !somenteLeitura && <button type="button" title="Apagar mensagem" aria-label="Apagar mensagem" onClick={() => { setMenuId(null); if (window.confirm('Apagar esta mensagem para todos no chat interno?')) onApagar(mensagem.id) }}><Icone nome="apagar" tamanho={16} /></button>}
                  </div>}
                </div>}
              </div>
            </div>
          </Fragment>
        )
      })}
      {copiaStatus && <div className="copy-feedback" role="status" onClick={() => setCopiaStatus('')}>{copiaStatus}</div>}
    </div>
  )
}

function Composer({ rotas, destino, onEnviado, onErro }) {
  const [texto, setTexto] = useState('')
  const [imagem, setImagem] = useState(null)
  const [previa, setPrevia] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [gravando, setGravando] = useState(false)
  const [segundos, setSegundos] = useState(0)
  const campo = useRef(null)
  const arquivo = useRef(null)
  const audioArquivo = useRef(null)
  const gravador = useRef(null)
  const cancelarAudio = useRef(false)

  useEffect(() => {
    if (!gravando) return undefined
    const id = window.setInterval(() => setSegundos(valor => valor + 1), 1000)
    return () => window.clearInterval(id)
  }, [gravando])

  useEffect(() => () => {
    if (gravador.current?.state === 'recording') {
      cancelarAudio.current = true
      gravador.current.stop()
    }
  }, [])

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
    if (evento.key === 'Enter' && !evento.shiftKey && !evento.ctrlKey && !evento.metaKey && !evento.nativeEvent.isComposing) enviar(evento)
  }

  async function enviarAudio(blob) {
    if (enviando || blob.size > 16 * 1024 * 1024) {
      onErro('Escolha um áudio de até 16 MB.')
      return
    }
    setEnviando(true); onErro('')
    try {
      await postar(`${BASE}/${rotas.audios}`, { headers: { 'Content-Type': blob.type || 'audio/mpeg' }, body: blob }, 'Não foi possível enviar o áudio.')
      await onEnviado()
    } catch (falha) { onErro(falha.message) }
    finally { setEnviando(false) }
  }

  async function alternarGravacao() {
    if (gravador.current) { gravador.current.stop(); return }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      onErro('Microfone indisponível neste navegador. Anexe um arquivo de áudio.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const tipo = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/webm'].find(item => MediaRecorder.isTypeSupported(item))
      if (!tipo) { stream.getTracks().forEach(track => { track.stop() }); onErro('Formato de gravação não suportado.'); return }
      const recorder = new MediaRecorder(stream, { mimeType: tipo })
      const partes = []
      recorder.ondataavailable = evento => { if (evento.data.size) partes.push(evento.data) }
      recorder.onstop = async () => {
        stream.getTracks().forEach(track => { track.stop() })
        gravador.current = null
        setGravando(false)
        if (cancelarAudio.current) { cancelarAudio.current = false; return }
        if (partes.length) await enviarAudio(new Blob(partes, { type: tipo.startsWith('audio/ogg') ? 'audio/ogg' : 'audio/webm' }))
      }
      cancelarAudio.current = false
      gravador.current = recorder
      setSegundos(0)
      recorder.start()
      setGravando(true)
    } catch { onErro('Não foi possível acessar o microfone. Confira a permissão do navegador.') }
  }

  return (
    <div className="chat-composer">
      {gravando && <div className="gravacao-status" role="status"><span className="gravacao-ponto" />Gravando {String(Math.floor(segundos / 60)).padStart(2, '0')}:{String(segundos % 60).padStart(2, '0')}<button type="button" onClick={() => { cancelarAudio.current = true; gravador.current?.stop() }}>Cancelar</button><span>Toque no microfone verde para enviar.</span></div>}
      {imagem && (
        <div className="int-attachment">
          {previa && <img src={previa} alt="" />}
          <span><strong>{imagem.name}</strong><small>{Math.round(imagem.size / 1024)} KB · será convertida para WebP</small></span>
          <button type="button" className="int-icon-btn small" onClick={removerImagem} aria-label="Remover imagem"><Icone nome="fechar" tamanho={16} /></button>
        </div>
      )}
      <form onSubmit={enviar}>
        <input ref={arquivo} type="file" accept="image/*" hidden onChange={e => escolherImagem(e.target.files?.[0])} />
        <input ref={audioArquivo} type="file" accept=".mp3,.ogg,audio/mpeg,audio/ogg" hidden onChange={e => { const escolhido = e.target.files?.[0]; e.target.value = ''; if (escolhido) enviarAudio(escolhido) }} />
        <button type="button" className="int-icon-btn" onClick={() => arquivo.current?.click()} disabled={enviando} aria-label="Anexar imagem" title="Anexar imagem"><Icone nome="clipe" /></button>
        <button type="button" className="int-icon-btn int-audio-attach" onClick={() => audioArquivo.current?.click()} disabled={enviando || gravando} aria-label="Anexar áudio" title="Anexar áudio"><Icone nome="mic" tamanho={20} /><span>Áudio</span></button>
        <textarea ref={campo} rows="1" value={texto} maxLength="4000" placeholder={`Mensagem para ${destino}`} aria-label="Mensagem"
          onChange={e => setTexto(e.target.value)} onKeyDown={aoTeclar} onPaste={aoColar} disabled={gravando} />
        {texto.trim() || imagem ? <button type="submit" className="button button-primary" disabled={enviando || gravando}>
          <Icone nome="enviar" tamanho={16} /><span>{enviando ? 'Enviando…' : 'Enviar'}</span>
        </button> : <button type="button" className={`atendimento-mic${gravando ? ' gravando-audio' : ''}`} disabled={enviando} onClick={alternarGravacao} aria-label={gravando ? 'Parar e enviar gravação' : 'Gravar áudio'} title={gravando ? 'Parar e enviar gravação' : 'Gravar áudio'}><Icone nome="mic" /></button>}
      </form>
      <small className="composer-hint">Enter envia · Shift+Enter quebra a linha · imagens até 12 MB · áudio até 16 MB</small>
    </div>
  )
}

/* ───────────── conversa ativa ───────────── */

function Conversa({ rotas, grupo, colega, me, onVoltar, onImagem, onErro, atualizarConversas, onOpen, modoApresentacao }) {
  const { mensagens, temAnteriores, atualizar, carregarAnteriores, marcarApagada } = useMensagens(rotas.mensagens, onErro)
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
        mensagens={modoApresentacao ? mensagens.map(mensagem => ({ ...mensagem, texto: 'Mensagem de demonstração', imagem_url: null, audio_url: null, remetente_nome: `Colaborador ${mensagem.remetente_id}`, remetente_foto_url: null })) : mensagens}
        meId={me.id}
        nomeRemetente={grupo ? null : colega.nome}
        fotoRemetente={grupo ? null : colega.foto_url}
        ehGrupo={Boolean(grupo)}
        somenteLeitura={modoApresentacao}
        temAnteriores={temAnteriores}
        onAnteriores={carregarAnteriores}
        onImagem={onImagem}
        onApagar={async id => {
          try {
            await apagar(`${BASE}/${rotas.apagar(id)}`)
            marcarApagada(id)
            await atualizar(true)
            atualizarConversas()
          } catch (falha) { onErro(falha.message) }
        }}
        onEditar={async (id, texto) => {
          try {
            await editar(`${BASE}/${rotas.apagar(id)}`, texto)
            await atualizar(true)
            atualizarConversas()
            return true
          } catch (falha) { onErro(falha.message); return false }
        }}
      />
      {modoApresentacao ? <div className="chat-composer int-read-only" role="status">Modo apresentação · conversa somente para leitura</div> : <Composer
        rotas={rotas}
        destino={grupo ? `Grupo · ${grupo.nome}` : colega.nome}
        onEnviado={() => atualizar(true)}
        onErro={onErro}
      />}
    </>
  )
}

/* ───────────── página ───────────── */

export default function Interno({ me, abrirColegaId, onOpen, onUnreadChange, onVisualizarImagem, papelParede, opacidadePapelParede, tomPapelParede, modoApresentacao }) {
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
  const setoresVisiveis = modoApresentacao ? setores.map(setor => ({ ...setor, pessoas: setor.pessoas.map(pessoa => ({ ...pessoa, nome: nomeApresentacao(pessoa), foto_url: null })) })) : setores
  const conversasVisiveis = modoApresentacao ? conversas.map(item => ({ ...item, nome: item.tipo === 'grupo' ? item.nome : `Colaborador ${item.alvo_id}`, foto_url: null, ultimo_remetente: item.ultimo_remetente ? 'Colaborador' : null, ultima_previa: item.ultima_previa ? 'Mensagem de demonstração' : null })) : conversas
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
          setores={setoresVisiveis} conversas={conversasVisiveis} aberto={aberto} colegaId={colegaSel?.id} grupoId={grupoSel?.id}
          onAlternar={id => setAberto(atual => (atual === id ? null : id))}
          onPessoa={selecionarPessoa} onGrupo={selecionarGrupo}
        />
        <section
          className="chat-pane"
          aria-label="Conversa"
          style={papelParede ? {
            '--int-wallpaper': `linear-gradient(${tomPapelParede === 'claro' ? `rgba(255,255,255,${opacidadePapelParede})` : `rgba(0,0,0,${opacidadePapelParede})`},${tomPapelParede === 'claro' ? `rgba(255,255,255,${opacidadePapelParede})` : `rgba(0,0,0,${opacidadePapelParede})`}),url("${papelParede}")`,
            '--int-wallpaper-size': 'cover',
          } : undefined}
        >
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
              colega={modoApresentacao && colega ? { ...colega, nome: nomeApresentacao(colega), foto_url: null } : colega}
              me={me}
              modoApresentacao={modoApresentacao}
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
