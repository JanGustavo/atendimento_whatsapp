/** Ponto único para chamadas HTTP do painel e do formulário público. */
export function fetchApi(path, options = {}) {
  return fetch(path, { credentials: 'same-origin', ...options })
}

export async function erroApi(response, fallback) {
  let mensagem = fallback || `Não foi possível concluir (${response.status}).`
  try {
    const dados = await response.json()
    if (typeof dados.detail === 'string') mensagem = dados.detail
  } catch {
    // Algumas respostas não têm corpo JSON.
  }
  const erro = new Error(mensagem)
  erro.status = response.status
  return erro
}

export async function getJSON(path) {
  const response = await fetchApi(path)
  if (!response.ok) {
    const erro = new Error(response.status === 401
      ? 'Sessão encerrada. Entre novamente.'
      : `Falha ao carregar (${response.status}).`)
    erro.status = response.status
    throw erro
  }
  return response.json()
}

export async function postForm(path, values) {
  const body = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null) body.set(key, String(value))
  })
  const response = await fetchApi(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
    body,
  })
  if (!response.ok) throw await erroApi(response)
}
