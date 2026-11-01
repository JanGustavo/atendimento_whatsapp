import { useEffect, useRef, useState } from 'react'
import { requisitar as fetchApi } from './api.js'

const NOMES_STATUS = { aberto: 'Aberto', em_atendimento: 'Em atendimento', fechado: 'Fechado' }
const NOVO_COMPUTADOR_VAZIO = { nome: '', dono_id: '', grupo: 'empresa', mesh_node_id: '' }

function dataHora(valor) {
  if (!valor) return ''
  const data = new Date(valor.endsWith('Z') ? valor : `${valor}Z`)
  return data.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

/* ---------- Peças compartilhadas ---------- */

function Campo({ rotulo, children }) {
  return <label>{rotulo}{children}</label>
}

function StatusChamado({ status }) {
  return <span className={`ticket-status ticket-status-${status} chamados-status`}>{NOMES_STATUS[status]}</span>
}

function RegistroAcessos({ acessos }) {
  return <div className="ticket-history chamados-acessos">
    <strong>Registro de acessos</strong>
    <ul className="chamados-acessos-lista">
      {acessos.map(acesso => <li key={acesso.id}>
        <span>{dataHora(acesso.inicio_em)}</span><span>{acesso.solicitante}</span><span>{acesso.resultado}</span>
        {acesso.acesso_url && <a href={acesso.acesso_url} target="_blank" rel="noopener noreferrer">Abrir desktop</a>}
      </li>)}
    </ul>
  </div>
}

function SolucaoRegistrada({ solucao }) {
  return <div className="ticket-solution chamados-solucao"><strong>Solução registrada</strong><p>{solucao}</p></div>
}

/* Cartão usado nas duas visões. `visaoEquipe` liga grupo do PC e registro de acessos;
   `children` recebe o rodapé de ações (só a equipe tem). */
function CartaoChamado({ chamado, visaoEquipe = false, children }) {
  const doDono = chamado.grupo === 'dono'
  return <article className={`ticket-card chamados-card chamados-card-${chamado.status}`}>
    <div className="ticket-card-top chamados-card-top">
      <div><span className="eyebrow">CHAMADO #{chamado.id}</span><h3>{chamado.computador_nome}</h3></div>
      <StatusChamado status={chamado.status} />
    </div>
    <p className="ticket-description">{chamado.descricao}</p>
    <div className="ticket-meta chamados-meta">
      <span>Aberto em {dataHora(chamado.criado_em)}</span>
      {visaoEquipe && <span className={doDono ? 'chamados-chip chamados-chip-dono' : 'chamados-chip'}>{doDono ? 'PC do dono' : 'PC da empresa'}</span>}
    </div>
    {visaoEquipe && chamado.acessos.length > 0 && <RegistroAcessos acessos={chamado.acessos} />}
    {chamado.solucao && <SolucaoRegistrada solucao={chamado.solucao} />}
    {children}
  </article>
}

function EstruturaChamados({ titulo, descricao, destaque, tituloLista, descricaoLista, lateral, children }) {
  return <div className="tickets-page chamados-page">
    <div className="page-intro">
      <div><div className="eyebrow">SUPORTE INTERNO</div><h1>{titulo}</h1><p>{descricao}</p></div>
      {destaque}
    </div>
    <div className="tickets-layout chamados-layout">
      <section className="tickets-list chamados-lista">
        <div className="tickets-section-title chamados-secao-titulo"><h2>{tituloLista}</h2><p>{descricaoLista}</p></div>
        {children}
      </section>
      <aside className="tickets-side chamados-lateral">{lateral}</aside>
    </div>
  </div>
}

/* ---------- Visão do colaborador ---------- */

function NovoChamado({ computadores, busy, onCreate }) {
  const [computadorId, setComputadorId] = useState('')
  const [descricao, setDescricao] = useState('')
  const escolhido = computadorId || String(computadores[0]?.id || '')

  async function enviar(event) {
    event.preventDefault()
    if (await onCreate({ computador_id: escolhido, descricao: descricao.trim() })) setDescricao('')
  }

  return <section className="surface tickets-side-card chamados-painel">
    <div className="eyebrow">NOVO PEDIDO</div>
    <h3>Abrir chamado</h3>
    {!computadores.length
      ? <p className="muted">Nenhum computador vinculado à sua conta. Peça ao gestor para cadastrá-lo.</p>
      : <form className="ticket-pc-form chamados-form" onSubmit={enviar}>
        <Campo rotulo="Computador">
          <select value={escolhido} onChange={event => setComputadorId(event.target.value)} required>
            {computadores.map(pc => <option key={pc.id} value={pc.id}>{pc.nome}</option>)}
          </select>
        </Campo>
        <Campo rotulo="Descreva o problema">
          <textarea value={descricao} onChange={event => setDescricao(event.target.value)} minLength="3" maxLength="4000" rows="5" placeholder="Ex.: não consigo acessar o sistema" required />
        </Campo>
        <button className="button button-primary" disabled={busy || descricao.trim().length < 3}>Enviar chamado</button>
      </form>}
  </section>
}

export function ChamadosVendedor({ chamados, computadores, busy, onCreate }) {
  const [acessos, setAcessos] = useState([])
  const [sessoesRemotas, setSessoesRemotas] = useState({ monitor_conectado: false, sessoes: [] })
  const [erroAcesso, setErroAcesso] = useState('')
  const botaoAutorizar = useRef(null)
  const pendente = acessos.find(acesso => acesso.resultado === 'pendente')
  useEffect(() => {
    if (pendente) botaoAutorizar.current?.focus()
  }, [pendente?.id])

  function reterFoco(event) {
    if (event.key !== 'Tab') return
    const botoes = event.currentTarget.querySelectorAll('button:not([disabled])')
    const primeiro = botoes[0]
    const ultimo = botoes[botoes.length - 1]
    if (event.shiftKey && document.activeElement === primeiro) {
      event.preventDefault()
      ultimo?.focus()
    } else if (!event.shiftKey && document.activeElement === ultimo) {
      event.preventDefault()
      primeiro?.focus()
    }
  }

  useEffect(() => {
    let ativo = true
    async function carregar() {
      try {
        const [acessosResposta, sessoesResposta] = await Promise.all([
          fetchApi('/api/meus-acessos'),
          fetchApi('/api/meus-sessoes-remotas'),
        ])
        if (ativo && acessosResposta.ok) setAcessos(await acessosResposta.json())
        if (ativo && sessoesResposta.ok) setSessoesRemotas(await sessoesResposta.json())
      } catch { /* rede indisponivel, nao presumir que a sessao foi encerrada */ }
    }
    carregar()
    const intervalo = setInterval(carregar, 3000)
    return () => { ativo = false; clearInterval(intervalo) }
  }, [])
  async function decidir(id, acao) {
    const corpo = new URLSearchParams({ decisao: acao })
    const resposta = await fetchApi(`/api/meus-acessos/${id}/decisao`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: corpo })
    if (!resposta.ok) { setErroAcesso((await resposta.json()).detail || 'Nao foi possivel responder'); return }
    setErroAcesso('')
    setAcessos(lista => lista.filter(a => a.id !== id))
  }
  async function encerrar(id) {
    const resposta = await fetchApi(`/api/meus-acessos/${id}/encerrar`, { method: 'POST' })
    if (!resposta.ok) { setErroAcesso('Nao foi possivel encerrar'); return }
    setErroAcesso('')
    setAcessos(lista => lista.filter(a => a.id !== id))
  }
  return <EstruturaChamados
    titulo="Meus chamados"
    descricao="Conte o que aconteceu no seu computador para a equipe de suporte."
    tituloLista="Meus pedidos"
    descricaoLista="Você acompanha aqui os chamados do seu computador."
    lateral={<NovoChamado computadores={computadores} busy={busy} onCreate={onCreate} />}
  >
    {sessoesRemotas.sessoes.filter(s => s.estado === 'ativa').map(s => (
      <div className="remote-session-banner" role="alert" key={s.id}>
        <strong>Possível sessão remota em andamento por {s.mesh_username}</strong>
        <span>{s.computador_nome} · {s.autorizacao_correlacionada ? 'Autorização vinculada' : 'Sem autorização vinculada ao chamado'}</span>
        {!sessoesRemotas.monitor_conectado && <span>Monitor de eventos desconectado: o estado exibido pode estar desatualizado.</span>}
        <span>Para interromper a conexão, use a barra de privacidade do MeshCentral no próprio computador.</span>
      </div>
    ))}
    {erroAcesso && <p role="alert">{erroAcesso}</p>}
    {pendente && <div className="remote-consent-overlay">
      <section role="alertdialog" aria-modal="true" aria-labelledby="remote-consent-title" aria-describedby="remote-consent-description" className="remote-consent-dialog" onKeyDown={reterFoco}>
        <div className="eyebrow">SOLICITAÇÃO DE ACESSO REMOTO</div>
        <h2 id="remote-consent-title">O supervisor {pendente.solicitante} solicita acesso ao seu computador.</h2>
        <p id="remote-consent-description">Confirme apenas se reconhecer o técnico e o motivo. Sem resposta, a solicitação expira automaticamente.</p>
        <dl className="remote-consent-details">
          <div><dt>Computador</dt><dd>{pendente.computador_nome}</dd></div>
          <div><dt>Chamado</dt><dd>#{pendente.chamado_id}</dd></div>
          <div><dt>Motivo</dt><dd>{pendente.motivo}</dd></div>
        </dl>
        <p className="muted">Esta confirmação funciona somente enquanto o painel estiver aberto. Ela não inicia uma sessão remota.</p>
        <div className="remote-consent-actions">
          <button ref={botaoAutorizar} className="button button-primary" onClick={() => decidir(pendente.id, 'autorizar')}>Aceitar</button>
          <button className="button button-soft" onClick={() => decidir(pendente.id, 'recusar')}>Recusar</button>
        </div>
      </section>
    </div>}
    {acessos.map(acesso => <section className="surface tickets-side-card" key={acesso.id}>
      <strong>Solicitação de acesso remoto: {acesso.solicitante}</strong>
      <p>{acesso.computador_nome} · Chamado #{acesso.chamado_id}</p>
      <p>{acesso.resultado === 'pendente' ? 'Aguardando sua resposta. Nenhum acesso foi iniciado.' : 'Autorização registrada, mas nenhuma sessão remota foi iniciada.'}</p>
      {acesso.resultado === "autorizado" && <button className="button button-soft" onClick={() => encerrar(acesso.id)}>Encerrar autorização</button>}
    </section>)}
    {chamados.map(chamado => <CartaoChamado key={chamado.id} chamado={chamado} />)}
    {!chamados.length && <div className="surface tickets-empty chamados-vazio">Nenhum chamado registrado ainda.</div>}
  </EstruturaChamados>
}

