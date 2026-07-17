/* src/views/SearchView.tsx
 *
 * The semantic-search screen (Phase 3 on the client). Read-only and query-
 * driven: submit a free-text query (with an optional top_k) and render the
 * ranked results, each with the note's category/priority badges and a
 * similarity percentage.
 *
 * A `searched` flag distinguishes "you haven't searched yet" from "searched,
 * no matches" so an empty result list reads correctly. All I/O goes through
 * `searchApi`; a failed search surfaces the backend error (never a silent
 * empty result). */

import { useState } from 'react'

import { searchApi } from '../api/client'
import type { SearchResult } from '../api/types'
import { CategoryBadge, PriorityBadge } from '../components/badges'
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
      <form
        onSubmit={handleSearch}
        className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4"
      >
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search notes by meaning, e.g. “learn backend”"
          className="rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-xs text-slate-500">
            Max results
            <input
              type="number"
              min={1}
              max={50}
              value={topK}
              onChange={(e) => setTopK(e.target.value)}
              placeholder="5"
              className="w-20 rounded-md border border-slate-300 px-2 py-1 text-sm outline-none focus:border-indigo-500"
            />
          </label>
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Searching…' : 'Search'}
          </button>
        </div>
      </form>

      {/* Error banner */}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Results */}
      {!loading && searched && results.length === 0 && !error && (
        <p className="text-sm text-slate-400">No matching notes found.</p>
      )}

      {results.length > 0 && (
        <ul className="flex flex-col gap-3">
          {results.map((result) => (
            <li
              key={result.note_id}
              className="rounded-lg border border-slate-200 bg-white p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate font-medium">{result.title}</h3>
                  {result.content && (
                    <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">
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
                  <span className="text-sm font-semibold text-indigo-700">
                    {result.similarity_score}%
                  </span>
                  <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full bg-indigo-500"
                      style={{ width: `${result.similarity_score}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-slate-400">match</span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default SearchView
