import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, riskReportFromFiles } from '../lib/api'
import { API_BASE_URL } from '../lib/constants'

// Normalize error to string
const normalizeError = (e) => {
  if (!e) return null
  if (typeof e === 'string') return e
  if (e instanceof Error) return e.message
  if (e.message) return String(e.message)
  return String(e)
}

export function useApi(fn) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const abortRef = useRef(null)

  const run = useCallback(
    async (...args) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setLoading(true)
      setError(null)
      try {
        const result = await fn(...args, { signal: controller.signal })
        setData(result)
        return result
      } catch (e) {
        if (e.name === 'AbortError') return
        setError(normalizeError(e))
        throw e
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    },
    [fn]
  )

  const reset = useCallback(() => {
    setData(null)
    setError(null)
    setLoading(false)
  }, [])

  useEffect(() => () => abortRef.current?.abort(), [])

  return { data, error, loading, run, reset }
}

export const useMatchThreeWay = () => useApi(api.matchThreeWay)
export const useRiskReport = () => useApi(api.riskReport)

export function useRiskReportFromFiles() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const abortRef = useRef(null)

  const reset = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setData(null)
    setError(null)
    setLoading(false)
  }, [])

  const submit = useCallback(async (txId, files, options = {}) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    let timedOut = false
    const timeoutId = setTimeout(() => {
      timedOut = true
      controller.abort()
    }, 120_000)

    setLoading(true)
    setError(null)
    setData(null)

    try {
      const result = await riskReportFromFiles(txId, files, {
        ...options,
        signal: controller.signal,
      })
      setData(result)
      return result
    } catch (cause) {
      if (cause?.name === 'AbortError' && !timedOut) return undefined
      if (cause?.name === 'AbortError') {
        const timeoutError = new Error('Request timeout, coba lagi.')
        setError(normalizeError(timeoutError))
        throw timeoutError
      }
      const requestError = cause instanceof Error
        ? cause
        : new Error('Terjadi kesalahan saat memproses dokumen.')
      setError(normalizeError(requestError))
      throw requestError
    } finally {
      clearTimeout(timeoutId)
      if (abortRef.current === controller) {
        abortRef.current = null
        setLoading(false)
      }
    }
  }, [])

  useEffect(() => () => abortRef.current?.abort(), [])

  return { data, loading, error, submit, reset }
}

export function useMakerRecommendation() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const abortRef = useRef(null)

  const submit = useCallback(async (itemName, file) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const timeoutId = setTimeout(() => controller.abort(), 120_000)

    setLoading(true)
    setError(null)
    setData(null)

    try {
      const form = new FormData()
      form.append('item_name', itemName)
      form.append('file', file)

      let res
      try {
        res = await fetch(`${API_BASE_URL}/api/v1/procurement/items/recommend-with-file`, {
          method: 'POST',
          body: form,
          signal: controller.signal,
        })
      } catch (e) {
        if (e.name === 'AbortError') {
          setError('Request timeout, coba lagi')
          return
        }
        throw e
      }

      const text = await res.text()
      let payload = null
      if (text) {
        try { payload = JSON.parse(text) } catch { payload = text }
      }

      if (!res.ok) {
        const detail =
          (typeof payload === 'object' && (payload?.detail ?? payload?.message)) ||
          res.statusText ||
          `HTTP ${res.status}`
        setError(String(detail))
        return
      }

      setData(payload)
    } catch (e) {
      setError(normalizeError(e))
    } finally {
      clearTimeout(timeoutId)
      if (abortRef.current === controller) setLoading(false)
    }
  }, [])

  useEffect(() => () => abortRef.current?.abort(), [])

  return { data, loading, error, submit }
}

// ── Bons (Purchase Request) hooks ──────────────────────────────────────────

export function useParseBons() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const abortRef = useRef(null)

  const submit = useCallback(async (file) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const timeoutId = setTimeout(() => controller.abort(), 120_000)

    setLoading(true)
    setError(null)
    setData(null)

    try {
      const result = await api.parseBons(file, { signal: controller.signal })
      setData(result)
      return result
    } catch (cause) {
      if (cause?.name === 'AbortError') {
        const timeoutError = new Error('Request timeout, coba lagi.')
        setError(normalizeError(timeoutError))
        throw timeoutError
      }
      const requestError = cause instanceof Error
        ? cause
        : new Error('Terjadi kesalahan saat memproses dokumen.')
      setError(normalizeError(requestError))
      throw requestError
    } finally {
      clearTimeout(timeoutId)
      if (abortRef.current === controller) setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setData(null)
    setError(null)
    setLoading(false)
  }, [])

  useEffect(() => () => abortRef.current?.abort(), [])

  return { data, loading, error, submit, reset }
}

export function useListDocuments(params = {}) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const abortRef = useRef(null)
  const paramsRef = useRef(params)
  
  // Always keep latest params in ref WITHOUT triggering re-render
  paramsRef.current = params
  
  // String key — stable reference untuk useEffect
  const paramsKey = JSON.stringify(params || {})
  
  // fetchData WAJIB stable (deps []) — baca params dari ref
  const fetchData = useCallback(async () => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    
    setLoading(true)
    setError(null)
    
    try {
      const result = await api.listDocuments(paramsRef.current)
      if (!controller.signal.aborted) setData(result)
    } catch (e) {
      if (!controller.signal.aborted) setError(normalizeError(e))
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }, [])  // ⚠️ WAJIB deps [] — jangan tambah apapun
  
  // useEffect HANYA depend pada paramsKey (string) dan fetchData (stable)
  useEffect(() => {
    fetchData()
    return () => abortRef.current?.abort()
  }, [paramsKey, fetchData])  // ⚠️ HANYA 2 deps
  
  return { data, loading, error, refetch: fetchData }
}

export function useDocumentDetail(id) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const abortRef = useRef(null)

  useEffect(() => {
    if (!id) {
      setData(null)
      setLoading(false)
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)
    setData(null)

    const fetchDetail = async () => {
      try {
        const result = await api.getDocument(id, { signal: controller.signal })
        if (!controller.signal.aborted) setData(result)
      } catch (e) {
        if (e.name === 'AbortError') return
        if (!controller.signal.aborted) setError(normalizeError(e))
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }

    fetchDetail()

    return () => abortRef.current?.abort()
  }, [id])

  return { data, loading, error }
}
