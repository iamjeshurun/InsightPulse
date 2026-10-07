import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api.js'

// The hosted API sleeps when idle and can take about a minute to wake. Poll
// /health until it answers, report "waking" while we wait, and stop after a few
// minutes so a visitor can retry by hand.
const RETRY_MS = 4000
const GIVE_UP_MS = 3 * 60 * 1000

export function useApiStatus() {
  const [status, setStatus] = useState({ state: 'checking', health: null })
  const [attempt, setAttempt] = useState(0)
  const cancelled = useRef(false)

  useEffect(() => {
    cancelled.current = false
    let timer
    const started = Date.now()
    const slow = setTimeout(() => {
      if (!cancelled.current) setStatus((current) => (current.state === 'checking' ? { ...current, state: 'waking' } : current))
    }, 1500)

    async function poll() {
      try {
        const health = await api.health()
        if (!cancelled.current) setStatus({ state: 'ready', health })
      } catch {
        if (cancelled.current) return
        if (Date.now() - started > GIVE_UP_MS) {
          setStatus({ state: 'unavailable', health: null })
          return
        }
        setStatus((current) => ({ ...current, state: 'waking' }))
        timer = setTimeout(poll, RETRY_MS)
      }
    }
    poll()
    return () => {
      cancelled.current = true
      clearTimeout(timer)
      clearTimeout(slow)
    }
  }, [attempt])

  const retry = useCallback(() => {
    setStatus({ state: 'checking', health: null })
    setAttempt((n) => n + 1)
  }, [])

  return { ...status, retry }
}