/* ---------- Visão da equipe de suporte / gestor ---------- */

function AcoesChamado({ chamado, busy, onRequest, onClose }) {
  const [solucao, setSolucao] = useState('')
  const semAcessoRemoto = chamado.grupo === 'dono'
  const acessoPreparado = chamado.acessos.some(acesso => ['pendente', 'autorizado'].includes(acesso.resultado) && !acesso.fim_em)

  async function fechar(event) {
    event.preventDefault()
    if (await onClose(chamado.id, solucao.trim())) setSolucao('')
  }

  return <div className="ticket-actions chamados-acoes">
    <button className="button button-primary" disabled={busy || semAcessoRemoto || acessoPreparado} title={semAcessoRemoto ? 'O PC do dono não permite solicitação remota' : ''} onClick={() => onRequest(chamado.id)}>{acessoPreparado ? 'Solicitação ativa' : 'Solicitar acesso'}</button>
    {semAcessoRemoto && <small>Sem acesso remoto ao PC do dono.</small>}
    <form onSubmit={fechar}>
      <input value={solucao} onChange={event => setSolucao(event.target.value)} placeholder="Descreva o que foi resolvido" aria-label="Descreva o que foi resolvido" minLength="3" maxLength="4000" required />
      <button className="button button-soft" disabled={busy || solucao.trim().length < 3}>Fechar chamado</button>
    </form>
  </div>
}

