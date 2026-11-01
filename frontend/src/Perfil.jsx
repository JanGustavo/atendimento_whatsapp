import { useEffect, useRef, useState } from 'react'
import ModalImagem from './ModalImagem.jsx'
import { fetchApi } from './api.js'

const FOTO_TIPOS_ACEITOS = ['image/png', 'image/jpeg', 'image/webp']
const FOTO_TAMANHO_MAX_MB = 2

function iniciais(nome = '') {
  return (
    nome
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((parte) => parte[0].toUpperCase())
      .join('') || 'FG'
  )
}

function AvatarPerfil({ nome, src, onAmpliar }) {
  return (
    <button
      type="button"
      className="perfil-avatar-button"
      onClick={onAmpliar}
      disabled={!src}
      aria-label={src ? 'Ampliar foto do perfil' : undefined}
      title={src ? 'Ampliar foto' : undefined}
    >
      <span className="perfil-avatar">
        {src ? <img src={src} alt={`Foto de ${nome}`} /> : <span aria-hidden="true">{iniciais(nome)}</span>}
      </span>
    </button>
  )
}

function FotoPerfil({ me, onEnviarFoto, onVisualizarFoto }) {
  const entrada = useRef(null)
  const [previa, setPrevia] = useState('')
  const [erroFoto, setErroFoto] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [fotoAberta, setFotoAberta] = useState(false)
  const envioDisponivel = typeof onEnviarFoto === 'function'

  useEffect(() => () => previa && URL.revokeObjectURL(previa), [previa])

  function aoAmpliar() {
    const url = previa || me.foto_url
    if (!url) return
    if (onVisualizarFoto) {
      onVisualizarFoto(url, me.nome)
    } else {
      setFotoAberta(true)
    }
  }

  async function escolher(evento) {
    const arquivo = evento.target.files?.[0]
    evento.target.value = ''
    if (!arquivo) return
    setErroFoto('')
    if (!FOTO_TIPOS_ACEITOS.includes(arquivo.type)) {
      setErroFoto('Use uma imagem PNG, JPG ou WebP.')
      return
    }
    if (arquivo.size > FOTO_TAMANHO_MAX_MB * 1024 * 1024) {
      setErroFoto(`A imagem deve ter até ${FOTO_TAMANHO_MAX_MB} MB.`)
      return
    }
    setEnviando(true)
    try {
      if (await onEnviarFoto(arquivo)) setPrevia(URL.createObjectURL(arquivo))
    } catch {
      setErroFoto('Não foi possível enviar a foto.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <>
      <AvatarPerfil nome={me.nome} src={previa || me.foto_url} onAmpliar={aoAmpliar} />
      <div className="perfil-foto">
        <input
          ref={entrada}
          type="file"
          accept={FOTO_TIPOS_ACEITOS.join(',')}
          onChange={escolher}
          hidden
          tabIndex={-1}
        />
        <button
          type="button"
          className="button button-soft"
          disabled={!envioDisponivel || enviando}
          onClick={() => entrada.current?.click()}
        >
          Anexar foto
        </button>
        <small className="perfil-dica">
          {envioDisponivel ? `PNG, JPG ou WebP, até ${FOTO_TAMANHO_MAX_MB} MB.` : 'Envio de foto disponível em breve.'}
        </small>
        {erroFoto && (
          <p className="form-error" role="alert">
            {erroFoto}
          </p>
        )}
      </div>
      {!onVisualizarFoto && fotoAberta && (previa || me.foto_url) && (
        <ModalImagem url={previa || me.foto_url} titulo={me.nome} onFechar={() => setFotoAberta(false)} />
      )}
    </>
  )
}

export default function Perfil({ me, onEnviarFoto, onVisualizarFoto }) {
  const [senhaAtual, setSenhaAtual] = useState('')
  const [senhaNova, setSenhaNova] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [aviso, setAviso] = useState('')
  const [erro, setErro] = useState('')
  const [busy, setBusy] = useState(false)

  async function salvar(evento) {
    evento.preventDefault()
    setErro('')
    setAviso('')
    if (senhaNova !== confirmacao) {
      setErro('As novas senhas não coincidem.')
      return
    }
    setBusy(true)
    try {
      const resposta = await fetchApi('/api/auth/senha', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
        body: new URLSearchParams({ senha_atual: senhaAtual, senha_nova: senhaNova, confirmacao }),
      })
      if (!resposta.ok) {
        const dados = await resposta.json().catch(() => ({}))
        throw new Error(dados.detail || 'Não foi possível alterar a senha.')
      }
      setSenhaAtual('')
      setSenhaNova('')
      setConfirmacao('')
      setAviso('Senha alterada com sucesso.')
    } catch (falha) {
      setErro(falha.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="perfil-page">
      <div className="page-intro">
        <div>
          <div className="eyebrow">MINHA CONTA</div>
          <h1>Perfil e senha</h1>
          <p>Atualize sua senha de acesso ao painel.</p>
        </div>
      </div>
      <div className="perfil-grid">
        <section className="surface perfil-card perfil-identidade" aria-label="Dados da conta">
          <FotoPerfil me={me} onEnviarFoto={onEnviarFoto} onVisualizarFoto={onVisualizarFoto} />
          <div className="perfil-dados">
            <strong>{me.nome}</strong>
            <span className="badge badge-neutral perfil-papel">{me.role}</span>
            <p className="muted">{me.email || 'Conta da equipe'}</p>
          </div>
        </section>
        <section className="surface perfil-card perfil-seguranca">
          <h2>Senha de acesso</h2>
          <p className="muted">Use pelo menos 8 caracteres.</p>
          <form className="perfil-form" onSubmit={salvar}>
            <label className="perfil-campo-largo">
              Senha atual
              <input
                type="password"
                autoComplete="current-password"
                value={senhaAtual}
                onChange={(e) => setSenhaAtual(e.target.value)}
                required
              />
            </label>
            <label>
              Nova senha
              <input
                type="password"
                autoComplete="new-password"
                minLength="8"
                value={senhaNova}
                onChange={(e) => setSenhaNova(e.target.value)}
                required
              />
            </label>
            <label>
              Confirmar nova senha
              <input
                type="password"
                autoComplete="new-password"
                minLength="8"
                value={confirmacao}
                onChange={(e) => setConfirmacao(e.target.value)}
                required
              />
            </label>
            {erro && (
              <p className="form-error perfil-feedback" role="alert">
                {erro}
              </p>
            )}
            {aviso && (
              <p className="perfil-success perfil-feedback" role="status">
                {aviso}
              </p>
            )}
            <div className="perfil-acoes">
              <button className="button button-primary" disabled={busy}>
                Alterar senha
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  )
}
