/**
 * The single HTTP client.
 *
 * Relative base URL: in production FastAPI serves this bundle from its own
 * origin, and in development Vite proxies `/api` to it. Nothing here ever
 * needs to know a hostname, which is what makes the closed-network build
 * identical to the local one.
 */

import axios, { AxiosError } from 'axios'

export const apiClient = axios.create({
  baseURL: '/api',
  timeout: 20_000,
  headers: { 'Content-Type': 'application/json' },
})

/** An error already carrying a message fit to show a user. */
export class ApiError extends Error {
  readonly status: number | undefined

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const FALLBACK_MESSAGE = 'אירעה שגיאה בתקשורת עם השרת.'

function extractDetail(error: AxiosError): string {
  const data = error.response?.data as { detail?: unknown } | undefined
  const detail = data?.detail

  if (typeof detail === 'string' && detail.trim()) return detail

  // FastAPI validation errors arrive as an array of issue objects. Surfacing
  // the raw array would show the user a JSON blob.
  if (Array.isArray(detail)) return 'אחד מהערכים שנשלחו אינו תקין.'

  if (error.code === 'ECONNABORTED') return 'הבקשה לשרת חרגה מזמן ההמתנה.'
  if (error.response?.status === 503) return 'הנתונים עדיין נטענים. נסה שוב בעוד רגע.'
  if (!error.response) return 'אין תקשורת עם השרת. ודא שהשירות פועל.'

  return FALLBACK_MESSAGE
}

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error)) {
      return Promise.reject(new ApiError(extractDetail(error), error.response?.status))
    }
    return Promise.reject(new ApiError(FALLBACK_MESSAGE))
  },
)
