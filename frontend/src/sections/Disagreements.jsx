import { useCallback, useEffect, useRef, useState } from 'react'
import { Highlighted } from '../Highlighted.jsx'
import { decimal, label, longDate } from '../format.js'

const prefersReducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
// When the browser supports scroll-driven animation (and motion is allowed) the
// section is pinned and the cards slide with the page scroll; otherwise they sit
// in a plain horizontal strip (always on phones). The buttons step through
// whichever is active.
const isPinned = () =>
  Boolean(window.CSS?.supports?.('animation-timeline: view()')) &&
  !prefersReducedMotion() &&
  window.matchMedia('(min-width: 721px)').matches

function scrollParent(element) {
  let node = element?.parentElement
  while (node && node !== document.body) {
    const overflow = getComputedStyle(node).overflowY
    if ((overflow === 'auto' || overflow === 'scroll') && node.scrollHeight > node.clientHeight) return node
    node = node.parentElement
  }
  return document.scrollingElement || document.documentElement
}

export function Disagreements({ example }) {
  const items = example.disagreements
  const sectionRef = useRef(null)
  const trackRef = useRef(null)
  const [index, setIndex] = useState(0)

  const measure = useCallback(() => {
    const section = sectionRef.current
    const track = trackRef.current
    if (!section || !track) return null
    if (isPinned()) {
      const scroller = scrollParent(section)
      const isRoot = scroller === document.scrollingElement || scroller === document.documentElement
      const viewport = isRoot ? window.innerHeight : scroller.clientHeight
      const offset = isRoot ? 0 : scroller.getBoundingClientRect().top
      const range = Math.max(section.offsetHeight - viewport, 1)
      const progress = Math.min(Math.max(-(section.getBoundingClientRect().top - offset) / range, 0), 1)
      return { pinned: true, scroller, range, progress }
    }
    const card = track.children[0]
    const step = card ? card.getBoundingClientRect().width + 24 : 524
    return { pinned: false, track, step, progress: track.scrollLeft / Math.max(track.scrollWidth - track.clientWidth, 1) }
  }, [])

  useEffect(() => {
    const update = () => {
      const state = measure()
      if (state) setIndex(Math.round(state.progress * (items.length - 1)))
    }
    window.addEventListener('scroll', update, true)
    window.addEventListener('resize', update)
    update()
    return () => {
      window.removeEventListener('scroll', update, true)
      window.removeEventListener('resize', update)
    }
  }, [items.length, measure])

  function go(delta) {
    const state = measure()
    if (!state) return
    const target = Math.min(Math.max(index + delta, 0), items.length - 1)
    const behavior = prefersReducedMotion() ? 'auto' : 'smooth'
    if (state.pinned) {
      state.scroller.scrollBy({ top: (target / (items.length - 1) - state.progress) * state.range, behavior })
    } else {
      state.track.scrollBy({ left: (target - index) * state.step, behavior })
    }
    setIndex(target)
  }

  return (
    <section id="disagree" ref={sectionRef} className="gallery" aria-labelledby="disagree-title">
      <div className="pin">
        <div className="wrap gallery-head">
          <div>
            <h2 id="disagree-title" className="heading">
              Where it disagrees
            </h2>
            <p>
              The {items.length} most confident disagreements with CFPB's categories. Several are defensible, because
              CFPB's labels are references, not ground truth. Scroll, or step through them.
            </p>
          </div>
          <div className="stepper" role="group" aria-label="Move through disagreements">
            <span className="num quiet" aria-live="polite">
              {index + 1} of {items.length}
            </span>
            <button type="button" className="round" aria-label="Previous disagreement" disabled={index === 0} onClick={() => go(-1)}>
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M12.5 4.5 7 10l5.5 5.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <button
              type="button"
              className="round"
              aria-label="Next disagreement"
              disabled={index === items.length - 1}
              onClick={() => go(1)}
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M7.5 4.5 13 10l-5.5 5.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </div>
        <div className="slide-track" ref={trackRef}>
          {items.map((item) => (
            <article key={item.id} className="dis-card">
              <dl>
                <dt>CFPB</dt>
                <dd className="struck">{label(item.cfpb_label)}</dd>
                <dt>Model</dt>
                <dd>
                  {label(item.model_label)} <span className="num quiet">{Math.round(item.confidence * 100)}%</span>
                </dd>
              </dl>
              <p>
                <Highlighted text={item.excerpt} terms={item.terms} />
              </p>
              <p className="num quiet small">
                Complaint {item.id}, filed {longDate(item.date)}. Strongest words:{' '}
                {item.terms.map(([term, score]) => `${term} +${decimal(score)}`).join(', ')}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
