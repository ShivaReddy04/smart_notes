/* App.tsx — the application shell.
 *
 * Owns the top-level chrome (header + tab bar) and the single piece of state
 * that decides which feature view is visible. Each tab renders its feature
 * view (Notes, Tasks, Search, Chat), each backed by the typed API client.
 *
 * State lives here (not a router) because this is a small four-view SPA — a
 * `useState` tab switch is simpler to follow than client-side routing, and the
 * seam to swap in a view is a single line per tab. */

import { useState } from 'react'

import ChatView from './views/ChatView'
import NotesView from './views/NotesView'
import SearchView from './views/SearchView'
import TasksView from './views/TasksView'

/** The four feature views, in display order. `id` is the switch key. */
const TABS = [
  { id: 'notes', label: 'Notes' },
  { id: 'tasks', label: 'Tasks' },
  { id: 'search', label: 'Search' },
  { id: 'chat', label: 'Chat' },
] as const

/** Union of the legal tab ids, derived from TABS so the two never drift. */
type TabId = (typeof TABS)[number]['id']

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('notes')

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl flex-col gap-1 px-6 py-5">
          <h1 className="text-2xl font-bold tracking-tight">AI Smart Notes</h1>
          <p className="text-sm text-slate-500">
            Notes &amp; tasks with AI categorization, semantic search, and chat.
          </p>
        </div>
      </header>

      {/* Tab navigation */}
      <nav className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl gap-1 px-4">
          {TABS.map((tab) => {
            const isActive = tab.id === activeTab
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={
                  'border-b-2 px-4 py-3 text-sm font-medium transition-colors ' +
                  (isActive
                    ? 'border-indigo-600 text-indigo-700'
                    : 'border-transparent text-slate-500 hover:text-slate-800')
                }
              >
                {tab.label}
              </button>
            )
          })}
        </div>
      </nav>

      {/* Active view */}
      <main className="mx-auto max-w-3xl px-6 py-8">
        {activeTab === 'notes' ? (
          <NotesView />
        ) : activeTab === 'tasks' ? (
          <TasksView />
        ) : activeTab === 'search' ? (
          <SearchView />
        ) : (
          <ChatView />
        )}
      </main>
    </div>
  )
}

export default App
