import { Fragment, useEffect, useRef, useState } from 'react'
import { messageDay, messageHour } from './dates.js'

function SetorIcon({ nome }) {
  const comum = {
    width: 20,
    height: 20,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
  }
  if (nome.toLowerCase().includes('estoque'))
    return (
      <svg {...comum}>
        <path d="M3 7 12 3l9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10" />
      </svg>
    )
  if (nome.toLowerCase().includes('garantia'))
    return (
      <svg {...comum}>
        <path d="M12 2 20 5v6c0 5-3.5 8.5-8 11-4.5-2.5-8-6-8-11V5zM9 12l2 2 4-4" />
      </svg>
    )
  if (nome.toLowerCase().includes('venda'))
    return (
      <svg {...comum}>
        <path d="M3 4h8l10 10-7 7L4 11V4zM7.5 7.5h.01" />
      </svg>
    )
  return (
    <svg {...comum}>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20v-2a6 6 0 0 1 12 0v2M17 5a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5v1" />
    </svg>
  )
}

async function leitura(url) {
  const resposta = await fetch(url, { credentials: 'same-origin' })
  if (!resposta.ok) throw new Error('Não foi possível carregar o chat interno.')
  return resposta.json()
}

async function converterWebp(arquivo) {
  if (arquivo.size > 12 * 1024 * 1024) throw new Error('Escolha uma imagem de até 12 MB.')
  const origem = await createImageBitmap(arquivo)
  try {
    const escala = Math.min(1, 1600 / Math.max(origem.width, origem.height))
    const tela = document.createElement('canvas')
    tela.width = Math.max(1, Math.round(origem.width * escala))
    tela.height = Math.max(1, Math.round(origem.height * escala))
    tela.getContext('2d').drawImage(origem, 0, 0, tela.width, tela.height)
    const webp = await new Promise((resolve) => tela.toBlob(resolve, 'image/webp', 0.78))
    if (!webp || webp.type !== 'image/webp' || webp.size > 2 * 1024 * 1024)
      throw new Error('Não foi possível preparar a imagem em WebP (limite de 2 MB).')
    return webp
  } finally {
    origem.close()
  }
}

