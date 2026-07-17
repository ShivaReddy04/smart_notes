/* src/views/NotesView.tsx
 *
 * The Notes feature screen. Responsibilities:
 *   * Load and list notes (the backend returns them pinned-first, newest-first).
 *   * Create a note (title required, content optional).
 *   * Pin/unpin and delete a note.
 *   * Show each note's AI-assigned category + priority as badges.
 *
 * All I/O goes through `notesApi`; this component only orchestrates state and
 * rendering. After a mutation we reload the list so the server's ordering stays
 * authoritative instead of re-sorting on the client. Failures surface the
 * backend's `detail` message via the `ApiError` thrown by the client. */

import { useEffect, useState } from 'react'

import { mediaUrl, notesApi } from '../api/client'
import type { Note, NoteImage } from '../api/types'
import { CategoryBadge, PriorityBadge } from '../components/badges'
import { errorMessage } from '../lib/errors'

function NotesView() {
  const [notes, setNotes] = useState<Note[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Which note is currently uploading an image (disables its control + shows a
  // spinner label). null when no upload is in flight.
  const [uploadingId, setUploadingId] = useState<number | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setNotes(await notesApi.list())
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  // Load once on mount.
  useEffect(() => {
    void load()
  }, [])

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    if (!title.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      await notesApi.create({
        title: title.trim(),
        content: content.trim() ? content.trim() : null,
      })
      setTitle('')
      setContent('')
      await load()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function handlePin(note: Note) {
    setError(null)
    try {
      await notesApi.pin(note.id, !note.is_pinned)
      await load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function handleDelete(note: Note) {
    setError(null)
    try {
      await notesApi.remove(note.id)
      setNotes((current) => current.filter((n) => n.id !== note.id))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  // Upload one or more selected images to a note. We upload sequentially (so a
  // single failure stops the rest and surfaces its message) then reload so the
  // note's embedded `images` reflect the server, including each image's URL.
  async function handleUploadImages(note: Note, files: FileList | null) {
    if (!files || files.length === 0) return
    setError(null)
    setUploadingId(note.id)
    try {
      for (const file of Array.from(files)) {
        await notesApi.uploadImage(note.id, file)
      }
      await load()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setUploadingId(null)
    }
  }

  async function handleDeleteImage(note: Note, image: NoteImage) {
    setError(null)
    try {
      await notesApi.removeImage(note.id, image.id)
      await load()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Create form */}
      <form
        onSubmit={handleCreate}
        className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4"
      >
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Note title"
          maxLength={255}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Content (optional)"
          rows={3}
          className="w-full resize-y rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-400">
            Category &amp; priority are assigned automatically.
          </span>
          <button
            type="submit"
            disabled={submitting || !title.trim()}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? 'Adding…' : 'Add note'}
          </button>
        </div>
      </form>

      {/* Error banner */}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* List */}
      {loading ? (
        <p className="text-sm text-slate-400">Loading notes…</p>
      ) : notes.length === 0 ? (
        <p className="text-sm text-slate-400">No notes yet. Add your first one above.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {notes.map((note) => (
            <li
              key={note.id}
              className="rounded-lg border border-slate-200 bg-white p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    {note.is_pinned && (
                      <span title="Pinned" className="text-indigo-500">
                        ●
                      </span>
                    )}
                    <h3 className="truncate font-medium">{note.title}</h3>
                  </div>
                  {note.content && (
                    <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">
                      {note.content}
                    </p>
                  )}
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <CategoryBadge category={note.category} />
                    <PriorityBadge priority={note.priority} />
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <button
                    type="button"
                    onClick={() => handlePin(note)}
                    className="text-xs font-medium text-slate-500 hover:text-indigo-700"
                  >
                    {note.is_pinned ? 'Unpin' : 'Pin'}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(note)}
                    className="text-xs font-medium text-slate-500 hover:text-red-600"
                  >
                    Delete
                  </button>
                </div>
              </div>

              {/* Attached images: thumbnails (click to open full size) + an
                  add-image tile. Each thumbnail has a hover ✕ to remove it. */}
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {note.images.map((img) => (
                  <div key={img.id} className="group relative">
                    <a
                      href={mediaUrl(img.url)}
                      target="_blank"
                      rel="noreferrer"
                      title={img.original_name}
                    >
                      <img
                        src={mediaUrl(img.url)}
                        alt={img.original_name}
                        className="h-20 w-20 rounded-md border border-slate-200 object-cover"
                      />
                    </a>
                    <button
                      type="button"
                      onClick={() => handleDeleteImage(note, img)}
                      title="Remove image"
                      className="absolute -right-1.5 -top-1.5 hidden h-5 w-5 items-center justify-center rounded-full bg-red-600 text-xs font-bold leading-none text-white group-hover:flex"
                    >
                      ×
                    </button>
                  </div>
                ))}
                <label
                  className={
                    'flex h-20 w-20 flex-col items-center justify-center rounded-md border border-dashed text-center text-xs transition-colors ' +
                    (uploadingId === note.id
                      ? 'cursor-wait border-slate-200 text-slate-300'
                      : 'cursor-pointer border-slate-300 text-slate-400 hover:border-indigo-400 hover:text-indigo-500')
                  }
                >
                  {uploadingId === note.id ? 'Uploading…' : '＋ Image'}
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif"
                    multiple
                    disabled={uploadingId === note.id}
                    onChange={(e) => {
                      void handleUploadImages(note, e.target.files)
                      e.target.value = '' // allow re-picking the same file
                    }}
                    className="hidden"
                  />
                </label>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default NotesView
