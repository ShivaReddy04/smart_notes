/* src/api/types.ts
 *
 * The TypeScript mirror of the backend's Pydantic schemas — the single source
 * of truth for every shape that crosses the API on the frontend side. Keeping
 * these in one file means a backend contract change surfaces here as a compile
 * error wherever the frontend is now wrong, which is the whole reason we chose
 * TypeScript for this SPA.
 *
 * Conventions:
 *   * JSON has no Date type, so all timestamps (`created_at`, `updated_at`,
 *     `due_date`) arrive as ISO-8601 strings and are typed `string`.
 *   * `| null` matches the backend's `Optional[...]` (Pydantic `X | None`).
 *   * The enums are modeled as string-literal unions so invalid values are
 *     caught at compile time and the members are autocompleted.
 */

/* ---- Enums (mirror app/ai/schemas.py and app/models/task.py) ------------- */

/** The eleven note categories the AI may assign (source of truth: Category). */
export type Category =
  | 'Work'
  | 'Study'
  | 'Personal'
  | 'Shopping'
  | 'Finance'
  | 'Health'
  | 'Ideas'
  | 'Coding'
  | 'Meetings'
  | 'Travel'
  | 'Other'

/** The three note priorities the AI may assign (source of truth: Priority). */
export type Priority = 'High' | 'Medium' | 'Low'

/** The three task states (source of truth: TaskStatus native PG enum). */
export type TaskStatus = 'Pending' | 'In Progress' | 'Completed'

/* ---- Notes (mirror app/schemas/note.py) ---------------------------------- */

/** An image attached to a note (mirror NoteImageResponse). */
export interface NoteImage {
  id: number
  /** Original filename as uploaded (for display/download). */
  original_name: string
  /** MIME type, e.g. 'image/png'. */
  content_type: string
  /** Size of the stored file in bytes. */
  size: number
  created_at: string
  /**
   * Server-relative path to fetch the bytes, e.g. '/media/9f3a…png'.
   * NOT under the API prefix — resolve it with `mediaUrl()` from the client.
   */
  url: string
}

/** A note as returned by the API (NoteResponse). */
export interface Note {
  id: number
  title: string
  content: string | null
  is_pinned: boolean
  /** AI-assigned, read-only. */
  category: Category
  /** AI-assigned, read-only. */
  priority: Priority
  created_at: string
  updated_at: string
  /** Attached images, oldest-first. Empty when the note has none. */
  images: NoteImage[]
}

/** Request body for POST /notes (NoteCreate). */
export interface NoteCreate {
  title: string
  content?: string | null
}

/** Request body for PUT /notes/{id} (NoteUpdate) — partial; send only changes. */
export interface NoteUpdate {
  title?: string
  content?: string | null
}

/** Request body for PATCH /notes/{id}/pin — `{ "pinned": boolean }`. */
export interface PinUpdate {
  pinned: boolean
}

/* ---- Tasks (mirror app/schemas/task.py) ---------------------------------- */

/** A task as returned by the API (TaskResponse). */
export interface Task {
  id: number
  title: string
  description: string | null
  due_date: string | null
  status: TaskStatus
  created_at: string
  updated_at: string
}

/** Request body for POST /tasks (TaskCreate). */
export interface TaskCreate {
  title: string
  description?: string | null
  due_date?: string | null
}

/** Request body for PUT /tasks/{id} (TaskUpdate) — partial; send only changes. */
export interface TaskUpdate {
  title?: string
  description?: string | null
  due_date?: string | null
}

/** Request body for PATCH /tasks/{id}/status (TaskStatusUpdate). */
export interface TaskStatusUpdate {
  status: TaskStatus
}

/* ---- Auth (mirror app/schemas/user.py) ----------------------------------- */

/** Request body for POST /auth/register and /auth/login. */
export interface AuthCredentials {
  email: string
  password: string
}

/** The current user (UserResponse) — never carries the password hash. */
export interface AuthUser {
  id: number
  email: string
  created_at: string
}

/** Response of register/login (Token) — the JWT to send as a Bearer header. */
export interface AuthToken {
  access_token: string
  token_type: string
}

/* ---- Semantic search (mirror app/ai/embedding_models.py: SearchResult) ---- */

/** One ranked hit from GET /search. */
export interface SearchResult {
  note_id: number
  title: string
  content: string | null
  category: Category
  priority: Priority
  created_at: string
  updated_at: string
  /** Similarity to the query, 0-100 (higher is closer). */
  similarity_score: number
}

/* ---- Chat / RAG (mirror app/schemas/chat.py) ----------------------------- */

/** Request body for POST /chat (ChatRequest). */
export interface ChatRequest {
  question: string
  /** Optional: how many notes to retrieve as context (1-20). */
  top_k?: number | null
}

/** One grounding note echoed back with a chat answer (ChatSource). */
export interface ChatSource {
  note_id: number
  title: string
  similarity_score: number
}

/** Response body for POST /chat (ChatResponse). */
export interface ChatResponse {
  answer: string
  sources: ChatSource[]
}
