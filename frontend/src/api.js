/** Ponto único para chamadas HTTP do painel e do formulário público. */
export function requisitar(rota, opcoes = {}) {
  return fetch(rota, { credentials: 'same-origin', ...opcoes })
}

export async function erroApi(resposta, padrao) {
  let mensagem = padrao || `Não foi possível concluir (${resposta.status}).`
  try {
    const dados = await resposta.json()
    if (typeof dados.detail === 'string') mensagem = dados.detail
  } catch {
    // Algumas respostas não têm corpo JSON.
  }
  const erro = new Error(mensagem)
  erro.status = resposta.status
  return erro
}

export async function obterJSON(rota) {
  const resposta = await requisitar(rota)
  if (!resposta.ok) {
    const erro = new Error(resposta.status === 401
      ? 'Sessão encerrada. Entre novamente.'
      : `Falha ao carregar (${resposta.status}).`)
    erro.status = resposta.status
    throw erro
  }
  return resposta.json()
}

export async function enviarFormulario(rota, valores) {
  const corpo = new URLSearchParams()
  Object.entries(valores).forEach(([chave, valor]) => {
    if (valor !== undefined && valor !== null) corpo.set(chave, String(valor))
  })
  const resposta = await requisitar(rota, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
    body: corpo,
  })
  if (!resposta.ok) throw await erroApi(resposta)
}
