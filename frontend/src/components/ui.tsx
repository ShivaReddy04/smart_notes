/* src/components/ui.tsx
 *
 * The app's shared UI kit — the small set of primitives every screen is built
 * from, so the product reads as one coherent design system instead of each view
 * hand-rolling its own buttons and inputs. Styling (spacing, radius, focus
 * rings, light/dark surfaces) lives HERE once; views compose these and stay
 * about behavior, not Tailwind soup.
 *
 * Everything is theme-aware: each primitive carries its own `dark:` variants, so
 * flipping the `.dark` class on <html> (see lib/theme.ts) restyles the whole UI
 * with no per-view work.
 *
 * Contents: cn() classname helper · icon set (inline SVG, currentColor) ·
 * Spinner · Button · IconButton · Input · Textarea · Card · Badge · EmptyState.
 */

import type {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SVGProps,
  TextareaHTMLAttributes,
} from 'react'

/* --------------------------------------------------------------------------
 * cn — tiny classname joiner. Filters out falsey values so callers can write
 * conditional classes inline (cn('base', active && 'on')) without a dependency.
 * ------------------------------------------------------------------------ */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}

/* --------------------------------------------------------------------------
 * Icons — a curated inline set (Feather-style, 24px grid, currentColor stroke)
 * so icons inherit text color and theme automatically, with zero icon-font or
 * external dependency. Size them with a `className` (e.g. "h-4 w-4").
 * ------------------------------------------------------------------------ */
type IconProps = SVGProps<SVGSVGElement>

function Svg({ children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  )
}

export const IconPlus = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
)
export const IconEdit = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z" />
  </Svg>
)
export const IconPin = (p: IconProps) => (
  <Svg {...p}>
    <path d="M9 4h6l-1 7 3 3v2H7v-2l3-3-1-7Z" />
    <path d="M12 16v5" />
  </Svg>
)
export const IconTrash = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 6h18" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    <path d="M10 11v6M14 11v6" />
  </Svg>
)
export const IconSearch = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.3-4.3" />
  </Svg>
)
export const IconChat = (p: IconProps) => (
  <Svg {...p}>
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z" />
  </Svg>
)
export const IconNote = (p: IconProps) => (
  <Svg {...p}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
    <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" />
  </Svg>
)
export const IconTask = (p: IconProps) => (
  <Svg {...p}>
    <path d="m9 11 3 3L22 4" />
    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
  </Svg>
)
export const IconSun = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </Svg>
)
export const IconMoon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
  </Svg>
)
export const IconClose = (p: IconProps) => (
  <Svg {...p}>
    <path d="M18 6 6 18M6 6l12 12" />
  </Svg>
)
export const IconImage = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <circle cx="9" cy="9" r="1.5" />
    <path d="m21 15-5-5L5 21" />
  </Svg>
)
export const IconSend = (p: IconProps) => (
  <Svg {...p}>
    <path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7Z" />
  </Svg>
)
export const IconSparkles = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 3l1.9 5.6L19.5 10l-5.6 1.4L12 17l-1.9-5.6L4.5 10l5.6-1.4L12 3Z" />
  </Svg>
)
export const IconMenu = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 12h18M3 6h18M3 18h18" />
  </Svg>
)

/* --------------------------------------------------------------------------
 * Spinner — inline loading indicator that inherits the current text color.
 * ------------------------------------------------------------------------ */
export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn('animate-spin', className)}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path
        d="M22 12a10 10 0 0 0-10-10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  )
}

/* --------------------------------------------------------------------------
 * Button — the primary action element. Variants cover the four roles the app
 * needs (primary/secondary/ghost/danger); `loading` swaps in a spinner and
 * disables the button so a click can't fire twice.
 * ------------------------------------------------------------------------ */
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ButtonSize = 'sm' | 'md'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  icon?: ReactNode
}

const BUTTON_BASE =
  'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-accent-500/50 disabled:cursor-not-allowed disabled:opacity-50'

const BUTTON_SIZES: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-xs',
  md: 'h-10 px-4 text-sm',
}

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-accent-600 text-white shadow-sm hover:bg-accent-500',
  secondary:
    'border border-slate-300 bg-white text-slate-700 shadow-sm hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700',
  ghost:
    'text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white',
  danger: 'bg-red-600 text-white shadow-sm hover:bg-red-500',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(BUTTON_BASE, BUTTON_SIZES[size], BUTTON_VARIANTS[variant], className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Spinner className="h-4 w-4" /> : icon}
      {children}
    </button>
  )
}

/* --------------------------------------------------------------------------
 * IconButton — a square, icon-only control (edit/pin/delete on cards). Always
 * takes a `label` for accessibility since it has no visible text.
 * ------------------------------------------------------------------------ */
interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string
  variant?: 'ghost' | 'danger' | 'active'
}

const ICON_BUTTON_VARIANTS: Record<NonNullable<IconButtonProps['variant']>, string> = {
  ghost:
    'text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-100',
  danger:
    'text-slate-500 hover:bg-red-50 hover:text-red-600 dark:text-slate-400 dark:hover:bg-red-950/40 dark:hover:text-red-400',
  active:
    'text-accent-600 hover:bg-accent-50 dark:text-accent-400 dark:hover:bg-accent-900/40',
}

export function IconButton({
  label,
  variant = 'ghost',
  className,
  ...props
}: IconButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cn(
        'inline-flex h-8 w-8 items-center justify-center rounded-lg transition-colors outline-none focus-visible:ring-2 focus-visible:ring-accent-500/50 disabled:cursor-not-allowed disabled:opacity-50',
        ICON_BUTTON_VARIANTS[variant],
        className,
      )}
      {...props}
    />
  )
}

/* --------------------------------------------------------------------------
 * Input / Textarea — form controls with a consistent focus ring and dark
 * surface. They spread all native props, so `type`, `value`, `onChange`, etc.
 * work exactly as expected; only styling is standardized.
 * ------------------------------------------------------------------------ */
const FIELD_BASE =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 shadow-sm outline-none transition focus:border-accent-500 focus:ring-2 focus:ring-accent-500/30 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100 dark:placeholder:text-slate-500'

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(FIELD_BASE, className)} {...props} />
}

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(FIELD_BASE, 'resize-y', className)} {...props} />
}

/* --------------------------------------------------------------------------
 * Card — the surface every note/task/panel sits on. One rounded, bordered,
 * subtly shadowed container that adapts to the theme.
 * ------------------------------------------------------------------------ */
export function Card({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900',
        className,
      )}
      {...props}
    />
  )
}

/* --------------------------------------------------------------------------
 * Badge — a generic pill. The specific category/priority/status badges layer
 * their color maps on top of this in badges.tsx and the views.
 * ------------------------------------------------------------------------ */
export function Badge({
  className,
  children,
}: {
  className?: string
  children: ReactNode
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
        className,
      )}
    >
      {children}
    </span>
  )
}

/* --------------------------------------------------------------------------
 * EmptyState — the friendly placeholder a list shows when it has no items yet,
 * so an empty screen looks designed rather than broken.
 * ------------------------------------------------------------------------ */
export function EmptyState({
  icon,
  title,
  hint,
}: {
  icon?: ReactNode
  title: string
  hint?: string
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-slate-300 px-6 py-14 text-center dark:border-slate-700">
      {icon && <div className="text-slate-400 dark:text-slate-500">{icon}</div>}
      <p className="text-sm font-medium text-slate-600 dark:text-slate-300">{title}</p>
      {hint && <p className="max-w-xs text-xs text-slate-400 dark:text-slate-500">{hint}</p>}
    </div>
  )
}
