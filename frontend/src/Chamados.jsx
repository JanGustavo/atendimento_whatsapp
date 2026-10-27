import { useState } from 'react'

const nomes = { aberto: 'Aberto', em_atendimento: 'Em atendimento', fechado: 'Fechado' }

function dataHora(valor) {
  if (!valor) return ''
  const data = new Date(valor.endsWith('Z') ? valor : `${valor}Z`)
  return data.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function CartaoChamado({ chamado, onRequest, onClose, busy }) {
  const [solucao, setSolucao] = useState('')
  return <article className="ticket-card">
    <div className="ticket-card-top"><div><span className="eyebrow">CHAMADO #{chamado.id}</span><h3>{chamado.computador_nome}</h3></div><span className={`ticket-status ticket-status-${chamado.status}`}>{nomes[chamado.status]}</span></div>
    <p className="ticket-description">{chamado.descricao}</p>
    <div className="ticket-meta">Aberto em {dataHora(chamado.criado_em)} · {chamado.grupo === 'dono' ? 'PC do dono' : 'PC da empresa'}</div>
    {chamado.acessos.length > 0 && <div className="ticket-history"><strong>Registro de acessos</strong>{chamado.acessos.map(acesso => <div key={acesso.id}>{dataHora(acesso.inicio_em)} · {acesso.solicitante} · {acesso.resultado}</div>)}</div>}
    {chamado.solucao && <div className="ticket-solution"><strong>Solução registrada</strong><p>{chamado.solucao}</p></div>}
    {chamado.status !== 'fechado' && <div className="ticket-actions">
      <button className="button button-primary" disabled={busy || chamado.grupo === 'dono'} title={chamado.grupo === 'dono' ? 'O PC do dono não permite solicitação remota' : ''} onClick={() => onRequest(chamado.id)}>Solicitar acesso</button>
      {chamado.grupo === 'dono' && <small>Sem acesso remoto ao PC do dono.</small>}
      <form onSubmit={async event => { event.preventDefault(); if (await onClose(chamado.id, solucao.trim())) setSolucao('') }}>
        <input value={solucao} onChange={event => setSolucao(event.target.value)} placeholder="Descreva o que foi resolvido" minLength="3" maxLength="4000" required />
        <button className="button button-soft" disabled={busy || solucao.trim().length < 3}>Fechar chamado</button>
      </form>
    </div>}
  </article>
}

export default function Chamados({ me, chamados, computadores, usuarios, busy, onRequest, onClose, onCreateComputer }) {
  const [novo, setNovo] = useState({ nome: '', dono_id: '', grupo: 'empresa', mesh_node_id: '' })
  const abertos = chamados.filter(chamado => chamado.status !== 'fechado').length
  return <div className="tickets-page">
    <div className="page-intro"><div><div className="eyebrow">SUPORTE INTERNO</div><h1>Chamados dos computadores</h1><p>Problemas enviados pela equipe e histórico de atendimento.</p></div><span className="count-chip">{abertos} pendentes</span></div>
    <div className="tickets-layout"><section className="tickets-list">
      <div className="tickets-section-title"><h2>Todos os chamados</h2><p>Os pedidos novos aparecem automaticamente.</p></div>
      {chamados.map(chamado => <CartaoChamado key={chamado.id} chamado={chamado} busy={busy} onRequest={onRequest} onClose={onClose} />)}
      {!chamados.length && <div className="surface tickets-empty">Nenhum chamado aberto ainda. Use o atalho <strong>/chamado</strong> nos computadores cadastrados.</div>}
    </section><aside className="tickets-side">
      <section className="surface tickets-side-card"><div className="eyebrow">COMPUTADORES</div><h3>{computadores.length} cadastrados</h3><div className="ticket-pc-list">{computadores.map(pc => <div key={pc.id}><strong>{pc.nome}</strong><small>{pc.dono_nome || 'Sem dono'} · {pc.grupo}</small></div>)}</div></section>
      {me.role === 'gestor' && <section className="surface tickets-side-card"><div className="eyebrow">GESTÃO</div><h3>Cadastrar computador</h3><form className="ticket-pc-form" onSubmit={async event => { event.preventDefault(); if (await onCreateComputer(novo)) setNovo({ nome: '', dono_id: '', grupo: 'empresa', mesh_node_id: '' }) }}>
        <label>Nome amigável<input value={novo.nome} onChange={event => setNovo({ ...novo, nome: event.target.value })} placeholder="Ex.: PC Caixa 1" required /></label>
        <label>Dono do PC<select value={novo.dono_id} onChange={event => setNovo({ ...novo, dono_id: event.target.value })} required><option value="">Selecione</option>{usuarios.map(usuario => <option key={usuario.id} value={usuario.id}>{usuario.nome}</option>)}</select></label>
        <label>Grupo<select value={novo.grupo} onChange={event => setNovo({ ...novo, grupo: event.target.value })}><option value="empresa">Empresa</option><option value="dono">Dono</option></select></label>
        <label>Mesh node ID (opcional)<input value={novo.mesh_node_id} onChange={event => setNovo({ ...novo, mesh_node_id: event.target.value })} placeholder="Para integração futura" /></label>
        <button className="button button-primary" disabled={busy}>Cadastrar</button>
      </form></section>}
    </aside></div>
  </div>
}
