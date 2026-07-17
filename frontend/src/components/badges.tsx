/* src/components/badges.tsx
 *
 * The shared category/priority pills. Notes and Search both display a note's
 * AI-assigned category and priority, so the color maps and markup live here in
 * one place rather than being copied per view. The style maps are keyed by the
 * `Category`/`Priority` unions, so adding a value to the backend enum surfaces
 * here as a missing-key type error until a color is chosen. */

import type { Category, Priority } from '../api/types'

/** Tailwind classes per category (Other/unknown reads as neutral slate). */
const CATEGORY_STYLES: Record<Category, string> = {
  Work: 'bg-blue-100 text-blue-700',
  Study: 'bg-violet-100 text-violet-700',
  Personal: 'bg-pink-100 text-pink-700',
  Shopping: 'bg-amber-100 text-amber-700',
  Finance: 'bg-emerald-100 text-emerald-700',
  Health: 'bg-rose-100 text-rose-700',
  Ideas: 'bg-yellow-100 text-yellow-700',
  Coding: 'bg-indigo-100 text-indigo-700',
  Meetings: 'bg-cyan-100 text-cyan-700',
  Travel: 'bg-teal-100 text-teal-700',
  Other: 'bg-slate-100 text-slate-600',
}

/** Tailwind classes per priority. */
const PRIORITY_STYLES: Record<Priority, string> = {
  High: 'bg-red-100 text-red-700',
  Medium: 'bg-amber-100 text-amber-700',
  Low: 'bg-slate-100 text-slate-600',
}

/** Base pill used by the specific badges below. */
function Pill({ className, children }: { className: string; children: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
      {children}
    </span>
  )
}

export function CategoryBadge({ category }: { category: Category }) {
  return <Pill className={CATEGORY_STYLES[category]}>{category}</Pill>
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  return <Pill className={PRIORITY_STYLES[priority]}>{priority}</Pill>
}