export default function Interno({ me, abrirColegaId, onOpen }) {
  const [setores, setSetores] = useState([])
  const [aberto, setAberto] = useState(null)
  const [colega, setColega] = useState(null)
  const [grupo, setGrupo] = useState(null)
  const [mensagens, setMensagens] = useState([])
  const [texto, setTexto] = useState('')
  const [imagem, setImagem] = useState(null)
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [temAnteriores, setTemAnteriores] = useState(false)
  const rolagem = useRef(null)
  const arquivoInput = useRef(null)
  const primeiroId = useRef(null)
  const carregando = useRef(false)
  const ultimoVisivel = useRef(null)
  const colegaAtual =
    setores.flatMap((setor) => setor.pessoas).find((pessoa) => pessoa.id === colega?.id) || colega
  const grupoAtual = setores.find((setor) => setor.id === grupo?.id) || grupo
  const alvo = grupo ? `grupos/${grupo.id}/mensagens` : colega ? `mensagens/${colega.id}` : null

  useEffect(() => {
    const atualizar = () =>
      leitura('/api/interno/setores')
        .then(setSetores)
        .catch((falha) => setErro(falha.message))
    atualizar()
    const intervalo = setInterval(atualizar, 3000)
    return () => clearInterval(intervalo)
  }, [])

  useEffect(() => {
    if (!alvo) return
    let ativo = true
    setMensagens([])
    setTemAnteriores(false)
    primeiroId.current = null
    ultimoVisivel.current = null
    const atualizar = () =>
      leitura(`/api/interno/${alvo}`)
        .then((novas) => {
          if (!ativo) return
          setMensagens((anteriores) => {
            if (!anteriores.length) {
              setTemAnteriores(novas.length === 50)
              primeiroId.current = novas[0]?.id || null
              return novas
            }
            const ids = new Set(anteriores.map((item) => item.id))
            return [...anteriores, ...novas.filter((item) => !ids.has(item.id))].sort(
              (a, b) => a.id - b.id,
            )
          })
        })
        .catch((falha) => {
          if (ativo) setErro(falha.message)
        })
    atualizar()
    const intervalo = setInterval(atualizar, 3000)
    return () => {
      ativo = false
      clearInterval(intervalo)
    }
  }, [alvo])
  useEffect(() => {
    const ultimo = mensagens.at(-1)?.id
    if (ultimo && ultimo !== ultimoVisivel.current) {
      ultimoVisivel.current = ultimo
      requestAnimationFrame(() => {
        if (rolagem.current) rolagem.current.scrollTop = rolagem.current.scrollHeight
      })
    }
  }, [mensagens.at(-1)?.id])
  async function carregarAnteriores() {
    if (!alvo || !temAnteriores || !primeiroId.current || carregando.current) return
    carregando.current = true
    const area = rolagem.current
    const altura = area?.scrollHeight || 0
    try {
      const antigas = await leitura(`/api/interno/${alvo}?antes=${primeiroId.current}`)
      setTemAnteriores(antigas.length === 50)
      if (antigas.length) {
        primeiroId.current = antigas[0].id
        setMensagens((atuais) => {
          const ids = new Set(atuais.map((item) => item.id))
          return [...antigas.filter((item) => !ids.has(item.id)), ...atuais]
        })
        requestAnimationFrame(() => {
          if (area) area.scrollTop += area.scrollHeight - altura
        })
      }
    } catch (falha) {
      setErro(falha.message)
    } finally {
      carregando.current = false
    }
  }
  useEffect(() => {
    if (colega && mensagens.length) onOpen(colega.id)
  }, [colega?.id, mensagens.length])

  useEffect(() => {
    if (!abrirColegaId || !setores.length) return
    const pessoa = setores
      .flatMap((setor) => setor.pessoas)
      .find((item) => item.id === abrirColegaId)
    if (pessoa) {
      setGrupo(null)
      setColega(pessoa)
      const setor = setores.find((item) => item.pessoas.some((usuario) => usuario.id === pessoa.id))
      setAberto(setor?.id || null)
      onOpen(pessoa.id)
    }
  }, [abrirColegaId, setores.length])

  async function enviar(evento) {
    evento.preventDefault()
    if (!alvo || !texto.trim() || enviando) return
    setEnviando(true)
    setErro('')
    try {
      const resposta = await fetch(`/api/interno/${alvo}`, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
        body: new URLSearchParams({ texto: texto.trim() }),
      })
      if (!resposta.ok) throw new Error('Não foi possível enviar a mensagem.')
      setTexto('')
      const novas = await leitura(`/api/interno/${alvo}`)
      setMensagens((atuais) =>
        [...atuais, ...novas.filter((item) => !atuais.some((atual) => atual.id === item.id))].sort(
          (a, b) => a.id - b.id,
        ),
      )
    } catch (falha) {
      setErro(falha.message)
    } finally {
      setEnviando(false)
    }
  }

  async function enviarImagem() {
    if (!alvo || !imagem || enviando) return
    setEnviando(true)
    setErro('')
    try {
      const webp = await converterWebp(imagem)
      const caminho = grupo
        ? `/api/interno/grupos/${grupo.id}/imagens`
        : `/api/interno/mensagens/${colega.id}/imagem`
      const resposta = await fetch(caminho, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'image/webp' },
        body: webp,
      })
      if (!resposta.ok) {
        const detalhe = await resposta.json().catch(() => ({}))
        throw new Error(detalhe.detail || 'Não foi possível enviar a imagem.')
      }
      setImagem(null)
      if (arquivoInput.current) arquivoInput.current.value = ''
      const novas = await leitura(`/api/interno/${alvo}`)
      setMensagens((atuais) =>
        [...atuais, ...novas.filter((item) => !atuais.some((atual) => atual.id === item.id))].sort(
          (a, b) => a.id - b.id,
        ),
      )
    } catch (falha) {
      setErro(falha.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="interno-page">
      <div className="page-intro">
        <div>
          <div className="eyebrow">EQUIPE</div>
          <h1>Chat interno</h1>
          <p>
            Converse com a equipe sem usar o WhatsApp. Colegas offline também recebem mensagens.
          </p>
        </div>
        <span className="demo-pill">INTERNO</span>
      </div>
      {erro && (
        <div className="toast toast-error" role="alert">
          {erro}
        </div>
      )}
      <div className="interno-grid">
        <aside className="surface interno-directory">
          <h2>Setores</h2>
          <p className="muted">Abra um setor para ver todos os usuários cadastrados.</p>
          {setores.map((setor) => (
            <div key={setor.id} className="interno-sector">
              <button
                className="interno-sector-button"
                onClick={() => setAberto(aberto === setor.id ? null : setor.id)}
                aria-expanded={aberto === setor.id}
              >
                <span className="interno-sector-title">
                  <span className="interno-sector-icon">
                    <SetorIcon nome={setor.nome} />
                  </span>
                  <span>
                    {setor.nome}
                    <small>{setor.total_pessoas} pessoas</small>
                  </span>
                </span>
                <span aria-hidden="true">{aberto === setor.id ? '▾' : '▸'}</span>
              </button>
              {aberto === setor.id && (
                <div className="interno-people">
                  {setor.grupo_ativo && (
                    <button
                      className={grupo?.id === setor.id ? 'selected' : ''}
                      onClick={() => {
                        setGrupo(setor)
                        setColega(null)
                        setMensagens([])
                        setErro('')
                      }}
                    >
                      <span className="interno-sector-icon">
                        <SetorIcon nome={setor.nome} />
                      </span>
                      <span>
                        Grupo · {setor.nome}
                        <small>Todos os membros ativos</small>
                      </span>
                    </button>
                  )}
                  {setor.pessoas.length ? (
                    setor.pessoas.map((pessoa) => (
                      <button
                        key={pessoa.id}
                        className={colega?.id === pessoa.id ? 'selected' : ''}
                        disabled={!pessoa.ativo}
                        onClick={() => {
                          setGrupo(null)
                          setColega(pessoa)
                          setMensagens([])
                          setErro('')
                          onOpen(pessoa.id)
                        }}
                      >
                        <span
                          className={
                            pessoa.ativo && pessoa.online
                              ? 'status-dot'
                              : 'status-dot status-dot-muted'
                          }
                        />
                        <span>
                          {pessoa.nome}
                          <small>
                            {!pessoa.ativo ? 'Inativo' : pessoa.online ? 'Online' : 'Offline'}
                          </small>
                        </span>
                      </button>
                    ))
                  ) : (
                    <small>Nenhum usuário neste setor.</small>
                  )}
                </div>
              )}
            </div>
          ))}
        </aside>
        <section className="surface interno-chat">
          {!alvo ? (
            <div className="chat-placeholder">
              <h2>Escolha uma conversa</h2>
              <p>Abra um setor e selecione o grupo ou alguém da equipe.</p>
            </div>
          ) : (
            <>
              <header>
                <h2>{grupo ? `Grupo · ${grupoAtual.nome}` : colega.nome}</h2>
                {grupo ? (
                  <span className="badge badge-open">Setor</span>
                ) : (
                  <span className={colegaAtual?.online ? 'badge badge-open' : 'badge badge-closed'}>
                    {colegaAtual?.online ? 'Online' : 'Offline'}
                  </span>
                )}
              </header>
              <div
                className="interno-messages"
                ref={rolagem}
                onScroll={(evento) => {
                  if (evento.currentTarget.scrollTop < 40) carregarAnteriores()
                }}
              >
                {temAnteriores && (
                  <button className="older-messages" onClick={carregarAnteriores}>
                    Carregar mensagens anteriores
                  </button>
                )}
                {mensagens.length ? (
                  mensagens.map((mensagem, index) => (
                    <Fragment key={mensagem.id}>
                      {(index === 0 ||
                        messageDay(mensagem.criada_em) !==
                          messageDay(mensagens[index - 1].criada_em)) && (
                        <div className="day-divider">
                          <span>{messageDay(mensagem.criada_em)}</span>
                        </div>
                      )}
                      <div
                        className={
                          mensagem.remetente_id === me.id
                            ? 'interno-message mine'
                            : 'interno-message'
                        }
                      >
                        <strong>
                          {mensagem.remetente_id === me.id
                            ? 'Você'
                            : grupo
                              ? mensagem.remetente_nome
                              : colega.nome}
                        </strong>
                        {mensagem.texto && <p>{mensagem.texto}</p>}
                        {mensagem.imagem_url && (
                          <img
                            className="interno-imagem"
                            src={mensagem.imagem_url}
                            alt="Imagem enviada no chat"
                            loading="lazy"
                          />
                        )}
                        <time>{messageHour(mensagem.criada_em)}</time>
                      </div>
                    </Fragment>
                  ))
                ) : (
                  <p className="muted">Nenhuma mensagem nesta conversa.</p>
                )}
              </div>
              <form onSubmit={enviar}>
                <input
                  value={texto}
                  onChange={(evento) => setTexto(evento.target.value)}
                  placeholder="Escreva uma mensagem interna..."
                  maxLength="4000"
                  required
                />
                <button className="button button-primary" disabled={enviando || !texto.trim()}>
                  Enviar
                </button>
              </form>
              <div className="interno-image-controls">
                <label>
                  Imagem{' '}
                  <input
                    ref={arquivoInput}
                    type="file"
                    accept="image/*"
                    onChange={(evento) => setImagem(evento.target.files?.[0] || null)}
                  />
                </label>
                <button
                  className="button button-soft"
                  disabled={enviando || !imagem}
                  onClick={enviarImagem}
                >
                  Enviar imagem
                </button>
                <small>Convertida para WebP antes do envio · até 2 MB</small>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
