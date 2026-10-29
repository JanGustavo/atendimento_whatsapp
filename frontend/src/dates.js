export function messageDate(value) {
  if (!value) return null
  const date = new Date(/[Z+-]\d\d:?\d\d$/.test(value) || value.endsWith('Z') ? value : `${value}Z`)
  return Number.isNaN(date.getTime()) ? null : date
}

export function messageDay(value) {
  const date = messageDate(value)
  return date
    ? date.toLocaleDateString('pt-BR', { day: 'numeric', month: 'long', year: 'numeric' })
    : ''
}

export function messageHour(value) {
  const date = messageDate(value)
  return date ? date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : ''
}
