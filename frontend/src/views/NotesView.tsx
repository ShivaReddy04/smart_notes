/* src/views/NotesView.tsx
 *
 * The Notes feature screen. Responsibilities:
 *   * Load and list notes (the backend returns them pinned-first, newest-first).
 *   * Create a note, or EDIT an existing one — the same top form does both: the
 *     "Edit" action on a card loads that note into the form, which switches to
 *     "Update" mode until saved or cancelled.
 *   * Pin/unpin and delete a note.
 *   * Attach / remove images.
 *   * Show each note's AI-assigned category + priority as badges.
 *
 * All I/O goes through `notesApi`; this component only orchestrates state and
 * rendering, and uses the shared UI kit (components/ui) so it matches the rest
 * of the app in both light and dark themes. After a mutation we reload the list
 * so the server's ordering stays authoritative. Failures surface the backend's
 * `detail` message via the `ApiError` thrown by the client. */

import { useEffect, useRef, useState } from 'react'

import { mediaUrl, notesApi, tasksApi } from '../api/client'
import type { Note, NoteImage, TaskSuggestion } from '../api/types'
import { CategoryBadge, PriorityBadge } from '../components/badges'
import {
  Button,
  Card,
  EmptyState,
  IconButton,
  IconClose,
  IconEdit,
  IconImage,
  IconNote,
  IconPin,
  IconPlus,
  IconSparkles,
  IconTrash,
  Input,
  Spinner,
  Textarea,
  cn,
} from '../components/ui'
import { errorMessage } from '../lib/errors'

