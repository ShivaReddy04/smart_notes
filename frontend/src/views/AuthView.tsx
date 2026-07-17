/* src/views/AuthView.tsx
 *
 * The unauthenticated screen: a single card that toggles between "Sign in" and
 * "Create account". It calls useAuth().login / register; on success the auth
 * provider flips to authenticated and App swaps in the real app, so this
 * component has no success branch of its own. Backend failures (bad credentials
 * 401, duplicate email 409, validation 422) surface inline via the ApiError
 * message. Styled with the shared UI kit for light/dark parity. */

import { useState } from 'react'

import { Button, Card, IconSparkles, Input } from '../components/ui'
import { useAuth } from '../lib/auth'
import { errorMessage } from '../lib/errors'

function AuthView() {
  const { login, register } = useAuth()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isRegister = mode === 'register'

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!email.trim() || !password) return
    setSubmitting(true)
    setError(null)
    try {
      const credentials = { email: email.trim(), password }
      if (isRegister) await register(credentials)
      else await login(credentials)
      // Success: AuthProvider flips status → App renders the workspace.
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  function switchMode() {
    setMode(isRegister ? 'login' : 'register')
    setError(null)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 dark:bg-slate-950">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-600 text-white shadow-sm">
            <IconSparkles className="h-6 w-6" />
          </span>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
              AI Smart Notes
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {isRegister ? 'Create your account' : 'Sign in to your workspace'}
            </p>
          </div>
        </div>

        <Card className="p-6">
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-slate-300">
              Email
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-slate-600 dark:text-slate-300">
              Password
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={isRegister ? 'At least 8 characters' : 'Your password'}
                autoComplete={isRegister ? 'new-password' : 'current-password'}
                minLength={isRegister ? 8 : undefined}
                required
              />
            </label>

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300">
                {error}
              </div>
            )}

            <Button
              type="submit"
              loading={submitting}
              disabled={!email.trim() || !password}
              className="mt-1 w-full"
            >
              {isRegister ? 'Create account' : 'Sign in'}
            </Button>
          </form>
        </Card>

        <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
          {isRegister ? 'Already have an account?' : 'New here?'}{' '}
          <button
            type="button"
            onClick={switchMode}
            className="font-medium text-accent-600 hover:text-accent-500 dark:text-accent-400"
          >
            {isRegister ? 'Sign in' : 'Create one'}
          </button>
        </p>
      </div>
    </div>
  )
}

export default AuthView
