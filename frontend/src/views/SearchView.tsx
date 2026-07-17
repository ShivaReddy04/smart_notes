/* src/views/SearchView.tsx
 *
 * The semantic-search screen (Phase 3 on the client). Read-only and query-
 * driven: submit a free-text query (with an optional top_k) and render the
 * ranked results, each with the note's category/priority badges and a
 * similarity percentage + bar.
 *
 * A `searched` flag distinguishes "you haven't searched yet" from "searched,
 * no matches" so the two empty states read correctly. All I/O goes through
 * `searchApi`; a failed search surfaces the backend error (never a silent
 * empty result). Built from the shared UI kit for light/dark parity. */

import { useState } from 'react'

import { searchApi } from '../api/client'
import type { SearchResult } from '../api/types'
import { CategoryBadge, PriorityBadge } from '../components/badges'
import {
  Button,
  Card,
  EmptyState,
  IconSearch,
  Input,
} from '../components/ui'
import { errorMessage } from '../lib/errors'

function SearchView() {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState('') // optional; empty = server default
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searched, setSearched] = useState(false)

  async function handleSearch(event: React.FormEvent) {
    event.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const parsedTopK = topK ? Number(topK) : undefined
      setResults(await searchApi.search(query.trim(), parsedTopK))
      setSearched(true)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Search form */}
      <Card className="p-4">
        <form onSubmit={handleSearch} className="flex flex-col gap-3">
          <Input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search notes by meaning, e.g. “learn backend”"
          />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
              Max results
              <Input
                type="number"
                min={1}
                max={50}
                value={topK}
                onChange={(e) => setTopK(e.target.value)}
                placeholder="5"
                className="w-20"
              />
            </label>
            <Button
              type="submit"
              loading={loading}
              disabled={!query.trim()}
              icon={!loading && <IconSearch className="h-4 w-4" />}
            >
              Search
            </Button>
          </div>
        </form>
      </Card>

      {/* Error banner */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Pre-search hint */}
      {!searched && !loading && !error && (
        <EmptyState
          icon={<IconSearch className="h-8 w-8" />}
          title="Search your notes by meaning"
          hint="Type what you’re looking for — results are ranked by semantic similarity, not just keywords."
        />
      )}

      {/* Searched, no matches */}
      {!loading && searched && results.length === 0 && !error && (
        <EmptyState
          icon={<IconSearch className="h-8 w-8" />}
          title="No matching notes found"
          hint="Try different wording or a broader query."
        />
      )}

      {/* Results */}
      {results.length > 0 && (
        <ul className="flex flex-col gap-3">
          {results.map((result) => (
            <li key={result.note_id}>
              <Card className="p-4 transition-shadow hover:shadow-md">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="truncate font-medium">{result.title}</h3>
                    {result.content && (
                      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600 dark:text-slate-300">
                        {result.content}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <CategoryBadge category={result.category} />
                      <PriorityBadge priority={result.priority} />
                    </div>
                  </div>
                  {/* Similarity score + bar */}
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="text-sm font-semibold text-accent-600 dark:text-accent-400">
                      {result.similarity_score}%
                    </span>
                    <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                      <div
                        className="h-full rounded-full bg-accent-500"
                        style={{ width: `${result.similarity_score}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-slate-400 dark:text-slate-500">
                      match
                    </span>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default SearchView
