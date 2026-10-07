import { useState } from 'react'
import { api } from '../api.js'
import { Highlighted } from '../Highlighted.jsx'
import { ASPECT_NAMES, decimal, label } from '../format.js'

const REVIEW_THRESHOLD = 0.4

const MODEL_NAMES = { tfidf_logistic_regression: 'TF-IDF + logistic regression', lexicon: 'keyword rules' }

// "sentiment:…+aspect:tfidf_logistic_regression" -> "TF-IDF + logistic regression"
function themeModel(version) {
  const part = version.split('+').find((item) => item.startsWith('aspect:'))
  const name = part ? part.slice('aspect:'.length) : version
  return MODEL_NAMES[name] || name.replaceAll('_', ' ')
}

function timeLabel(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' })
}

function Correction({ analysis }) {
  const [open, setOpen] = useState(false)
  const [choice, setChoice] = useState(analysis.predictions.aspect?.label || 'other')
  const [state, setState] = useState('idle')
  if (state === 'saved') return <p className="quiet small">Thanks. Your correction was saved for evaluation.</p>
  if (!open)
    return (
      <button type="button" className="link-button" onClick={() => setOpen(true)}>
        Suggest a different theme
      </button>
    )
  async function save(event) {
    event.preventDefault()
    setState('saving')
    try {
      await api.feedback({ analysis_id: analysis.id, task: 'aspect', corrected_label: choice })
      setState('saved')
    } catch {
      setState('error')
    }
  }
  return (
    <form className="correction" onSubmit={save}>
      <label htmlFor={`fix-${analysis.id}`}>Correct theme</label>
      <select id={`fix-${analysis.id}`} value={choice} onChange={(event) => setChoice(event.target.value)}>
        {Object.keys(ASPECT_NAMES).map((key) => (
          <option key={key} value={key}>
            {label(key)}
          </option>
        ))}
      </select>
      <button type="submit" className="button ghost compact" disabled={state === 'saving'}>
        {state === 'saving' ? 'Saving…' : 'Save correction'}
      </button>
      {state === 'error' && (
        <span className="error-text" role="alert">
          Could not save. Try again.
        </span>
      )}
    </form>
  )
}

function LiveResult({ analysis }) {
  const aspect = analysis.predictions.aspect
  const fromModel = aspect?.method === 'model'
  const needsReview = fromModel && aspect.confidence < REVIEW_THRESHOLD
  const others = ['sentiment', 'intent', 'urgency'].filter((task) => analysis.predictions[task])
  return (
    <article className="live-result" aria-label={`Live result: ${label(aspect?.label)}`}>
      <div className="live-result-head">
        <span className="tag-live">Live</span>
        <span className="quiet small num">
          {timeLabel(analysis.created_at)}, theme model: {themeModel(analysis.model_version)}
        </span>
      </div>
      <div className="live-theme">
        <h3>{label(aspect?.label)}</h3>
        <span className="num quiet">{Math.round((aspect?.confidence || 0) * 100)}% confident</span>
        {needsReview && <span className="tag-review">Needs review</span>}
      </div>
      {needsReview && (
        <p className="quiet small">Below the {REVIEW_THRESHOLD.toFixed(2)} confidence threshold, so a person would check this label.</p>
      )}
      <p className="live-text">
        <Highlighted text={analysis.text} terms={aspect?.terms || []} motion="replay" tidy={false} />
      </p>
      {fromModel && aspect.terms?.length > 0 ? (
        <div className="terms">
          <span className="quiet">Words behind the label</span>
          {aspect.terms.map(([term, score]) => (
            <span key={term} className="term num">
              {term} <span className="plus">+{decimal(score)}</span>
            </span>
          ))}
        </div>
      ) : (
        <p className="quiet small">
          {fromModel ? 'No single word stood out for this label.' : 'Labelled by a keyword rule; no model weights to show.'}
        </p>
      )}
      <dl className="other-labels">
        {others.map((task) => {
          const prediction = analysis.predictions[task]
          return (
            <div key={task}>
              <dt>{label(task)}</dt>
              <dd>
                {label(prediction.label)}{' '}
                <span className="quiet small">{prediction.method === 'lexicon' ? '(keyword rule)' : `(model, ${Math.round(prediction.confidence * 100)}%)`}</span>
              </dd>
            </div>
          )
        })}
      </dl>
      <Correction analysis={analysis} />
    </article>
  )
}

export function Live({ status }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [results, setResults] = useState([])
  const ready = status.state === 'ready'

  async function submit(event) {
    event.preventDefault()
    if (!ready || text.trim().length < 3) return
    setBusy(true)
    setError('')
    try {
      const analysis = await api.analyze({ text: text.trim(), source: 'review' })
      setResults((current) => [analysis, ...current])
      setText('')
    } catch (requestError) {
      setError(requestError.message || 'The request failed.')
    } finally {
      setBusy(false)
    }
  }

  let note
  if (status.state === 'ready') note = <p className="small quiet">Ready. Results appear below, newest first.</p>
  else if (status.state === 'unavailable')
    note = (
      <p className="small error-text" role="alert">
        The live model did not respond.{' '}
        <button type="button" className="link-button" onClick={status.retry}>
          Try again
        </button>
      </p>
    )
  else
    note = (
      <div>
        <p className="small">Waking the live model. This usually takes under a minute.</p>
        <div className="waking-bar" aria-hidden="true">
          <i />
        </div>
      </div>
    )

  return (
    <section id="live" className="wrap live" aria-labelledby="live-title">
      <div className="reveal">
        <span className="tag-live">Live</span>
        <h2 id="live-title" className="heading">
          Try it on your own words
        </h2>
        <p>
          Live results run on the hosted model and appear here with the model version and time. The example above never
          changes.
        </p>
      </div>
      <div>
        <form className="panel live-form" onSubmit={submit} aria-label="Analyze text">
          <label htmlFor="live-text">Customer feedback</label>
          <textarea
            id="live-text"
            rows="5"
            minLength={3}
            maxLength={10000}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="For example: I was charged a late fee even though my payment posted on time."
          />
          <div className="live-actions">
            <button type="submit" className="button primary" disabled={!ready || busy || text.trim().length < 3}>
              {busy ? 'Analyzing…' : 'Analyze'}
            </button>
            <div className="live-note">{note}</div>
          </div>
          {error && (
            <p className="error-text small" role="alert">
              {error}
            </p>
          )}
        </form>
        <div className="live-results" aria-live="polite">
          {results.map((analysis) => (
            <LiveResult key={analysis.id} analysis={analysis} />
          ))}
        </div>
      </div>
    </section>
  )
}
