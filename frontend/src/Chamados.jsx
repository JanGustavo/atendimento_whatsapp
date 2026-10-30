import { useEffect, useState } from 'react'

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
  const [erroAcesso, setErroAcesso] = useState('')
  useEffect(() => {
    let ativo = true
    async function carregar() {
      try { const r = await fetch('/api/meus-acessos'); if (r.ok && ativo) setAcessos(await r.json()) } catch { /* rede indisponivel */ }
    }
    carregar()
    const intervalo = setInterval(carregar, 3000)
    return () => { ativo = false; clearInterval(intervalo) }
  }, [])
  async function decidir(id, acao) {
    const corpo = new URLSearchParams({ decisao: acao })
    const resposta = await fetch(`/api/meus-acessos/${id}/decisao`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: corpo })
    if (!resposta.ok) { setErroAcesso((await resposta.json()).detail || 'Nao foi possivel responder'); return }
    setErroAcesso('')
    setAcessos(lista => lista.filter(a => a.id !== id))
  }
  async function encerrar(id) {
    const resposta = await fetch(`/api/meus-acessos/${id}/encerrar`, { method: 'POST' })
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
    {erroAcesso && <p role="alert">{erroAcesso}</p>}
    {acessos.map(acesso => <section className="surface tickets-side-card" key={acesso.id}>
      <strong>Solicitação de acesso remoto: {acesso.solicitante}</strong>
      <p>{acesso.resultado === "pendente" ? "Autorize somente se reconhecer o técnico. A solicitação expira automaticamente." : "Autorização registrada. Conexão remota ainda não está habilitada."}</p>
      {acesso.resultado === "pendente" && <><button className="button button-primary" onClick={() => decidir(acesso.id, "autorizar")}>Autorizar</button> <button className="button button-soft" onClick={() => decidir(acesso.id, "recusar")}>Recusar</button></>}
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
  const abertos = chamados.filter(chamado => chamado.status !== 'fechado').length
  return <EstruturaChamados
    titulo="Chamados dos computadores"
    descricao="Problemas enviados pela equipe e histórico de atendimento."
    destaque={<span className="count-chip chamados-pendentes">{abertos} pendentes</span>}
    tituloLista="Todos os chamados"
    descricaoLista="Os pedidos novos aparecem automaticamente."
    lateral={<>
      <ListaComputadores computadores={computadores} />
      {me.role === 'gestor' && <CadastroComputador usuarios={usuarios} busy={busy} onCreateComputer={onCreateComputer} />}
    </>}
  >
    {chamados.map(chamado => <CartaoChamado key={chamado.id} chamado={chamado} visaoEquipe>
      {chamado.status !== 'fechado' && <AcoesChamado chamado={chamado} busy={busy} onRequest={onRequest} onClose={onClose} />}
    </CartaoChamado>)}
    {!chamados.length && <div className="surface tickets-empty chamados-vazio">Nenhum chamado aberto ainda. Use o atalho <strong>/chamado</strong> nos computadores cadastrados.</div>}
  </EstruturaChamados>
}
