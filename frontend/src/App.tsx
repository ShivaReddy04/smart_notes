/* App.tsx — the application shell.
 *
 * Owns the top-level chrome and the single piece of state that decides which
 * feature view is visible. The chrome is a product-style layout:
 *
 *   * Desktop (md+): a fixed left SIDEBAR with the brand mark, icon nav, and a
 *     theme toggle pinned at the bottom.
 *   * Mobile: the sidebar collapses. A slim top bar shows a hamburger that
 *     slides the same sidebar in as an overlay DRAWER; picking a section (or
 *     tapping the backdrop) closes it.
 *
 * State lives here (not a router) because this is a small four-view SPA — a
 * `useState` tab switch is simpler than client-side routing, and each view is a
 * one-line swap. Theming is delegated wholesale to useTheme (lib/theme.ts).
 */

import { useState } from 'react'

import {
  IconChat,
  IconClose,
  IconMenu,
  IconMoon,
  IconNote,
  IconSearch,
  IconSparkles,
  IconSun,
  IconTask,
  cn,
} from './components/ui'
import { useTheme } from './lib/theme'
import ChatView from './views/ChatView'
import NotesView from './views/NotesView'
import SearchView from './views/SearchView'
import TasksView from './views/TasksView'

/** The four feature views: nav metadata + the header shown above each view. */
const NAV = [
  {
    id: 'notes',
    label: 'Notes',
    icon: IconNote,
    title: 'Notes',
    subtitle: 'Capture ideas — AI sorts them by category and priority.',
  },
  {
    id: 'tasks',
    label: 'Tasks',
    icon: IconTask,
    title: 'Tasks',
    subtitle: 'Track what needs doing and when it’s due.',
  },
  {
    id: 'search',
    label: 'Search',
    icon: IconSearch,
    title: 'Semantic search',
    subtitle: 'Find notes by meaning, not just keywords.',
  },
  {
    id: 'chat',
    label: 'Chat',
    icon: IconChat,
    title: 'Chat',
    subtitle: 'Ask questions answered from your notes and tasks.',
  },
] as const

/** Union of the legal tab ids, derived from NAV so the two never drift. */
type TabId = (typeof NAV)[number]['id']

function App() {
  const [activeTab, setActiveTab] = useState<TabId>('notes')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const { theme, toggle } = useTheme()

  const active = NAV.find((n) => n.id === activeTab)!

  /** Switch section and always close the mobile drawer. */
  function go(id: TabId) {
    setActiveTab(id)
    setDrawerOpen(false)
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl">
        {/* --- Desktop sidebar (md+) --- */}
        <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-slate-200 bg-white md:flex dark:border-slate-800 dark:bg-slate-900">
          <SidebarBody
            activeTab={activeTab}
            onNavigate={go}
            theme={theme}
            onToggleTheme={toggle}
          />
        </aside>

        {/* --- Mobile drawer (< md) --- */}
        {drawerOpen && (
          <div className="fixed inset-0 z-40 md:hidden">
            {/* Backdrop */}
            <button
              type="button"
              aria-label="Close menu"
              onClick={() => setDrawerOpen(false)}
              className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
            />
            {/* Panel */}
            <aside className="absolute inset-y-0 left-0 flex w-64 flex-col border-r border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-900">
              <SidebarBody
                activeTab={activeTab}
                onNavigate={go}
                theme={theme}
                onToggleTheme={toggle}
                onClose={() => setDrawerOpen(false)}
              />
            </aside>
          </div>
        )}

        {/* --- Main column --- */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Mobile top bar */}
          <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur md:hidden dark:border-slate-800 dark:bg-slate-900/80">
            <button
              type="button"
              aria-label="Open menu"
              onClick={() => setDrawerOpen(true)}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              <IconMenu className="h-5 w-5" />
            </button>
            <span className="font-semibold">{active.title}</span>
          </header>

          {/* Section header + active view */}
          <main className="mx-auto w-full max-w-3xl flex-1 px-5 py-6 sm:px-8 sm:py-10">
            <div className="mb-6">
              <h1 className="text-2xl font-bold tracking-tight">{active.title}</h1>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                {active.subtitle}
              </p>
            </div>

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
      </div>
    </div>
  )
}

/**
 * The sidebar's inner content, shared verbatim by the desktop aside and the
 * mobile drawer so the nav can never drift between the two. `onClose` renders a
 * close button (drawer only); it is omitted on desktop.
 */
function SidebarBody({
  activeTab,
  onNavigate,
  theme,
  onToggleTheme,
  onClose,
}: {
  activeTab: TabId
  onNavigate: (id: TabId) => void
  theme: 'light' | 'dark'
  onToggleTheme: () => void
  onClose?: () => void
}) {
  return (
    <>
      {/* Brand */}
      <div className="flex items-center gap-3 px-5 py-5">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-600 text-white shadow-sm">
          <IconSparkles className="h-5 w-5" />
        </span>
        <div className="min-w-0 leading-tight">
          <p className="truncate text-sm font-semibold">Smart Notes</p>
          <p className="truncate text-xs text-slate-400 dark:text-slate-500">AI workspace</p>
        </div>
        {onClose && (
          <button
            type="button"
            aria-label="Close menu"
            onClick={onClose}
            className="ml-auto inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
          >
            <IconClose className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Nav */}
      <nav className="flex flex-1 flex-col gap-1 px-3">
        {NAV.map((item) => {
          const isActive = item.id === activeTab
          const Icon = item.icon
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id)}
              aria-current={isActive ? 'page' : undefined}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-accent-50 text-accent-700 dark:bg-accent-500/10 dark:text-accent-300'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/70 dark:hover:text-slate-100',
              )}
            >
              <Icon className="h-[18px] w-[18px]" />
              {item.label}
            </button>
          )
        })}
      </nav>

      {/* Footer: theme toggle */}
      <div className="border-t border-slate-200 p-3 dark:border-slate-800">
        <button
          type="button"
          onClick={onToggleTheme}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/70 dark:hover:text-slate-100"
        >
          {theme === 'dark' ? (
            <IconSun className="h-[18px] w-[18px]" />
          ) : (
            <IconMoon className="h-[18px] w-[18px]" />
          )}
          {theme === 'dark' ? 'Light mode' : 'Dark mode'}
        </button>
      </div>
    </>
  )
}

export default App
