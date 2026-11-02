export function formatPhone(value) {
  const digits = String(value || '').replace(/\D/g, '')
  if (!/^55\d{10,11}$/.test(digits)) return String(value || '')
  const ddd = digits.slice(2, 4)
  const local = digits.slice(4)
  return `+55 (${ddd}) ${local.slice(0, -4)}-${local.slice(-4)}`
}
