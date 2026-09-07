export function parseCsv(text) {
  const rows = []
  let row = [], field = '', quoted = false
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index]
    if (char === '"' && quoted && text[index + 1] === '"') { field += '"'; index += 1 }
    else if (char === '"') quoted = !quoted
    else if (char === ',' && !quoted) { row.push(field); field = '' }
    else if ((char === '\n' || char === '\r') && !quoted) {
      if (char === '\r' && text[index + 1] === '\n') index += 1
      row.push(field); field = ''
      if (row.some((value) => value.trim())) rows.push(row)
      row = []
    } else field += char
  }
  row.push(field)
  if (row.some((value) => value.trim())) rows.push(row)
  if (rows.length < 2) return []
  const headers = rows[0].map((value) => value.trim().toLowerCase())
  if (!headers.includes('text')) throw new Error('CSV must contain a text column')
  return rows.slice(1).map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index]?.trim() || ''])))
}

export function toAnalysisCsv(analyses) {
  const escape = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`
  const label = (item, task) => item.predictions?.[task]?.label || ''
  const headers = ['id', 'created_at', 'product', 'source', 'sentiment', 'aspect', 'intent', 'urgency', 'text']
  const rows = analyses.map((item) => [
    item.id, item.created_at, item.product, item.source,
    label(item, 'sentiment'), label(item, 'aspect') || 'other', label(item, 'intent'),
    label(item, 'urgency'), item.text,
  ].map(escape).join(','))
  return [headers.join(','), ...rows].join('\n')
}
