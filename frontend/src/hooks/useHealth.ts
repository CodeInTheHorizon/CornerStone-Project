/** Loads backend health once on mount and exposes a manual retry. */

import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchHealth } from '@/services/systemService'
import type { HealthResponse } from '@/types/api'

type Status = 'loading' | 'ready' | 'error'

export function useHealth() {
  const [data, setData] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Starts as 'loading' so the mount effect never has to set state synchronously.
  const [status, setStatus] = useState<Status>('loading')
  const mounted = useRef(true)

  const runFetch = useCallback(async () => {
    try {
      const health = await fetchHealth()
      if (!mounted.current) return
      setData(health)
      setStatus('ready')
    } catch (err) {
      if (!mounted.current) return
      setData(null)
      setError(err instanceof Error ? err.message : 'Unknown error.')
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    // runFetch only sets state after awaiting the request, so no state is
    // set synchronously here; the rule cannot see across the async boundary.
    // oxlint-disable-next-line react/set-state-in-effect
    void runFetch()
    return () => {
      mounted.current = false
    }
  }, [runFetch])

  const reload = useCallback(() => {
    setStatus('loading')
    setError(null)
    void runFetch()
  }, [runFetch])

  return { data, error, status, reload }
}
