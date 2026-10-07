import { segments, tidyExcerpt } from './highlight.js'

// Renders text with the label's driving words marked. `motion` chooses how the
// marks appear: "scroll" (they fill in as the passage scrolls into view),
// "replay" (they fill in one after another now) or "none".
export function Highlighted({ text, terms, motion = 'none', tidy = true }) {
  const runs = segments(tidy ? tidyExcerpt(text) : text, terms)
  return runs.map((run, index) => {
    if (!run.hit) return <span key={index}>{run.text}</span>
    const style =
      motion === 'scroll'
        ? { animationRange: `entry ${60 + run.order * 10}% cover ${40 + run.order * 6}%` }
        : motion === 'replay'
          ? { animationDelay: `${120 + run.order * 160}ms` }
          : undefined
    return (
      <mark key={index} className={`mark ${motion}`} style={style}>
        {run.text}
      </mark>
    )
  })
}
