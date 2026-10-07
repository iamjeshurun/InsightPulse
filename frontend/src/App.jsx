import { useEffect, useState } from 'react'
import { Disagreements } from './sections/Disagreements.jsx'
import { Results, Statement, ThemeExplorer } from './sections/Evidence.jsx'
import { Closing, Footer, HowItWorks } from './sections/Bottom.jsx'
import { Live } from './sections/Live.jsx'
import { Header, Hero, Stream } from './sections/Top.jsx'
import { useApiStatus } from './useApiStatus.js'

// The example is precomputed (scripts/build_case_study.py) and served as a
// static file, so the page never waits for the API.
function useExample() {
  const [state, setState] = useState({ example: null, error: '' })
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}example-insights.json`)
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`))))
      .then((example) => setState({ example, error: '' }))
      .catch((error) => setState({ example: null, error: error.message }))
  }, [])
  return state
}

export default function App() {
  const status = useApiStatus()
  const { example, error } = useExample()
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Header status={status} />
      <main id="main">
        <Hero />
        {error && (
          <p className="wrap error-text" role="alert">
            The example analysis could not be loaded ({error}). Live analysis below still works once the model is ready.
          </p>
        )}
        {example ? (
          <>
            <Stream example={example} />
            <Results example={example} />
            <Statement example={example} />
            <ThemeExplorer example={example} />
            <Disagreements example={example} />
          </>
        ) : (
          !error && (
            <p className="wrap quiet loading" aria-busy="true">
              Loading the example…
            </p>
          )
        )}
        <Live status={status} />
        {example && <HowItWorks example={example} />}
        <Closing />
      </main>
      <Footer />
    </>
  )
}
