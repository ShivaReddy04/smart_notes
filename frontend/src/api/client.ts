/* src/api/client.ts
 *
 * The one place the frontend talks to the backend. Every component calls these
 * typed functions instead of touching `fetch` directly, so URL building, JSON
 * headers, error handling, and 204 handling live in exactly one seam (the same
 * "one place does the I/O" discipline the backend uses for its repositories).
 *
 * Errors: a non-2xx response is turned into an `ApiError` carrying the HTTP
 * status and the backend's `{ "detail": ... }` message, so the UI can show a
 * real reason ("Note with id 5 was not found.") rather than a generic failure.
 */

import type {
  ChatRequest,
  ChatResponse,
  Note,
  NoteCreate,
  NoteImage,
  NoteUpdate,
  SearchResult,
  Task,
  TaskCreate,
  TaskStatus,
  TaskUpdate,
} from './types'

/** API root, injected at build time from frontend/.env (VITE_API_BASE_URL). */
const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'

/**
 * The server ORIGIN, derived by stripping the '/api/v1' suffix off BASE_URL.
 * With the local storage backend, images are served at the origin root
 * (e.g. '/media/…'), NOT under the API prefix, so `mediaUrl()` joins their
 * server-relative `url` onto this.
 */
const API_ORIGIN = BASE_URL.replace(/\/api\/v\d+\/?$/, '')

/**
 * Turn a note image's `url` into an absolute, loadable URL.
 *
 * The backend returns either an absolute URL (the R2 backend, e.g.
 * 'https://…r2.dev/abc.png') or a server-relative path (the local backend,
 * '/media/abc.png'). An already-absolute URL is returned unchanged; only a
 * relative path is prefixed with the API origin. This lets the same frontend
 * work against either storage backend with no build-time switch.
 */
export function mediaUrl(path: string): string {
  return /^https?:\/\//i.test(path) ? path : `${API_ORIGIN}${path}`
}

/** Error thrown for any non-2xx response, carrying the status + backend detail. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Build a query string from defined params only (`undefined` keys are dropped). */
function queryString(
  params: Record<string, string | number | undefined>,
): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value))
  }
  const rendered = search.toString()
  return rendered ? `?${rendered}` : ''
}

/**
 * Core request helper. Sends JSON, and on failure extracts the backend's
 * `detail` message into an `ApiError`. Returns `undefined` for 204 responses
 * (e.g. DELETE) and the parsed JSON body otherwise.
 */
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  // For multipart uploads the body is a FormData: we must NOT set
  // 'Content-Type' ourselves, or we'd clobber the boundary the browser adds.
  // JSON requests keep the explicit content type as before.
  const isFormData = options.body instanceof FormData
  const headers = isFormData
    ? { ...options.headers }
    : { 'Content-Type': 'application/json', ...options.headers }

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // Non-JSON error body — keep the status text as the message.
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/* ---- Notes --------------------------------------------------------------- */

export const notesApi = {
  list: (skip = 0, limit = 100) =>
    request<Note[]>(`/notes${queryString({ skip, limit })}`),
  get: (id: number) => request<Note>(`/notes/${id}`),
  create: (data: NoteCreate) =>
    request<Note>('/notes', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: NoteUpdate) =>
    request<Note>(`/notes/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  pin: (id: number, pinned: boolean) =>
    request<Note>(`/notes/${id}/pin`, {
      method: 'PATCH',
      body: JSON.stringify({ pinned }),
    }),
  remove: (id: number) =>
    request<void>(`/notes/${id}`, { method: 'DELETE' }),

  /* ---- Image attachments (Phase 5) ---- */

  /** Attach an image to a note (multipart field `file`). */
  uploadImage: (noteId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<NoteImage>(`/notes/${noteId}/images`, {
      method: 'POST',
      body: form,
    })
  },
  /** List a note's images. */
  listImages: (noteId: number) =>
    request<NoteImage[]>(`/notes/${noteId}/images`),
  /** Remove one image from a note. */
  removeImage: (noteId: number, imageId: number) =>
    request<void>(`/notes/${noteId}/images/${imageId}`, { method: 'DELETE' }),
}

/* ---- Tasks --------------------------------------------------------------- */

export const tasksApi = {
  list: (skip = 0, limit = 100) =>
    request<Task[]>(`/tasks${queryString({ skip, limit })}`),
  get: (id: number) => request<Task>(`/tasks/${id}`),
  create: (data: TaskCreate) =>
    request<Task>('/tasks', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: TaskUpdate) =>
    request<Task>(`/tasks/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  setStatus: (id: number, status: TaskStatus) =>
    request<Task>(`/tasks/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
  remove: (id: number) =>
    request<void>(`/tasks/${id}`, { method: 'DELETE' }),
}

/* ---- Semantic search ----------------------------------------------------- */

export const searchApi = {
  search: (query: string, topK?: number) =>
    request<SearchResult[]>(`/search${queryString({ query, top_k: topK })}`),
}

/* ---- Chat / RAG ---------------------------------------------------------- */

export const chatApi = {
  ask: (body: ChatRequest) =>
    request<ChatResponse>('/chat', { method: 'POST', body: JSON.stringify(body) }),
}
