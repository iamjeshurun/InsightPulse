import { hasRedactionTag } from '../highlight.js'
import { Highlighted } from '../Highlighted.jsx'
import { label } from '../format.js'

export const REPO_URL = 'https://github.com/iamjeshurun/InsightPulse'
export const EVALUATION_URL = `${REPO_URL}/blob/main/docs/case-study-2024.md`

const STATUS_SHORT = { checking: 'Checking', waking: 'Waking up', ready: 'Ready', unavailable: 'Offline' }

const STATUS_TEXT = {
  checking: 'Checking the live model',
  waking: 'Live model waking up',
  ready: 'Live model ready',
  unavailable: 'Live model unavailable',
}

export function Header({ status }) {
  return (
    <header className="site-header">
      <div className="wrap header-row">
        <a className="wordmark" href="#top">
          InsightPulse
        </a>
        <nav aria-label="Sections" className="nav-links">
          <a href="#themes">Example</a>
          <a href="#disagree">Disagreements</a>
          <a href="#live">Try it live</a>
          <a href="#how">How it works</a>
        </nav>
        <div className="header-actions">
          <span className={`status ${status.state}`} role="status" aria-live="polite">
            <i aria-hidden="true" />
            <span className="long">{STATUS_TEXT[status.state]}</span>
            <span className="short" aria-hidden="true">
              {STATUS_SHORT[status.state]}
            </span>
          </span>
          <a className="button ghost compact" href={REPO_URL} aria-label="View source on GitHub">
            <span className="long">View source</span>
            <span className="short">Source</span>
          </a>
        </div>
      </div>
    </header>
  )
}

export function Hero() {
  return (
    <section id="top" className="wrap hero" aria-labelledby="hero-title">
      <p className="kicker fade-up">Voice-of-customer analytics, open source</p>
      <h1 id="hero-title" className="display">
        <span className="line">
          <span style={{ animationDelay: '80ms' }}>Know what customers</span>
        </span>
        <span className="line">
          <span style={{ animationDelay: '200ms' }}>complain about.</span>
        </span>
        <span className="line muted-line">
          <span style={{ animationDelay: '320ms' }}>
            And <span className="why">why</span> the model
          </span>
        </span>
        <span className="line muted-line">
          <span style={{ animationDelay: '440ms' }}>thinks so.</span>
        </span>
      </h1>
      <div className="hero-row fade-up" style={{ animationDelay: '700ms' }}>
        <p className="lede">
          InsightPulse sorts customer feedback into themes, shows the words behind every label, and hands the uncertain
          ones to a person.
        </p>
        <div className="actions">
          <a className="button primary" href="#live">
            Analyze your own text
          </a>
          <a className="button ghost" href="#themes">
            Explore the example
          </a>
        </div>
      </div>
    </section>
  )
}

export function Stream({ example }) {
  // Two agreed examples per theme, long enough to read, labelled by the model.
  const cards = Object.values(example.evidence)
    .flat()
    .filter((record) => record.excerpt.length > 120 && !hasRedactionTag(record.excerpt))
  const loop = [...cards, ...cards]
  return (
    <section className="stream fade-up" style={{ animationDelay: '900ms' }} aria-label="Complaints sorted by the model">
      <p className="wrap stream-note">
        A replay of archived CFPB complaints from January 2024, labelled by the bundled model.
      </p>
      <div className="marquee">
        {loop.map((record, index) => (
          <article key={`${record.id}-${index}`} className="stream-card" aria-hidden={index >= cards.length}>
            <div className="stream-head">
              <span>{label(record.model_label)}</span>
              <span className="num quiet">{Math.round(record.confidence * 100)}% confident</span>
            </div>
            <p>
              <Highlighted text={record.excerpt} terms={record.terms} />
            </p>
          </article>
        ))}
      </div>
    </section>
  )
}
