/* src/lib/errors.ts
 *
 * One shared place to turn any thrown value into a user-facing string. Every
 * view calls this in its catch blocks so error handling reads the same across
 * the app: an `ApiError` shows the backend's `detail` message, any other Error
 * shows its message, and anything else shows a safe generic fallback. */

import { ApiError } from '../api/client'

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Something went wrong.'
}
