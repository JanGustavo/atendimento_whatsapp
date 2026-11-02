// Feriados nacionais fixos e Sexta-feira da Paixão (Páscoa pelo calendário gregoriano).
export function feriadosNacionais(ano) {
  if (!Number.isInteger(ano) || ano < 2020 || ano > 2100) return []
  const a = ano % 19
  const b = Math.floor(ano / 100)
  const c = ano % 100
  const d = Math.floor(b / 4)
  const e = b % 4
  const f = Math.floor((b + 8) / 25)
  const g = Math.floor((b - f + 1) / 3)
  const h = (19 * a + b - d - g + 15) % 30
  const i = Math.floor(c / 4)
  const k = c % 4
  const l = (32 + 2 * e + 2 * i - h - k + 7) % 7
  const m = Math.floor((a + 11 * h + 22 * l) / 451)
  const mesPascoa = Math.floor((h + l - 7 * m + 114) / 31)
  const diaPascoa = ((h + l - 7 * m + 114) % 31) + 1
  const sexta = new Date(Date.UTC(ano, mesPascoa - 1, diaPascoa - 2)).toISOString().slice(0, 10)
  return [
    [`${ano}-01-01`, 'Confraternização Universal'],
    [sexta, 'Paixão de Cristo'],
    [`${ano}-04-21`, 'Tiradentes'],
    [`${ano}-05-01`, 'Dia do Trabalho'],
    [`${ano}-09-07`, 'Independência do Brasil'],
    [`${ano}-10-12`, 'Nossa Senhora Aparecida'],
    [`${ano}-11-02`, 'Finados'],
    [`${ano}-11-15`, 'Proclamação da República'],
    [`${ano}-11-20`, 'Consciência Negra'],
    [`${ano}-12-25`, 'Natal'],
  ].sort(([a], [b]) => a.localeCompare(b)).map(([data, nome]) => ({ data, nome }))
}
