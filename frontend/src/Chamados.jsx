import { useEffect, useRef, useState } from 'react'
import { requisitar as fetchApi } from './api.js'
import { messageDateTime, shortDateTime } from './dates.js'

const NOMES_STATUS = { aberto: 'Aberto', em_atendimento: 'Em atendimento', fechado: 'Fechado' }
const NOVO_COMPUTADOR_VAZIO = { nome: '', dono_id: '', grupo: 'empresa', mesh_node_id: '' }

function dataHora(valor) {
  return messageDateTime(valor)
}

function useAvisoSessao() {
  const anteriores = useRef(null)
  const [aviso, setAviso] = useState(null)
  function observar(sessoes, conectado) {
    if (!conectado) { anteriores.current = null; return }
    const atuais = new Map(sessoes.map(sessao => [sessao.id, sessao.estado]))
    if (anteriores.current) {
      const encerrada = sessoes.find(sessao => sessao.estado === 'encerrada' && anteriores.current.get(sessao.id) === 'ativa')
      const iniciada = sessoes.find(sessao => sessao.estado === 'ativa' && anteriores.current.get(sessao.id) !== 'ativa')
      if (encerrada) setAviso({ tipo: 'fim', texto: `Conexão com ${encerrada.computador_nome} encerrada às ${dataHora(encerrada.fim_em)}.` })
      else if (iniciada) setAviso({ tipo: 'inicio', texto: `Conexão iniciada com ${iniciada.computador_nome} por ${iniciada.mesh_username}.` })
    }
    anteriores.current = atuais
  }
  return { aviso, setAviso, observar }
}

/* ---------- Peças compartilhadas ---------- */

function Campo({ rotulo, children }) {
  return <label>{rotulo}{children}</label>
}

function StatusChamado({ status }) {
  return <span className={`ticket-status ticket-status-${status} chamados-status`}>{NOMES_STATUS[status]}</span>
}

function RegistroAcessos({ acessos }) {
  const agrupados = acessos.reduce((lista, acesso) => {
    const anterior = lista.at(-1)
    if (anterior && anterior.solicitante_id === acesso.solicitante_id && anterior.resultado === acesso.resultado && shortDateTime(anterior.inicio_em) === shortDateTime(acesso.inicio_em)) anterior.repeticoes += 1
    else lista.push({ ...acesso, repeticoes: 1 })
    return lista
  }, [])
  return <div className="ticket-history chamados-acessos">
    <strong>Registro de acessos</strong>
    <ul className="chamados-acessos-lista">
      {agrupados.map(acesso => <li key={acesso.id} title={dataHora(acesso.inicio_em)}>
        <span>{shortDateTime(acesso.inicio_em)}</span><span>{acesso.solicitante}</span><span>{acesso.sessao_remota_ativa ? 'Sessão observada' : acesso.resultado === 'expirado' ? 'Pedido não confirmado a tempo' : acesso.acesso_url ? 'Aguardando confirmação no PC' : acesso.resultado}{acesso.repeticoes > 1 ? ` · ${acesso.repeticoes} registros` : ''}</span>
        {acesso.acesso_url && <a href={acesso.acesso_url} target="_blank" rel="noopener noreferrer" title="Abre a Área de Trabalho deste PC no MeshCentral; a conexão ainda exige confirmação nativa">Abrir Área de Trabalho deste PC ↗</a>}
      </li>)}
    </ul>
  </div>
}

function SolucaoRegistrada({ solucao }) {
  return <div className="ticket-solution chamados-solucao"><strong>Solução registrada</strong><p>{solucao === 'Nada' ? 'Ainda não registrada.' : solucao}</p></div>
}

/* Cartão usado nas duas visões. `visaoEquipe` liga grupo do PC e registro de acessos;
   `children` recebe o rodapé de ações (só a equipe tem). */
