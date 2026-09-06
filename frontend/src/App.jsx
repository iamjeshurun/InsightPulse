import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './api.js'
import { parseCsv, toAnalysisCsv } from './csv.js'

const EMPTY_SUMMARY = { total: 0, average_confidence: 0, sentiment: {}, intent: {}, urgency: {}, aspect: {}, products: {}, by_day: {}, low_confidence: 0 }
const pretty = (value) => value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
const confidence = (analysis) => Math.min(...Object.values(analysis.predictions).map((item) => item.confidence))

function StatCard({ label, value, detail, tone = 'ink' }) {
  return <article className={`stat-card ${tone}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>
}

function Distribution({ title, values, colors }) {
  const maximum = Math.max(...Object.values(values), 1)
  return <section className="panel distribution">
    <div className="panel-heading"><div><span className="eyebrow">Distribution</span><h2>{title}</h2></div></div>
    <div className="bars">{Object.entries(values).sort((a, b) => b[1] - a[1]).map(([label, count], index) =>
      <div className="bar-row" key={label}>
        <span>{pretty(label)}</span><div className="bar-track"><i style={{ width: `${(count / maximum) * 100}%`, background: colors[index % colors.length] }} /></div><b>{count}</b>
      </div>)}</div>
  </section>
}

function AnalyzeForm({ onComplete }) {
  const [form, setForm] = useState({ text: '', product: 'InsightPulse', source: 'review' })
  const [state, setState] = useState({ loading: false, error: '' })
  async function submit(event) {
    event.preventDefault(); setState({ loading: true, error: '' })
    try { await api.analyze(form); setForm({ ...form, text: '' }); await onComplete() }
    catch (error) { setState({ loading: false, error: error.message }); return }
    setState({ loading: false, error: '' })
  }
  return <section className="panel analyze-panel">
    <div className="panel-heading"><div><span className="eyebrow">Live inference</span><h2>Analyze feedback</h2></div><span className="model-pill">API v1</span></div>
    <form onSubmit={submit}>
      <textarea aria-label="Customer feedback" placeholder="Paste a review, survey response, or support ticket…" value={form.text} onChange={(event) => setForm({ ...form, text: event.target.value })} minLength="3" required />
      <div className="form-row"><input aria-label="Product" value={form.product} onChange={(event) => setForm({ ...form, product: event.target.value })} required />
        <select aria-label="Source" value={form.source} onChange={(event) => setForm({ ...form, source: event.target.value })}><option value="review">Review</option><option value="survey">Survey</option><option value="support_ticket">Support ticket</option></select>
        <button disabled={state.loading}>{state.loading ? 'Analyzing…' : 'Analyze text'}</button></div>
      {state.error && <p className="error">{state.error}</p>}
    </form>
  </section>
}

function CsvUpload({ onComplete }) {
  const [message, setMessage] = useState('CSV columns: text, product, source')
  async function upload(event) {
    const file = event.target.files?.[0]; if (!file) return
    try {
      const rows = parseCsv(await file.text())
      if (rows.length > 100) throw new Error('Upload a maximum of 100 records at a time')
      await api.batch(rows.map((row) => ({ text: row.text, product: row.product || 'Unknown', source: row.source || 'review' })))
      setMessage(`${rows.length} records analyzed successfully`); await onComplete()
    } catch (error) { setMessage(error.message) }
    event.target.value = ''
  }
  return <label className="upload"><span>Batch import</span><strong>Drop in customer feedback</strong><small>{message}</small><input type="file" accept=".csv,text/csv" onChange={upload} /></label>
}

function ReviewTable({ analyses, onFeedback }) {
  const [filter, setFilter] = useState('all')
  const visible = analyses.filter((item) => filter === 'all' || item.predictions.sentiment.label === filter || item.predictions.urgency.label === filter)
  return <section className="panel table-panel">
    <div className="panel-heading"><div><span className="eyebrow">Evidence</span><h2>Recent feedback</h2></div><select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="all">All signals</option><option value="negative">Negative</option><option value="positive">Positive</option><option value="high">High urgency</option></select></div>
    <div className="table-scroll"><table><thead><tr><th>Feedback</th><th>Product</th><th>Sentiment</th><th>Aspect</th><th>Intent</th><th>Confidence</th><th /></tr></thead>
      <tbody>{visible.map((item) => <tr key={item.id}><td><p>{item.text}</p><small>{new Date(item.created_at).toLocaleString()}</small></td><td>{item.product}</td><td><span className={`tag ${item.predictions.sentiment.label}`}>{pretty(item.predictions.sentiment.label)}</span></td><td>{pretty(item.predictions.aspect?.label || 'other')}</td><td>{pretty(item.predictions.intent.label)}</td><td>{Math.round(confidence(item) * 100)}%</td><td><button className="text-button" onClick={() => onFeedback(item)}>Correct</button></td></tr>)}</tbody></table></div>
    {!visible.length && <div className="empty">No feedback matches this filter.</div>}
  </section>
}

function FeedbackDialog({ analysis, onClose }) {
  const [task, setTask] = useState('sentiment'), [label, setLabel] = useState('neutral'), [saving, setSaving] = useState(false)
  if (!analysis) return null
  async function save() { setSaving(true); await api.feedback({ analysis_id: analysis.id, task, corrected_label: label }); setSaving(false); onClose() }
  return <div className="modal-backdrop" role="presentation"><div className="modal" role="dialog" aria-modal="true" aria-label="Correct prediction"><span className="eyebrow">Human feedback</span><h2>Correct this prediction</h2><p>{analysis.text}</p><label>Task<select value={task} onChange={(event) => setTask(event.target.value)}><option>sentiment</option><option>aspect</option><option>intent</option><option>urgency</option></select></label><label>Correct label<input value={label} onChange={(event) => setLabel(event.target.value)} /></label><div className="modal-actions"><button className="secondary" onClick={onClose}>Cancel</button><button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save correction'}</button></div></div></div>
}

export default function App() {
  const [summary, setSummary] = useState(EMPTY_SUMMARY), [analyses, setAnalyses] = useState([]), [health, setHealth] = useState(null)
  const [error, setError] = useState(''), [reviewing, setReviewing] = useState(null)
  const refresh = useCallback(async () => {
    try { const [nextSummary, nextAnalyses, nextHealth] = await Promise.all([api.summary(), api.analyses(), api.health()]); setSummary(nextSummary); setAnalyses(nextAnalyses); setHealth(nextHealth); setError('') }
    catch (requestError) { setError(requestError.message) }
  }, [])
  useEffect(() => { refresh() }, [refresh])
  const negativeRate = summary.total ? Math.round(((summary.sentiment.negative || 0) / summary.total) * 100) : 0
  const lowConfidence = useMemo(() => analyses.filter((item) => confidence(item) < 0.65), [analyses])
  function exportCsv() { const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([toAnalysisCsv(analyses)], { type: 'text/csv' })); link.download = 'insightpulse-analysis.csv'; link.click(); URL.revokeObjectURL(link.href) }
  return <div className="app-shell">
    <aside><a className="brand" href="#top"><span>IP</span><div>InsightPulse<small>Customer intelligence</small></div></a><nav><a className="active" href="#overview">Overview</a><a href="#analyze">Analyze</a><a href="#feedback">Feedback</a><a href="#review">Review queue <b>{lowConfidence.length}</b></a></nav><div className="sidebar-status"><i className={health ? 'online' : ''} /><div><strong>{health ? 'System operational' : 'API unavailable'}</strong><small>{health?.model_version || 'Waiting for service'}</small></div></div></aside>
    <main id="top"><header><div><span className="eyebrow">Voice of customer</span><h1>Signals worth acting on.</h1><p>See what customers feel, need, and may do next.</p></div><button className="secondary" onClick={exportCsv} disabled={!analyses.length}>Export CSV</button></header>
      {error && <div className="error-banner">Could not reach the API: {error}</div>}
      <section id="overview" className="stats"><StatCard label="Feedback analyzed" value={summary.total.toLocaleString()} detail="Across all connected sources" tone="violet" /><StatCard label="Negative sentiment" value={`${negativeRate}%`} detail={`${summary.sentiment.negative || 0} records need attention`} tone="coral" /><StatCard label="Model confidence" value={`${Math.round(summary.average_confidence * 100)}%`} detail="Mean across three tasks" tone="mint" /><StatCard label="Review queue" value={summary.low_confidence} detail="Below 65% confidence" tone="gold" /></section>
      <section className="grid-two"><Distribution title="Customer sentiment" values={summary.sentiment} colors={['#ff6b57', '#725cff', '#38b98b']} /><Distribution title="Customer aspects" values={summary.aspect} colors={['#725cff', '#4d8df7', '#f3a83b', '#38b98b']} /></section>
      <section id="analyze" className="grid-action"><AnalyzeForm onComplete={refresh} /><CsvUpload onComplete={refresh} /></section>
      <div id="feedback"><ReviewTable analyses={analyses} onFeedback={setReviewing} /></div>
      <section id="review" className="review-callout"><div><span className="eyebrow">Review queue</span><h2>{lowConfidence.length} predictions need a human look</h2><p>Corrections are stored as labeled feedback for continuous evaluation and future retraining.</p></div><button onClick={() => document.querySelector('.table-panel')?.scrollIntoView({ behavior: 'smooth' })}>Review evidence</button></section>
      <footer>InsightPulse · Local-first customer intelligence · API {health?.api_version || '—'}</footer>
    </main><FeedbackDialog analysis={reviewing} onClose={() => setReviewing(null)} />
  </div>
}
