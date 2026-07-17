/* src/views/TasksView.tsx
 *
 * The Tasks feature screen. Mirrors NotesView's shape but for tasks:
 *   * Load and list tasks (backend returns them newest-first).
 *   * Create a task, or EDIT one — the top form does both: the ✎ action loads a
 *     task's title/description/due-date into the form, which switches to update
 *     mode until saved or cancelled.
 *   * Change status inline (Pending → In Progress → Completed) via the dedicated
 *     status endpoint.
 *   * Delete a task.
 *
 * All I/O goes through `tasksApi`, and the screen is built from the shared UI
 * kit so it matches the rest of the app in light and dark. A status change
 * patches the task in place (status doesn't affect ordering); create/update
 * reload to honor the server's newest-first order; delete filters locally. */

import { useEffect, useRef, useState } from 'react'

import { tasksApi } from '../api/client'
import type { Task, TaskStatus } from '../api/types'
import {
  Button,
  Card,
  EmptyState,
  IconButton,
  IconEdit,
  IconPlus,
  IconTask,
  IconTrash,
  Input,
  Textarea,
  cn,
} from '../components/ui'
import { errorMessage } from '../lib/errors'

/** The three statuses, used to populate the status <select>. */
const STATUSES: TaskStatus[] = ['Pending', 'In Progress', 'Completed']

/** Themed classes per status — colors the inline status control by its value. */
const STATUS_STYLES: Record<TaskStatus, string> = {
  Pending:
    'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
  'In Progress':
    'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300',
  Completed:
    'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
}

/** Format an ISO timestamp for display, or return '' when absent. */
function formatDate(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString()
}

/**
 * Convert an ISO timestamp into the `datetime-local` input value (local time,
 * "YYYY-MM-DDTHH:mm"). Used when editing so the picker shows the task's current
 * due date. The reverse (input -> UTC ISO) is a plain `new Date(v).toISOString()`.
 */
function toDateTimeLocalValue(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`
}

function TasksView() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Shared form state. `editingId` decides create-vs-update.
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [dueDate, setDueDate] = useState('') // datetime-local value (local time)
  const [submitting, setSubmitting] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)

  const formRef = useRef<HTMLDivElement>(null)
  const titleRef = useRef<HTMLInputElement>(null)

  const isEditing = editingId !== null

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setTasks(await tasksApi.list())
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  /** Enter edit mode: copy the task into the form, then reveal + focus it. */
  function startEdit(task: Task) {
    setEditingId(task.id)
    setTitle(task.title)
    setDescription(task.description ?? '')
    setDueDate(task.due_date ? toDateTimeLocalValue(task.due_date) : '')
    setError(null)
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    requestAnimationFrame(() => titleRef.current?.focus())
  }

  /** Leave edit mode and clear the form back to "new task". */
  function resetForm() {
    setEditingId(null)
    setTitle('')
    setDescription('')
    setDueDate('')
  }

  /** Create a new task or save edits to an existing one, depending on mode. */
  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!title.trim()) return
    setSubmitting(true)
    setError(null)
    const payload = {
      title: title.trim(),
      description: description.trim() ? description.trim() : null,
      // datetime-local has no timezone; convert to a UTC ISO string.
      due_date: dueDate ? new Date(dueDate).toISOString() : null,
    }
    try {
      if (editingId !== null) {
        await tasksApi.update(editingId, payload)
      } else {
        await tasksApi.create(payload)
      }
      resetForm()
      await load()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleStatusChange(task: Task, status: TaskStatus) {
    setError(null)
    try {
      const updated = await tasksApi.setStatus(task.id, status)
      setTasks((current) => current.map((t) => (t.id === updated.id ? updated : t)))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  async function handleDelete(task: Task) {
    setError(null)
    try {
      await tasksApi.remove(task.id)
      if (editingId === task.id) resetForm()
      setTasks((current) => current.filter((t) => t.id !== task.id))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Create / edit form */}
      <div ref={formRef}>
        <Card className="p-4">
          <div className="mb-3 flex items-center gap-2">
            <span className="text-slate-400 dark:text-slate-500">
              {isEditing ? (
                <IconEdit className="h-4 w-4" />
              ) : (
                <IconPlus className="h-4 w-4" />
              )}
            </span>
            <h2 className="text-sm font-semibold">
              {isEditing ? 'Edit task' : 'New task'}
            </h2>
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
              placeholder="Task title"
              maxLength={255}
            />
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              rows={2}
            />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                Due
                <Input
                  type="datetime-local"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  className="w-auto"
                />
              </label>
              <div className="flex items-center gap-2">
                {isEditing && (
                  <Button type="button" variant="ghost" onClick={resetForm}>
                    Cancel
                  </Button>
                )}
                <Button type="submit" loading={submitting} disabled={!title.trim()}>
                  {isEditing ? 'Save changes' : 'Add task'}
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

      {/* List */}
      {loading ? (
        <p className="text-sm text-slate-400 dark:text-slate-500">Loading tasks…</p>
      ) : tasks.length === 0 ? (
        <EmptyState
          icon={<IconTask className="h-8 w-8" />}
          title="No tasks yet"
          hint="Add your first task above and track it to done."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {tasks.map((task) => {
            const isBeingEdited = editingId === task.id
            return (
              <li key={task.id}>
                <Card
                  className={cn(
                    'p-4 transition-shadow hover:shadow-md',
                    isBeingEdited && 'ring-2 ring-accent-500/60',
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="truncate font-medium">{task.title}</h3>
                      {task.description && (
                        <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600 dark:text-slate-300">
                          {task.description}
                        </p>
                      )}
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {/* Inline status control, colored by current value. */}
                        <select
                          value={task.status}
                          onChange={(e) =>
                            handleStatusChange(task, e.target.value as TaskStatus)
                          }
                          aria-label="Change status"
                          className={cn(
                            'cursor-pointer rounded-full border-0 px-2.5 py-1 text-xs font-medium outline-none focus-visible:ring-2 focus-visible:ring-accent-500/50',
                            STATUS_STYLES[task.status],
                          )}
                        >
                          {STATUSES.map((status) => (
                            <option key={status} value={status}>
                              {status}
                            </option>
                          ))}
                        </select>
                        {task.due_date && (
                          <span className="text-xs text-slate-400 dark:text-slate-500">
                            Due {formatDate(task.due_date)}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <IconButton label="Edit task" onClick={() => startEdit(task)}>
                        <IconEdit className="h-4 w-4" />
                      </IconButton>
                      <IconButton
                        label="Delete task"
                        variant="danger"
                        onClick={() => handleDelete(task)}
                      >
                        <IconTrash className="h-4 w-4" />
                      </IconButton>
                    </div>
                  </div>
                </Card>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

export default TasksView