function CartaoChamado({ chamado, visaoEquipe = false, children }) {
  const doDono = chamado.grupo === 'dono'
  return <article className={`ticket-card chamados-card chamados-card-${chamado.status}`}>
    <div className="ticket-card-top chamados-card-top">
      <div><span className="eyebrow">CHAMADO #{chamado.id}</span><h3>{chamado.computador_nome} · {chamado.dono_nome || 'Usuário não vinculado'}</h3></div>
      <StatusChamado status={chamado.status} />
    </div>
    <p className="ticket-description">{chamado.descricao}</p>
    <div className="ticket-meta chamados-meta">
      <span>Aberto em {dataHora(chamado.criado_em)}</span>
      {visaoEquipe && doDono && <span className="chamados-chip chamados-chip-dono">PC do dono</span>}
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

export function ChamadosVendedor({ chamados, computadores, busy, onCreate, modoApresentacao }) {
  const [acessos, setAcessos] = useState([])
  const [sessoesRemotas, setSessoesRemotas] = useState({ monitor_conectado: false, sessoes: [] })
  const [erroAcesso, setErroAcesso] = useState('')
  const avisoSessao = useAvisoSessao()
  const botaoAutorizar = useRef(null)
  const pendente = acessos.find(acesso => acesso.resultado === 'pendente' && !acesso.confirmacao_no_mesh)
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
        if (ativo && sessoesResposta.ok) {
          const dados = await sessoesResposta.json()
          avisoSessao.observar(dados.sessoes, dados.monitor_conectado)
          setSessoesRemotas(dados)
        }
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
    {avisoSessao.aviso && <div className={`remote-session-alert remote-session-alert-${avisoSessao.aviso.tipo}`} role="alert"><strong>{avisoSessao.aviso.tipo === 'inicio' ? 'Acesso remoto iniciado' : 'Acesso remoto encerrado'}</strong><span>{modoApresentacao ? 'Evento de demonstração.' : avisoSessao.aviso.texto}</span><button type="button" onClick={() => avisoSessao.setAviso(null)} aria-label="Fechar aviso">×</button></div>}
    {acessos.some(acesso => acesso.confirmacao_no_mesh) && !sessoesRemotas.monitor_conectado && <p className="muted" role="status">Monitor de sessões desligado ou desconectado. O painel não consegue confirmar o fim da conexão; confira a barra do MeshCentral no computador.</p>}
    {sessoesRemotas.sessoes.filter(s => s.estado === 'ativa').map(s => (
      <div className="remote-session-banner" role="alert" key={s.id}>
        <strong>Possível sessão remota em andamento por {modoApresentacao ? 'Técnico' : s.mesh_username}</strong>
        <span>{modoApresentacao ? 'Computador fictício' : s.computador_nome} · {s.autorizacao_correlacionada ? 'Autorização vinculada' : 'Sem autorização vinculada ao chamado'}</span>
        {!sessoesRemotas.monitor_conectado && <span>Monitor de eventos desconectado: o estado exibido pode estar desatualizado.</span>}
        <span>Para interromper a conexão, use a barra de privacidade do MeshCentral no próprio computador.</span>
      </div>
    ))}
    {erroAcesso && <p role="alert">{erroAcesso}</p>}
    {pendente && !modoApresentacao && <div className="remote-consent-overlay">
      <section role="alertdialog" aria-modal="true" aria-labelledby="remote-consent-title" aria-describedby="remote-consent-description" className="remote-consent-dialog" onKeyDown={reterFoco}>
        <div className="eyebrow">SOLICITAÇÃO DE ACESSO REMOTO</div>
        <h2 id="remote-consent-title">O supervisor {pendente.solicitante} solicita acesso ao seu computador.</h2>
        <p id="remote-consent-description">Este aceite libera o link do seu computador para o técnico no painel. Confirme apenas se reconhecer o técnico e o motivo. Sem resposta, o pedido expira.</p>
        <dl className="remote-consent-details">
          <div><dt>Computador</dt><dd>{pendente.computador_nome}</dd></div>
          <div><dt>Chamado</dt><dd>#{pendente.chamado_id}</dd></div>
          <div><dt>Motivo</dt><dd>{pendente.motivo}</dd></div>
        </dl>
        <p className="muted">Quando o técnico iniciar a conexão no MeshCentral, você receberá outra confirmação no próprio computador.</p>
        <div className="remote-consent-actions">
          <button ref={botaoAutorizar} className="button button-primary" onClick={() => decidir(pendente.id, 'autorizar')}>Aceitar</button>
          <button className="button button-soft" onClick={() => decidir(pendente.id, 'recusar')}>Recusar</button>
        </div>
      </section>
    </div>}
    {acessos.map(acesso => <section className="surface tickets-side-card" key={acesso.id}>
      <strong>Solicitação de acesso remoto: {modoApresentacao ? 'Técnico' : acesso.solicitante}</strong>
      <p>{modoApresentacao ? 'Computador fictício' : acesso.computador_nome} · Chamado #{acesso.chamado_id}</p>
      <p>{acesso.sessao_remota_ativa
        ? 'Uma conexão foi observada. Para interrompê-la, use a barra de privacidade do MeshCentral no computador.'
        : acesso.confirmacao_no_mesh
        ? 'O técnico recebeu um link temporário. Confirme a conexão somente no aviso do MeshCentral exibido neste computador.'
        : acesso.resultado === 'pendente'
          ? 'Aguardando sua resposta no painel. Nenhum link foi liberado.'
          : 'Link liberado no painel. O MeshCentral também pedirá confirmação no computador antes da conexão.'}</p>
      {!modoApresentacao && acesso.confirmacao_no_mesh && acesso.resultado === 'pendente' && <button className="button button-soft" onClick={() => encerrar(acesso.id)}>Cancelar pedido no painel</button>}
      {!modoApresentacao && acesso.resultado === "autorizado" && <button className="button button-soft" onClick={() => encerrar(acesso.id)}>Encerrar autorização</button>}
    </section>)}
    {chamados.map(chamado => <CartaoChamado key={chamado.id} chamado={chamado} />)}
    {!chamados.length && <div className="surface tickets-empty chamados-vazio">Nenhum chamado registrado ainda.</div>}
  </EstruturaChamados>
}

/* ---------- Visão da equipe de suporte / gestor ---------- */

function AcoesChamado({ chamado, busy, onRequest, onClose }) {
  const [solucao, setSolucao] = useState('')
  const semAcessoRemoto = chamado.grupo === 'dono'
  const acessoPreparado = chamado.acessos.some(acesso => ['pendente', 'aceito'].includes(acesso.resultado) && !acesso.fim_em)

  async function fechar(event) {
    event.preventDefault()
    if (window.confirm('Fechar este chamado e salvar a solução?') && await onClose(chamado.id, solucao.trim())) setSolucao('')
  }

  return <div className="ticket-actions chamados-acoes">
    <button className="button button-primary" disabled={busy || semAcessoRemoto || acessoPreparado} title={semAcessoRemoto ? 'O PC do dono não permite solicitação remota' : ''} onClick={() => { if (window.confirm('Solicitar acesso remoto a este computador?')) onRequest(chamado.id) }}>{acessoPreparado ? 'Solicitação ativa' : 'Solicitar acesso'}</button>
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
        <strong>{pc.dono_nome || 'Usuário não vinculado'}</strong><small>{pc.nome}</small>
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
      <Campo rotulo="Mesh node ID (opcional)"><input value={novo.mesh_node_id} onChange={atualizar('mesh_node_id')} placeholder="Copie o ID do dispositivo no MeshCentral" /></Campo>
      <button className="button button-primary" disabled={busy}>Cadastrar</button>
    </form>
  </section>
}

export default function Chamados({ me, chamados, computadores, usuarios, busy, onRequest, onClose, onCreateComputer, modoApresentacao }) {
  const [sessoesRemotas, setSessoesRemotas] = useState({ monitor_conectado: false, meshcentral_url: null, remoto_provider: 'simulado', sessoes: [] })
  const avisoSessao = useAvisoSessao()
  useEffect(() => {
    let ativo = true
    async function atualizar() {
      try {
        const resposta = await fetchApi('/api/chamados/sessoes-remotas')
        if (ativo && resposta.ok) {
          const dados = await resposta.json()
          avisoSessao.observar(dados.sessoes, dados.monitor_conectado)
          setSessoesRemotas(dados)
        }
      } catch { /* historico permanece visivel */ }
    }
    atualizar()
    const intervalo = setInterval(atualizar, 3000)
    return () => { ativo = false; clearInterval(intervalo) }
  }, [])
  const aguardando = chamados.filter(chamado => chamado.status === 'aberto').length
  return <EstruturaChamados
    titulo="Chamados dos computadores"
    descricao="Problemas enviados pela equipe e histórico de atendimento."
    destaque={<span className="count-chip chamados-pendentes">{aguardando} aguardando resposta</span>}
    tituloLista="Todos os chamados"
    descricaoLista="Os pedidos novos aparecem automaticamente."
    lateral={<>
      <section className="surface tickets-side-card chamados-painel mesh-atalho">
        <div className="eyebrow">ACESSO REMOTO</div>
        <h3>MeshCentral</h3>
        <p>{sessoesRemotas.remoto_provider === 'meshcentral'
          ? 'Registre o pedido no chamado e abra o PC pelo link temporário. O colaborador confirma a conexão no próprio computador pelo MeshCentral.'
          : 'O painel ainda registra solicitações simuladas. O MeshCentral abre em outra aba e exige login próprio.'}</p>
        {sessoesRemotas.meshcentral_url
          ? <a className="button button-soft mesh-atalho-link" href={sessoesRemotas.meshcentral_url} target="_blank" rel="noopener noreferrer">Abrir MeshCentral ↗</a>
          : <small>Configure MESHCENTRAL_URL para abrir o servidor.</small>}
        <small>O botão abre o servidor; use o link do chamado para ir direto à Área de Trabalho do PC.</small>
        {me.role === 'gestor' && <details className="mesh-diagnostico"><summary>Diagnóstico</summary><small>{sessoesRemotas.monitor_conectado ? 'Monitor de sessões conectado.' : 'Monitor de sessões desligado ou desconectado: avisos de encerramento podem atrasar.'}</small></details>}
      </section>
      <ListaComputadores computadores={computadores} />
      {me.role === 'gestor' && <CadastroComputador usuarios={usuarios} busy={busy} onCreateComputer={onCreateComputer} />}
    </>}
  >
    {avisoSessao.aviso && <div className={`remote-session-alert remote-session-alert-${avisoSessao.aviso.tipo}`} role="alert"><strong>{avisoSessao.aviso.tipo === 'inicio' ? 'Acesso remoto iniciado' : 'Acesso remoto encerrado'}</strong><span>{modoApresentacao ? 'Evento de demonstração.' : avisoSessao.aviso.texto}</span><button type="button" onClick={() => avisoSessao.setAviso(null)} aria-label="Fechar aviso">×</button></div>}
    {sessoesRemotas.sessoes.length > 0 && <section className="surface tickets-side-card" aria-label="Auditoria de sessões MeshCentral">
      <h2>Sessões de desktop observadas no MeshCentral</h2>
      <p className="muted">{sessoesRemotas.monitor_conectado ? 'Monitor conectado' : 'Monitor desconectado: sessões podem estar desatualizadas'}</p>
      <ul className="ticket-history">
        {sessoesRemotas.sessoes.slice(0, 30).map(s => <li key={s.id}>
          <strong>{modoApresentacao ? 'Computador fictício' : s.computador_nome}</strong> · {modoApresentacao ? 'Técnico' : s.mesh_username} · {s.estado}
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
