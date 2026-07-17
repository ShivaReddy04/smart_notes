/* src/views/TasksView.tsx
 *
 * The Tasks feature screen. Mirrors NotesView's shape but for tasks:
 *   * Load and list tasks (backend returns them newest-first).
 *   * Create a task (title required; description and due date optional).
 *   * Change status via the dedicated status endpoint (Pending → In Progress →
 *     Completed).
 *   * Delete a task.
 *
 * All I/O goes through `tasksApi`. A status change returns the updated task, so
 * we patch it into state in place (status doesn't affect ordering); create
 * reloads to honor the server's newest-first order; delete filters locally. */

import { useEffect, useState } from 'react'

import { tasksApi } from '../api/client'
import type { Task, TaskStatus } from '../api/types'
import { errorMessage } from '../lib/errors'

/** The three statuses, used to populate the status <select>. */
const STATUSES: TaskStatus[] = ['Pending', 'In Progress', 'Completed']

/** Tailwind classes per status badge. */
const STATUS_STYLES: Record<TaskStatus, string> = {
  Pending: 'bg-slate-100 text-slate-600',
  'In Progress': 'bg-blue-100 text-blue-700',
  Completed: 'bg-emerald-100 text-emerald-700',
}

/** Format an ISO timestamp for display, or return '' when absent. */
function formatDate(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString()
}

function TasksView() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [dueDate, setDueDate] = useState('') // datetime-local value (local time)
  const [submitting, setSubmitting] = useState(false)

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

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    if (!title.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      await tasksApi.create({
        title: title.trim(),
        description: description.trim() ? description.trim() : null,
        // datetime-local has no timezone; convert to a UTC ISO string.
        due_date: dueDate ? new Date(dueDate).toISOString() : null,
      })
      setTitle('')
      setDescription('')
      setDueDate('')
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
      setTasks((current) => current.filter((t) => t.id !== task.id))
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
          placeholder="Task title"
          maxLength={255}
          className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Description (optional)"
          rows={2}
          className="resize-y rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-xs text-slate-500">
            Due
            <input
              type="datetime-local"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="rounded-md border border-slate-300 px-2 py-1 text-sm outline-none focus:border-indigo-500"
            />
          </label>
          <button
            type="submit"
            disabled={submitting || !title.trim()}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting ? 'Adding…' : 'Add task'}
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
        <p className="text-sm text-slate-400">Loading tasks…</p>
      ) : tasks.length === 0 ? (
        <p className="text-sm text-slate-400">No tasks yet. Add your first one above.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {tasks.map((task) => (
            <li
              key={task.id}
              className="rounded-lg border border-slate-200 bg-white p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate font-medium">{task.title}</h3>
                  {task.description && (
                    <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">
                      {task.description}
                    </p>
                  )}
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[task.status]}`}
                    >
                      {task.status}
                    </span>
                    {task.due_date && (
                      <span className="text-xs text-slate-400">
                        Due {formatDate(task.due_date)}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <select
                    value={task.status}
                    onChange={(e) =>
                      handleStatusChange(task, e.target.value as TaskStatus)
                    }
                    className="rounded-md border border-slate-300 px-2 py-1 text-xs outline-none focus:border-indigo-500"
                  >
                    {STATUSES.map((status) => (
                      <option key={status} value={status}>
                        {status}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => handleDelete(task)}
                    className="text-xs font-medium text-slate-500 hover:text-red-600"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default TasksView
