import { useState } from 'react'
import { hasRedactionTag } from '../highlight.js'
import { Highlighted } from '../Highlighted.jsx'
import { decimal, label, longDate, percent } from '../format.js'

export function Results({ example }) {
  const result = example.results['2024_case']
  const baseline = example.results['2019_test']
  const review = example.review.case_2024
  const whole = Math.floor(result.accuracy * 100)
  const tenth = Math.round(result.accuracy * 1000) % 10
  return (
    <section className="wrap results" aria-label="Key results">
      <div className="result reveal">
        <i className="rule draw" aria-hidden="true" />
        <p className="figure num" aria-label={percent(result.accuracy, 1)}>
          <span className="count" style={{ '--to': whole }} aria-hidden="true" />
          <span aria-hidden="true">.{tenth}%</span>
        </p>
        <p className="figure-note">
          agreement with CFPB's own categories on {result.n.toLocaleString()} complaints.{' '}
          <span className="quiet">A constant guess gets {percent(result.majority_baseline, 1)}.</span>
        </p>
      </div>
      <div className="result reveal">
        <i className="rule draw" aria-hidden="true" />
        <p className="figure num" aria-label={decimal(baseline.macro_f1)}>
          <span aria-hidden="true">0.</span>
          <span className="count" style={{ '--to': Math.round(baseline.macro_f1 * 100) }} aria-hidden="true" />
        </p>
        <p className="figure-note">
          macro-F1 for the TF-IDF baseline, ahead of {example.transformers_2019.models_tried} fine-tuned transformers{' '}
          <span className="quiet">(best of them: {decimal(example.transformers_2019.best_macro_f1)}).</span>
        </p>
      </div>
      <div className="result reveal">
        <i className="rule draw" aria-hidden="true" />
        <p className="figure num" aria-label={percent(review.errors_caught_share)}>
          <span className="count" style={{ '--to': Math.round(review.errors_caught_share * 100) }} aria-hidden="true" />
          <span aria-hidden="true">%</span>
        </p>
        <p className="figure-note">
          of disagreements caught by reviewing the least-confident <strong>{percent(review.flagged_share)}</strong> of
          labels.
        </p>
      </div>
    </section>
  )
}

export function Statement({ example }) {
  const result = example.results['2024_case']
  const words = `We trained the model on complaints from January 2019, then ran it on ${result.n.toLocaleString()} complaints filed five years later. It matched CFPB’s own categories ${percent(result.accuracy, 1)} of the time. Where it didn’t, the reasons are worth reading.`.split(' ')
  return (
    <section className="wrap statement" aria-label="Summary">
      <p>
        {words.map((word, index) => (
          <span key={index} className="word">
            {word}{' '}
          </span>
        ))}
      </p>
    </section>
  )
}

// Prefer a complaint long enough to read whose text was not cut up by redaction.
function readableEvidence(items) {
  return (
    items.find((item) => item.excerpt.length >= 120 && !hasRedactionTag(item.excerpt)) ||
    items.find((item) => item.excerpt.length >= 120) ||
    items[0]
  )
}

export function ThemeExplorer({ example }) {
  const result = example.results['2024_case']
  const themes = Object.entries(result.per_class)
    .map(([id, value]) => ({ id, ...value }))
    .sort((a, b) => b.n - a.n)
  const [selected, setSelected] = useState('fraud_security')
  const [replays, setReplays] = useState(0)
  const theme = themes.find((item) => item.id === selected) || themes[0]
  const correct = result.confusion[theme.id][theme.id]
  const [confusedAs, confusedN] = Object.entries(result.confusion[theme.id])
    .filter(([other]) => other !== theme.id)
    .sort((a, b) => b[1] - a[1])[0]
  const evidence = readableEvidence(example.evidence[theme.id] || [])

  function pick(id) {
    setSelected(id)
    setReplays((n) => n + 1)
  }

  return (
    <section id="themes" className="wrap" aria-labelledby="themes-title">
      <div className="section-intro reveal">
        <h2 id="themes-title" className="heading">
          Every theme, with its evidence
        </h2>
        <p>
          Pick a theme. The words that drove the label light up, with their weights from the model. This is example
          data: archived CFPB complaints from {longDate(example.dataset.date_range[0])} to{' '}
          {longDate(example.dataset.date_range[1])}.
        </p>
      </div>

      <div className="panel tilt">
        <div className="panel-head">
          <strong>Complaint themes</strong>
          <span className="quiet">Example data, scored by the bundled theme model</span>
        </div>
        <div className="explorer">
          <div className="theme-list" role="group" aria-label="Themes">
            {themes.map((item) => {
              const active = item.id === theme.id
              const found = Math.round((result.confusion[item.id][item.id] / item.n) * 100)
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`theme-row${active ? ' active' : ''}`}
                  aria-pressed={active}
                  onClick={() => pick(item.id)}
                >
                  <span className="theme-name">
                    <span>{label(item.id)}</span>
                    <span className="num quiet">{item.n.toLocaleString()}</span>
                  </span>
                  <span className="theme-bar">
                    <span className="track">
                      <i className="grow" style={{ width: `${found}%` }} />
                    </span>
                    <span className="num">{found}%</span>
                  </span>
                  <span className={`theme-f1 num${item.f1 < 0.4 ? ' quiet' : ''}`}>{decimal(item.f1)}</span>
                </button>
              )
            })}
            <p className="list-note">Bar: share of CFPB's complaints the model found. Right: F1.</p>
          </div>

          <div className="theme-detail">
            <div className="detail-head">
              <h3>{label(theme.id)}</h3>
              <span className="num quiet">F1 {decimal(theme.f1)}</span>
            </div>
            <p className="detail-summary">
              Found{' '}
              <strong>
                {correct.toLocaleString()} of {theme.n.toLocaleString()}
              </strong>{' '}
              complaints CFPB filed here. Misses most often go to <strong>{label(confusedAs)}</strong> ({confusedN}).
            </p>
            {evidence && (
              <figure className="quote" key={`${theme.id}-${replays}`}>
                <blockquote>
                  <Highlighted text={evidence.excerpt} terms={evidence.terms} motion={replays ? 'replay' : 'scroll'} />
                </blockquote>
                <figcaption>
                  <span className="quiet">CFPB filed it as</span>
                  <span>{label(evidence.cfpb_label)}</span>
                  <span className="quiet">The model said</span>
                  <span>
                    {label(evidence.model_label)}{' '}
                    <span className="num quiet">({Math.round(evidence.confidence * 100)}% confident)</span>
                  </span>
                  <span className="quiet">Source</span>
                  <span className="num quiet">
                    Complaint {evidence.id}, filed {longDate(evidence.date)}
                  </span>
                </figcaption>
              </figure>
            )}
            {evidence && evidence.terms.length > 0 && (
              <div className="terms">
                <span className="quiet">Words behind the label</span>
                {evidence.terms.map(([term, score]) => (
                  <span key={term} className="term num">
                    {term} <span className="plus">+{decimal(score)}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
