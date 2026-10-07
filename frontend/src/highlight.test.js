import assert from 'node:assert/strict'
import { test } from 'node:test'
import { segments } from './highlight.js'

const hits = (runs) => runs.filter((run) => run.hit).map((run) => run.text)

test('highlights whole words only, case-insensitively', () => {
  const runs = segments('A fee, then FEES and a coffee.', [['fee', 0.7]])
  assert.deepEqual(hits(runs), ['fee'])
  assert.equal(runs.map((run) => run.text).join(''), 'A fee, then FEES and a coffee.')
})

test('prefers the longer term and numbers hits in reading order', () => {
  const runs = segments('Remove it from my credit report. Credit matters.', [['credit', 0.2], ['my credit', 0.4], ['report', 0.3]])
  assert.deepEqual(hits(runs), ['my credit', 'report', 'Credit'])
  assert.deepEqual(runs.filter((run) => run.hit).map((run) => run.order), [0, 1, 2])
})

test('returns the text untouched when there are no terms', () => {
  assert.deepEqual(segments('Nothing to see', []), [{ text: 'Nothing to see', hit: false, order: 0 }])
})

test('redaction marks read as one placeholder', async () => {
  const { tidyExcerpt, hasRedactionTag } = await import('./highlight.js')
  assert.equal(tidyExcerpt('Paid {$820.00} to XXXX XXXX, call [PHONE].'), 'Paid $820.00 to [redacted] , call [redacted].')
  assert.equal(hasRedactionTag('Called their [CUSTOMER_ID] today'), true)
  assert.equal(hasRedactionTag('No tags here'), false)
})
