/* src/components/badges.tsx
 *
 * The shared category/priority pills. Notes and Search both display a note's
 * AI-assigned category and priority, so the color maps and markup live here in
 * one place rather than being copied per view. They render on the shared Badge
 * primitive (components/ui) so shape/spacing stay consistent app-wide; this file
 * only owns the color mapping.
 *
 * Each entry carries BOTH a light and a dark treatment (a soft tint + readable
 * text on each theme), so the pills stay legible when the app is in dark mode.
 * The style maps are keyed by the `Category`/`Priority` unions, so adding a
 * value to the backend enum surfaces here as a missing-key type error until a
 * color is chosen. */

import type { Category, Priority } from '../api/types'
import { Badge } from './ui'

/** Light + dark classes per category (Other/unknown reads as neutral slate). */
const CATEGORY_STYLES: Record<Category, string> = {
  Work: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300',
  Study: 'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300',
  Personal: 'bg-pink-100 text-pink-700 dark:bg-pink-500/15 dark:text-pink-300',
  Shopping: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  Finance: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
  Health: 'bg-rose-100 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300',
  Ideas: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-500/15 dark:text-yellow-300',
  Coding: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300',
  Meetings: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-300',
  Travel: 'bg-teal-100 text-teal-700 dark:bg-teal-500/15 dark:text-teal-300',
  Other: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
}

/** Light + dark classes per priority. */
const PRIORITY_STYLES: Record<Priority, string> = {
  High: 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300',
  Medium: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
  Low: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
}

export function CategoryBadge({ category }: { category: Category }) {
  return <Badge className={CATEGORY_STYLES[category]}>{category}</Badge>
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <Badge className={PRIORITY_STYLES[priority]}>{priority}</Badge>
}
