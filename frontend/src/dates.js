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

export function messageDateTime(value) {
  const day = messageDay(value)
  const hour = messageHour(value)
  return day && hour ? `${day}, ${hour}` : ''
}

export function shortDateTime(value) {
  const date = messageDate(value)
  if (!date) return ''
  return `${date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })} ${messageHour(value)}`
}

export function readDateTime(value) {
  const date = messageDate(value)
  if (!date) return ''
  const today = new Date()
  return date.toDateString() === today.toDateString() ? messageHour(value) : messageDateTime(value)
}
