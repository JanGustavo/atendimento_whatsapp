import { useState } from 'react'

export default function Perfil({ me }) {
  const [senhaAtual, setSenhaAtual] = useState('')
  const [senhaNova, setSenhaNova] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [aviso, setAviso] = useState('')
  const [erro, setErro] = useState('')
  const [busy, setBusy] = useState(false)

  async function salvar(evento) {
    evento.preventDefault()
    setErro(''); setAviso('')
    if (senhaNova !== confirmacao) { setErro('As novas senhas não coincidem.'); return }
    setBusy(true)
    try {
      const resposta = await fetch('/api/auth/senha', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
        body: new URLSearchParams({ senha_atual: senhaAtual, senha_nova: senhaNova, confirmacao }),
      })
      if (!resposta.ok) {
        const dados = await resposta.json().catch(() => ({}))
        throw new Error(dados.detail || 'Não foi possível alterar a senha.')
      }
      setSenhaAtual(''); setSenhaNova(''); setConfirmacao('')
      setAviso('Senha alterada com sucesso.')
    } catch (falha) { setErro(falha.message) }
    finally { setBusy(false) }
  }

  return <div className="perfil-page">
    <div className="page-intro"><div><div className="eyebrow">MINHA CONTA</div><h1>Perfil e senha</h1><p>Atualize sua senha de acesso ao painel.</p></div></div>
    <section className="surface perfil-card">
      <div><strong>{me.nome}</strong><p className="muted">{me.role} · {me.email || 'Conta da equipe'}</p></div>
      <form onSubmit={salvar}>
        <label>Senha atual<input type="password" autoComplete="current-password" value={senhaAtual} onChange={e => setSenhaAtual(e.target.value)} required /></label>
        <label>Nova senha<input type="password" autoComplete="new-password" minLength="8" value={senhaNova} onChange={e => setSenhaNova(e.target.value)} required /></label>
        <label>Confirmar nova senha<input type="password" autoComplete="new-password" minLength="8" value={confirmacao} onChange={e => setConfirmacao(e.target.value)} required /></label>
        {erro && <p className="form-error" role="alert">{erro}</p>}
        {aviso && <p className="perfil-success" role="status">{aviso}</p>}
        <button className="button button-primary" disabled={busy}>Alterar senha</button>
      </form>
    </section>
  </div>
}