function ListaComputadores({ computadores }) {
  return <section className="surface tickets-side-card chamados-painel">
    <div className="eyebrow">COMPUTADORES</div>
    <h3>{computadores.length} cadastrados</h3>
    <div className="ticket-pc-list chamados-pcs">
      {computadores.map(pc => <div key={pc.id} className={`chamados-pc chamados-pc-${pc.grupo}`}>
        <strong>{pc.nome}</strong><small>{pc.dono_nome || 'Sem dono'} · {pc.grupo}</small>
      </div>)}
    </div>
  </section>
}

function CadastroComputador({ usuarios, busy, onCreateComputer }) {
  const [novo, setNovo] = useState(NOVO_COMPUTADOR_VAZIO)
  const atualizar = campo => event => setNovo({ ...novo, [campo]: event.target.value })

  async function cadastrar(event) {
    event.preventDefault()
    if (await onCreateComputer(novo)) setNovo(NOVO_COMPUTADOR_VAZIO)
  }

  return <section className="surface tickets-side-card chamados-painel">
    <div className="eyebrow">GESTÃO</div>
    <h3>Cadastrar computador</h3>
    <form className="ticket-pc-form chamados-form" onSubmit={cadastrar}>
      <Campo rotulo="Nome amigável"><input value={novo.nome} onChange={atualizar('nome')} placeholder="Ex.: PC Caixa 1" required /></Campo>
      <Campo rotulo="Dono do PC">
        <select value={novo.dono_id} onChange={atualizar('dono_id')} required>
          <option value="">Selecione</option>
          {usuarios.map(usuario => <option key={usuario.id} value={usuario.id}>{usuario.nome}</option>)}
        </select>
      </Campo>
      <Campo rotulo="Grupo">
        <select value={novo.grupo} onChange={atualizar('grupo')}><option value="empresa">Empresa</option><option value="dono">Dono</option></select>
      </Campo>
      <Campo rotulo="Mesh node ID (opcional)"><input value={novo.mesh_node_id} onChange={atualizar('mesh_node_id')} placeholder="Para integração futura" /></Campo>
      <button className="button button-primary" disabled={busy}>Cadastrar</button>
    </form>
  </section>
}

