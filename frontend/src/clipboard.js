export async function copiarTexto(texto) {
  if (!texto) return false
  try {
    await navigator.clipboard.writeText(texto)
    return true
  } catch {
    const campo = document.createElement('textarea')
    try {
      campo.value = texto
      campo.style.position = 'fixed'
      campo.style.opacity = '0'
      document.body.appendChild(campo)
      campo.select()
      return document.execCommand('copy')
    } catch {
      return false
    } finally {
      campo.remove()
    }
  }
}
