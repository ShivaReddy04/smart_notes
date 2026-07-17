/* src/views/ChatView.tsx
 *
 * The chat-with-notes screen (Phase 4 RAG on the client). The backend /chat is
 * single-shot (no server-side memory), but we keep a client-side transcript of
 * Q&A pairs for a natural chat feel. Each answer renders with its source notes
 * (title + similarity %) so the grounding is visible — the whole point of RAG.
 *
 * The in-flight question is tracked separately (`pending`) so it shows
 * immediately with a "Thinking…" placeholder while the answer is generated. All
 * I/O goes through `chatApi`; on error the question is restored for retry. */

import { useState } from 'react'

import { chatApi } from '../api/client'
import type { ChatSource } from '../api/types'
import { errorMessage } from '../lib/errors'

interface Exchange {
  question: string
  answer: string
  sources: ChatSource[]
}

function Sources({ sources }: { sources: ChatSource[] }) {
  if (sources.length === 0) return null
  return (
    <div className="mt-2 border-t border-slate-100 pt-2">
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        Sources
      </p>
      <ul className="flex flex-col gap-0.5">
        {sources.map((source) => (
          <li key={source.note_id} className="flex items-center gap-2 text-xs text-slate-500">
            <span className="truncate">{source.title}</span>
            <span className="text-slate-300">·</span>
            <span className="shrink-0 text-indigo-600">{source.similarity_score}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ChatView() {
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [question, setQuestion] = useState('')
  const [pending, setPending] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleAsk(event: React.FormEvent) {
    event.preventDefault()
    const asked = question.trim()
    if (!asked) return
    setQuestion('')
    setPending(asked)
    setLoading(true)
    setError(null)
    try {
      const response = await chatApi.ask({ question: asked })
      setExchanges((current) => [
        ...current,
        { question: asked, answer: response.answer, sources: response.sources },
      ])
    } catch (err) {
      setError(errorMessage(err))
      setQuestion(asked) // restore so the user can retry
    } finally {
      setPending(null)
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Transcript */}
      <div className="flex min-h-40 flex-col gap-4">
        {exchanges.length === 0 && !pending && (
          <p className="text-sm text-slate-400">
            Ask a question about your notes, e.g. “What did I plan to study this week?”
          </p>
        )}

        {exchanges.map((exchange, index) => (
          <div key={index} className="flex flex-col gap-2">
            <div className="self-end rounded-lg rounded-br-none bg-indigo-600 px-3 py-2 text-sm text-white">
              {exchange.question}
            </div>
            <div className="self-start rounded-lg rounded-bl-none border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800">
              <p className="whitespace-pre-wrap">{exchange.answer}</p>
              <Sources sources={exchange.sources} />
            </div>
          </div>
        ))}

        {/* In-flight question */}
        {pending && (
          <div className="flex flex-col gap-2">
            <div className="self-end rounded-lg rounded-br-none bg-indigo-600 px-3 py-2 text-sm text-white">
              {pending}
            </div>
            <div className="self-start rounded-lg rounded-bl-none border border-slate-200 bg-white px-3 py-2 text-sm text-slate-400">
              Thinking…
            </div>
          </div>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Ask form */}
      <form onSubmit={handleAsk} className="flex items-center gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about your notes…"
          maxLength={1000}
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Ask
        </button>
      </form>
    </div>
  )
}

export default ChatView
