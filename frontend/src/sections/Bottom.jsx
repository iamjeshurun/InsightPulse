import { percent } from '../format.js'
import { EVALUATION_URL, REPO_URL } from './Top.jsx'

const spelled = (n) => ['Zero', 'One', 'Two', 'Three', 'Four', 'Five'][n] || String(n)

export function HowItWorks({ example }) {
  const review = example.review.case_2024
  const steps = [
    [
      'Data',
      `Public complaint narratives from CFPB’s archive, with personal details redacted and duplicates removed. ${example.dataset.examples.toLocaleString()} from January 1 to 4, 2024 make up the example.`,
    ],
    [
      'Model',
      `TF-IDF features and logistic regression, one classifier per task. ${spelled(example.transformers_2019.models_tried)} fine-tuned transformers were tried and scored lower.`,
    ],
    ['Service', 'A FastAPI service with rate limiting, Prometheus metrics and drift checks, plus this dashboard and a public API.'],
    [
      'Review',
      `Labels under ${example.review.case_2024.threshold.toFixed(2)} confidence go to a person. On the example, reviewing ${percent(review.flagged_share)} of labels catches ${percent(review.errors_caught_share)} of the disagreements.`,
    ],
  ]
  return (
    <section id="how" className="how" aria-labelledby="how-title">
      <div className="pin">
        <div className="wrap">
          <h2 id="how-title" className="heading">
            How it works
          </h2>
          <div className="steps-rail">
            <div className="rail" aria-hidden="true">
              <i className="progress" />
            </div>
            <ol className="steps">
              {steps.map(([title], index) => (
                <li key={title}>
                  <span className="node num" style={{ animationRange: `contain ${index * 25}% contain ${index * 25 + 6}%` }}>
                    {index + 1}
                  </span>
                  <span className="step-title">{title}</span>
                </li>
              ))}
            </ol>
          </div>
          <div className="step-copy">
            {steps.map(([title, copy], index) => (
              <p
                key={title}
                className={`desc${index === steps.length - 1 ? ' last' : ''}`}
                style={{ animationRange: `contain ${index * 25}% contain ${(index + 1) * 25}%` }}
              >
                <strong className="step-copy-title">{title}. </strong>
                {copy}
              </p>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

export function Closing() {
  return (
    <section className="wrap closing" aria-label="Get the code">
      <p className="closing-title reveal">
        Read the <span className="marker">code</span>.
      </p>
      <div className="actions centered reveal">
        <a className="button primary large" href={REPO_URL}>
          View on GitHub
        </a>
        <a className="button ghost large" href={EVALUATION_URL}>
          Read the full evaluation
        </a>
      </div>
    </section>
  )
}

export function Footer() {
  return (
    <footer className="site-footer">
      <p className="wrap">
        The example is a case study on archived data, not a held-out test. Complaints are unverified, one-sided accounts,
        and CFPB's categories are reference labels. Sentiment and trends are not shown for this data.{' '}
        <a href={EVALUATION_URL}>Full evaluation</a>.
      </p>
    </footer>
  )
}
