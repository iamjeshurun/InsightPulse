// Split text into plain and highlighted runs for the terms that drove a label.
// Matching is case-insensitive on word boundaries; longer terms win, so
// "my credit" is highlighted as one run rather than as "credit" alone.
export function segments(text, terms = []) {
  const words = [...new Set(terms.map(([term]) => term.toLowerCase()))].sort((a, b) => b.length - a.length)
  if (!text || !words.length) return [{ text: text || '', hit: false, order: 0 }]
  const escaped = words.map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+'))
  const pattern = new RegExp(`(?<![\\p{L}\\p{N}])(${escaped.join('|')})(?![\\p{L}\\p{N}])`, 'giu')
  const out = []
  let position = 0
  let order = 0
  for (const match of text.matchAll(pattern)) {
    if (match.index > position) out.push({ text: text.slice(position, match.index), hit: false, order: 0 })
    out.push({ text: match[0], hit: true, order: order++ })
    position = match.index + match[0].length
  }
  if (position < text.length) out.push({ text: text.slice(position), hit: false, order: 0 })
  return out
}

// CFPB masks personal details as XXXX and our own redaction adds tags like
// [CUSTOMER_ID]; show both as one readable placeholder.
export function tidyExcerpt(text) {
  return text
    .replace(/\{\$([\d,.]+)\}/g, '$$$1')
    .replace(/(?:X{2,}[ /-]*)+/g, '[redacted] ')
    .replace(/\[(?:EMAIL|PHONE|CUSTOMER_ID|SSN|CARD|ACCOUNT)\]/g, '[redacted]')
}

export const hasRedactionTag = (text) => /\[(?:EMAIL|PHONE|CUSTOMER_ID|SSN|CARD|ACCOUNT)\]/.test(text)