export default function Chamados({ me, chamados, computadores, usuarios, busy, onRequest, onClose, onCreateComputer }) {
  const [sessoesRemotas, setSessoesRemotas] = useState({ monitor_conectado: false, meshcentral_url: null, remoto_provider: 'simulado', sessoes: [] })
  useEffect(() => {
    let ativo = true
    async function atualizar() {
      try {
        const resposta = await fetchApi('/api/chamados/sessoes-remotas')
        if (ativo && resposta.ok) setSessoesRemotas(await resposta.json())
      } catch { /* historico permanece visivel */ }
    }
    atualizar()
    const intervalo = setInterval(atualizar, 3000)
    return () => { ativo = false; clearInterval(intervalo) }
  }, [])
  const abertos = chamados.filter(chamado => chamado.status !== 'fechado').length
  return <EstruturaChamados
    titulo="Chamados dos computadores"
    descricao="Problemas enviados pela equipe e histórico de atendimento."
    destaque={<span className="count-chip chamados-pendentes">{abertos} pendentes</span>}
    tituloLista="Todos os chamados"
    descricaoLista="Os pedidos novos aparecem automaticamente."
    lateral={<>
      <section className="surface tickets-side-card chamados-painel mesh-atalho">
        <div className="eyebrow">ACESSO REMOTO</div>
        <h3>MeshCentral</h3>
        <p>{sessoesRemotas.remoto_provider === 'meshcentral'
          ? 'Abra o servidor em outra aba com sua conta MeshCentral. A autorização do chamado e a confirmação no computador são etapas separadas.'
          : 'O painel ainda registra solicitações simuladas. O MeshCentral abre em outra aba e exige login próprio.'}</p>
        {sessoesRemotas.meshcentral_url
          ? <a className="button button-soft mesh-atalho-link" href={sessoesRemotas.meshcentral_url} target="_blank" rel="noopener noreferrer">Abrir MeshCentral ↗</a>
          : <small>Configure MESHCENTRAL_URL para abrir o servidor.</small>}
        <small>O botão abre o servidor; não inicia acesso a um computador.</small>
      </section>
      <ListaComputadores computadores={computadores} />
      {me.role === 'gestor' && <CadastroComputador usuarios={usuarios} busy={busy} onCreateComputer={onCreateComputer} />}
    </>}
  >
    {sessoesRemotas.sessoes.length > 0 && <section className="surface tickets-side-card" aria-label="Auditoria de sessões MeshCentral">
      <h2>Sessões de desktop observadas no MeshCentral</h2>
      <p className="muted">{sessoesRemotas.monitor_conectado ? 'Monitor conectado' : 'Monitor desconectado: sessões podem estar desatualizadas'}</p>
      <ul className="ticket-history">
        {sessoesRemotas.sessoes.slice(0, 30).map(s => <li key={s.id}>
          <strong>{s.computador_nome}</strong> · {s.mesh_username} · {s.estado}
          <span> · {s.inicio_em ? dataHora(s.inicio_em) : 'Início não observado'} / {s.fim_em ? dataHora(s.fim_em) : 'Fim não observado'}</span>
          <span> · {s.autorizacao_correlacionada ? 'Vinculada a consentimento' : 'Sem vínculo com autorização'}</span>
        </li>)}
      </ul>
    </section>}
    {chamados.map(chamado => <CartaoChamado key={chamado.id} chamado={chamado} visaoEquipe>
      {chamado.status !== 'fechado' && <AcoesChamado chamado={chamado} busy={busy} onRequest={onRequest} onClose={onClose} />}
    </CartaoChamado>)}
    {!chamados.length && <div className="surface tickets-empty chamados-vazio">Nenhum chamado aberto ainda. Use o atalho <strong>/chamado</strong> nos computadores cadastrados.</div>}
  </EstruturaChamados>
}
