/* src/views/ChatView.tsx
 *
 * The chat screen (RAG on the client). The backend /chat is single-shot (no
 * server-side memory), but we keep a client-side transcript of Q&A pairs for a
 * natural chat feel. Since Phase A the backend answers from the user's notes AND
 * tasks, so the UI invites both kinds of question. Each answer renders with its
 * source notes (title + similarity %) so the grounding stays visible.
 *
 * The in-flight question is tracked separately (`pending`) so it shows
 * immediately with a "Thinking…" placeholder while the answer is generated. All
 * I/O goes through `chatApi`; on error the question is restored for retry. Built
 * from the shared UI kit for light/dark parity with the rest of the app. */

import { useEffect, useRef, useState } from 'react'

import { chatApi } from '../api/client'
import type { ChatSource } from '../api/types'
import { Button, Card, IconSend, IconSparkles, cn } from '../components/ui'
import { errorMessage } from '../lib/errors'

interface Exchange {
  question: string
  answer: string
  sources: ChatSource[]
}

/** Starter prompts (notes + tasks) shown on the empty state; click to fill. */
const EXAMPLES = [
  'What did I plan to study this week?',
  'Which tasks are still pending?',
  'Summarize my finance notes',
  'What’s due soon?',
]

function Sources({ sources }: { sources: ChatSource[] }) {
  if (sources.length === 0) return null
  return (
    <div className="mt-2 border-t border-slate-100 pt-2 dark:border-slate-800">
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        Sources
      </p>
      <ul className="flex flex-col gap-0.5">
        {sources.map((source) => (
          <li
            key={source.note_id}
            className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400"
          >
            <span className="truncate">{source.title}</span>
            <span className="text-slate-300 dark:text-slate-600">·</span>
            <span className="shrink-0 text-accent-600 dark:text-accent-400">
              {source.similarity_score}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Three-dot "typing" indicator shown while an answer is generating. */
function Thinking() {
  return (
    <span className="flex items-center gap-1 py-0.5" aria-label="Thinking">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400 dark:bg-slate-500"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  )
}

function ChatView() {
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [question, setQuestion] = useState('')
  const [pending, setPending] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const inputRef = useRef<HTMLInputElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Keep the newest message in view as the transcript grows.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [exchanges, pending])

  function fillExample(example: string) {
    setQuestion(example)
    inputRef.current?.focus()
  }

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

  const isEmpty = exchanges.length === 0 && !pending

  return (
    <div className="flex flex-col gap-4">
      {/* Transcript */}
      <div className="flex min-h-48 flex-col gap-4">
        {isEmpty && (
          <Card className="flex flex-col items-center gap-4 px-6 py-10 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-600 text-white shadow-sm">
              <IconSparkles className="h-6 w-6" />
            </span>
            <div>
              <p className="text-sm font-semibold">Chat with your notes &amp; tasks</p>
              <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                Ask a question — answers are grounded in what you’ve saved.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => fillExample(example)}
                  className="rounded-full border border-slate-200 px-3 py-1.5 text-xs text-slate-600 transition-colors hover:border-accent-300 hover:bg-accent-50 hover:text-accent-700 dark:border-slate-700 dark:text-slate-300 dark:hover:border-accent-500/50 dark:hover:bg-accent-500/10 dark:hover:text-accent-300"
                >
                  {example}
                </button>
              ))}
            </div>
          </Card>
        )}

        {exchanges.map((exchange, index) => (
          <div key={index} className="flex flex-col gap-2">
            <div className="max-w-[85%] self-end rounded-2xl rounded-br-md bg-accent-600 px-4 py-2.5 text-sm text-white shadow-sm">
              {exchange.question}
            </div>
            <div className="max-w-[85%] self-start rounded-2xl rounded-bl-md border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-800 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100">
              <p className="whitespace-pre-wrap">{exchange.answer}</p>
              <Sources sources={exchange.sources} />
            </div>
          </div>
        ))}

        {/* In-flight question */}
        {pending && (
          <div className="flex flex-col gap-2">
            <div className="max-w-[85%] self-end rounded-2xl rounded-br-md bg-accent-600 px-4 py-2.5 text-sm text-white shadow-sm">
              {pending}
            </div>
            <div className="max-w-[85%] self-start rounded-2xl rounded-bl-md border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-800 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <Thinking />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Error banner */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Composer */}
      <form
        onSubmit={handleAsk}
        className={cn(
          'sticky bottom-4 flex items-center gap-2 rounded-xl border border-slate-200 bg-white p-2 shadow-sm',
          'focus-within:border-accent-500 focus-within:ring-2 focus-within:ring-accent-500/30',
          'dark:border-slate-800 dark:bg-slate-900',
        )}
      >
        <input
          ref={inputRef}
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about your notes and tasks…"
          maxLength={1000}
          className="flex-1 bg-transparent px-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none dark:text-slate-100 dark:placeholder:text-slate-500"
        />
        <Button
          type="submit"
          loading={loading}
          disabled={!question.trim()}
          icon={!loading && <IconSend className="h-4 w-4" />}
        >
          Ask
        </Button>
      </form>
    </div>
  )
}

export default ChatView
