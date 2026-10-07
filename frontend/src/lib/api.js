import { API_BASE_URL } from './constants'

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

async function request(path, { method = 'GET', body, signal } = {}) {
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData
  let res
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: isFormData || !body ? undefined : { 'Content-Type': 'application/json' },
      body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
      signal,
    })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new ApiError('Tidak dapat terhubung ke server.', 0, null)
  }

  const text = await res.text()
  let data = null
  if (text) {
    try { data = JSON.parse(text) } catch { data = text }
  }

  if (!res.ok) {
    const detail =
      (typeof data === 'object' && (data?.detail ?? data?.message)) ||
      res.statusText ||
      `HTTP ${res.status}`
    throw new ApiError(String(detail), res.status, data)
  }
  return data
}

export async function riskReportFromFiles(txId, files, options = {}) {
  const form = new FormData()
  form.append('po_file', files.poFile)
  form.append('gr_file', files.grFile)
  form.append('invoice_file', files.invoiceFile)
  if (files.taxInvoiceFile) form.append('tax_invoice_file', files.taxInvoiceFile)
  form.append('has_level2_approval', String(options.hasLevel2Approval))
  form.append('has_complete_docs', String(options.hasCompleteDocs))

  return request(
    `/api/v1/audit/transactions/${encodeURIComponent(txId)}/risk-report-with-files`,
    {
      method: 'POST',
      body: form,
      signal: options.signal,
    },
  )
}

export const api = {
  matchThreeWay: (transactionId, { po, gr, invoice }, opts = {}) =>
    request(`/api/v1/audit/transactions/${encodeURIComponent(transactionId)}/match`, {
      method: 'POST',
      body: { po, gr, invoice },
      ...opts,
    }),

  riskReport: (transactionId, payload = {}, opts = {}) =>
    request(`/api/v1/audit/transactions/${encodeURIComponent(transactionId)}/risk-report`, {
      method: 'POST',
      body: {
        has_level2_approval: false,
        has_complete_docs: true,
        ...payload,
      },
      ...opts,
    }),

  createFinding: (payload, opts = {}) =>
    request('/api/v1/audit/findings', { method: 'POST', body: payload, ...opts }),

  getFinding: (id, opts = {}) =>
    request(`/api/v1/audit/findings/${encodeURIComponent(id)}`, opts),

  // Bon Permintaan (Purchase Request) endpoints
  parseBons: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/api/v1/procurement/bons/parse', {
      method: 'POST',
      body: form,
    })
  },

  listDocuments: (params = {}) => {
    const clean = Object.fromEntries(
      Object.entries(params).filter(([_key, v]) => v !== undefined && v !== null && v !== '')
    )
    const qs = new URLSearchParams(clean).toString()
    return request(`/api/v1/procurement/documents?${qs}`)
  },

  getDocument: (id) =>
    request(`/api/v1/procurement/documents/${encodeURIComponent(id)}`),
}