function NotesView() {
  const [notes, setNotes] = useState<Note[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Shared form state. `editingId` decides create-vs-update: null = creating a
  // new note, a number = editing that note.
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)

  // Which note is currently uploading an image (disables its control + shows a
  // spinner label). null when no upload is in flight.
  const [uploadingId, setUploadingId] = useState<number | null>(null)

  // AI task-extraction state. `extractingId` = the note currently being
  // analyzed; `suggestNoteId` = the note whose suggestions panel is open, with
  // `suggestions` + a parallel `selected` mask; `creatingTasks` while saving.
  const [extractingId, setExtractingId] = useState<number | null>(null)
  const [suggestNoteId, setSuggestNoteId] = useState<number | null>(null)
  const [suggestions, setSuggestions] = useState<TaskSuggestion[]>([])
  const [selected, setSelected] = useState<boolean[]>([])
  const [creatingTasks, setCreatingTasks] = useState(false)
  const [createdMessage, setCreatedMessage] = useState<string | null>(null)

  // Refs so entering edit mode can scroll the form into view and focus it.
  const formRef = useRef<HTMLDivElement>(null)
  const titleRef = useRef<HTMLInputElement>(null)

  const isEditing = editingId !== null

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

  /** Enter edit mode: copy the note into the form, then reveal + focus it. */
  function startEdit(note: Note) {
    setEditingId(note.id)
    setTitle(note.title)
    setContent(note.content ?? '')
    setError(null)
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    // Focus after the scroll/paint so the caret lands in the title field.
    requestAnimationFrame(() => titleRef.current?.focus())
  }

  /** Leave edit mode and clear the form back to "new note". */
  function resetForm() {
    setEditingId(null)
    setTitle('')
    setContent('')
  }

  /** Create a new note or save edits to an existing one, depending on mode. */
  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!title.trim()) return
    setSubmitting(true)
    setError(null)
    const payload = {
      title: title.trim(),
      content: content.trim() ? content.trim() : null,
    }
    try {
      if (editingId !== null) {
        await notesApi.update(editingId, payload)
      } else {
        await notesApi.create(payload)
      }
      resetForm()
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
      // If we were editing the note we just deleted, drop out of edit mode.
      if (editingId === note.id) resetForm()
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

  /** Ask the AI to extract tasks from a note and open its suggestions panel. */
  async function handleExtract(note: Note) {
    setError(null)
    setCreatedMessage(null)
    setExtractingId(note.id)
    try {
      const result = await notesApi.suggestTasks(note.id)
      setSuggestNoteId(note.id)
      setSuggestions(result)
      setSelected(result.map(() => true)) // all checked by default
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setExtractingId(null)
    }
  }

  function toggleSuggestion(index: number) {
    setSelected((prev) => prev.map((v, i) => (i === index ? !v : v)))
  }

  function closeSuggestions() {
    setSuggestNoteId(null)
    setSuggestions([])
    setSelected([])
  }

  /** Create the checked suggestions as real tasks, then close the panel. */
  async function handleCreateSelected() {
    const chosen = suggestions.filter((_, i) => selected[i])
    if (chosen.length === 0) return
    setCreatingTasks(true)
    setError(null)
    try {
      for (const suggestion of chosen) {
        await tasksApi.create({
          title: suggestion.title,
          description: suggestion.description,
          due_date: null,
        })
      }
      setCreatedMessage(
        `Added ${chosen.length} task${chosen.length === 1 ? '' : 's'} to your Tasks.`,
      )
      closeSuggestions()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setCreatingTasks(false)
    }
  }

  const selectedCount = selected.filter(Boolean).length

  return (
    <div className="flex flex-col gap-6">
      {/* Create / edit form */}
      <div ref={formRef}>
        <Card className="p-4">
        <div className="mb-3 flex items-center gap-2">
          <span className="text-slate-400 dark:text-slate-500">
            {isEditing ? <IconEdit className="h-4 w-4" /> : <IconPlus className="h-4 w-4" />}
          </span>
          <h2 className="text-sm font-semibold">{isEditing ? 'Edit note' : 'New note'}</h2>
          {isEditing && (
            <span className="rounded-full bg-accent-50 px-2 py-0.5 text-xs font-medium text-accent-700 dark:bg-accent-500/10 dark:text-accent-300">
              editing
            </span>
          )}
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <Input
            ref={titleRef}
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Note title"
            maxLength={255}
          />
          <Textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Content (optional)"
            rows={3}
          />
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-slate-400 dark:text-slate-500">
              Category &amp; priority are assigned automatically.
            </span>
            <div className="flex items-center gap-2">
              {isEditing && (
                <Button type="button" variant="ghost" size="md" onClick={resetForm}>
                  Cancel
                </Button>
              )}
              <Button type="submit" loading={submitting} disabled={!title.trim()}>
                {isEditing ? 'Save changes' : 'Add note'}
              </Button>
            </div>
          </div>
        </form>
        </Card>
      </div>

      {/* Error banner */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Task-created confirmation */}
      {createdMessage && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-300">
          <span>{createdMessage}</span>
          <button
            type="button"
            onClick={() => setCreatedMessage(null)}
            aria-label="Dismiss"
            className="shrink-0 opacity-70 hover:opacity-100"
          >
            <IconClose className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* List */}
      {loading ? (
        <p className="text-sm text-slate-400 dark:text-slate-500">Loading notes…</p>
      ) : notes.length === 0 ? (
        <EmptyState
          icon={<IconNote className="h-8 w-8" />}
          title="No notes yet"
          hint="Add your first note above — AI will categorize it for you."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {notes.map((note) => {
            const isBeingEdited = editingId === note.id
            return (
              <li key={note.id}>
                <Card
                  className={cn(
                    'p-4 transition-shadow hover:shadow-md',
                    isBeingEdited && 'ring-2 ring-accent-500/60',
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        {note.is_pinned && (
                          <span
                            title="Pinned"
                            className="text-accent-500 dark:text-accent-400"
                          >
                            <IconPin className="h-3.5 w-3.5" />
                          </span>
                        )}
                        <h3 className="truncate font-medium">{note.title}</h3>
                      </div>
                      {note.content && (
                        <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600 dark:text-slate-300">
                          {note.content}
                        </p>
                      )}
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <CategoryBadge category={note.category} />
                        <PriorityBadge priority={note.priority} />
                      </div>
                      <button
                        type="button"
                        onClick={() => handleExtract(note)}
                        disabled={extractingId === note.id}
                        className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-accent-600 transition-colors hover:text-accent-500 disabled:opacity-60 dark:text-accent-400"
                      >
                        {extractingId === note.id ? (
                          <Spinner className="h-3.5 w-3.5" />
                        ) : (
                          <IconSparkles className="h-3.5 w-3.5" />
                        )}
                        {extractingId === note.id ? 'Extracting…' : 'Extract tasks'}
                      </button>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <IconButton label="Edit note" onClick={() => startEdit(note)}>
                        <IconEdit className="h-4 w-4" />
                      </IconButton>
                      <IconButton
                        label={note.is_pinned ? 'Unpin note' : 'Pin note'}
                        variant={note.is_pinned ? 'active' : 'ghost'}
                        onClick={() => handlePin(note)}
                      >
                        <IconPin className="h-4 w-4" />
                      </IconButton>
                      <IconButton
                        label="Delete note"
                        variant="danger"
                        onClick={() => handleDelete(note)}
                      >
                        <IconTrash className="h-4 w-4" />
                      </IconButton>
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
                            className="h-20 w-20 rounded-lg border border-slate-200 object-cover dark:border-slate-700"
                          />
                        </a>
                        <button
                          type="button"
                          onClick={() => handleDeleteImage(note, img)}
                          title="Remove image"
                          aria-label="Remove image"
                          className="absolute -right-1.5 -top-1.5 hidden h-5 w-5 items-center justify-center rounded-full bg-red-600 text-white shadow group-hover:flex"
                        >
                          <IconClose className="h-3 w-3" />
                        </button>
                      </div>
                    ))}
                    <label
                      className={cn(
                        'flex h-20 w-20 flex-col items-center justify-center gap-1 rounded-lg border border-dashed text-center text-xs transition-colors',
                        uploadingId === note.id
                          ? 'cursor-wait border-slate-200 text-slate-300 dark:border-slate-700 dark:text-slate-600'
                          : 'cursor-pointer border-slate-300 text-slate-400 hover:border-accent-400 hover:text-accent-500 dark:border-slate-700 dark:text-slate-500 dark:hover:border-accent-500 dark:hover:text-accent-400',
                      )}
                    >
                      <IconImage className="h-4 w-4" />
                      {uploadingId === note.id ? 'Uploading…' : 'Image'}
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

                  {/* AI task suggestions for this note (drafts until created) */}
                  {suggestNoteId === note.id && (
                    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-800/40">
                      {suggestions.length === 0 ? (
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs text-slate-500 dark:text-slate-400">
                            No actionable tasks found in this note.
                          </p>
                          <button
                            type="button"
                            onClick={closeSuggestions}
                            className="text-xs font-medium text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100"
                          >
                            Dismiss
                          </button>
                        </div>
                      ) : (
                        <>
                          <div className="mb-2 flex items-center justify-between">
                            <p className="text-xs font-semibold text-slate-600 dark:text-slate-300">
                              Suggested tasks
                            </p>
                            <IconButton
                              label="Close suggestions"
                              onClick={closeSuggestions}
                            >
                              <IconClose className="h-4 w-4" />
                            </IconButton>
                          </div>
                          <ul className="flex flex-col gap-1">
                            {suggestions.map((suggestion, index) => (
                              <li key={index}>
                                <label className="flex cursor-pointer items-start gap-2 rounded-md px-1.5 py-1 hover:bg-slate-100 dark:hover:bg-slate-800/60">
                                  <input
                                    type="checkbox"
                                    checked={selected[index] ?? false}
                                    onChange={() => toggleSuggestion(index)}
                                    className="mt-0.5 h-4 w-4 shrink-0 accent-accent-600"
                                  />
                                  <span className="min-w-0">
                                    <span className="block text-sm text-slate-800 dark:text-slate-100">
                                      {suggestion.title}
                                    </span>
                                    {suggestion.description && (
                                      <span className="block text-xs text-slate-500 dark:text-slate-400">
                                        {suggestion.description}
                                      </span>
                                    )}
                                  </span>
                                </label>
                              </li>
                            ))}
                          </ul>
                          <div className="mt-2 flex items-center justify-end gap-2">
                            <Button size="sm" variant="ghost" onClick={closeSuggestions}>
                              Cancel
                            </Button>
                            <Button
                              size="sm"
                              loading={creatingTasks}
                              disabled={selectedCount === 0}
                              onClick={handleCreateSelected}
                            >
                              {`Create ${selectedCount} task${selectedCount === 1 ? '' : 's'}`}
                            </Button>
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </Card>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

export default NotesView
