import test from 'node:test'
import assert from 'node:assert/strict'
import { parseCsv, toAnalysisCsv } from './csv.js'

test('parses quoted CSV fields', () => {
  const result = parseCsv('text,product,source\n"Fast, clear UI",Core,review\nBroken export,Exports,support_ticket')
  assert.equal(result.length, 2)
  assert.equal(result[0].text, 'Fast, clear UI')
})

test('requires a text column', () => {
  assert.throws(() => parseCsv('message\nhello'), /text column/)
})

test('exports predictions safely', () => {
  const csv = toAnalysisCsv([{ id: '1', created_at: '2026-01-01', product: 'Core', source: 'review', text: 'Great', predictions: { sentiment: { label: 'positive' }, intent: { label: 'praise' }, urgency: { label: 'low' } } }])
  assert.match(csv, /positive/)
})
