/**
 * Top-bar account menu: who is signed in, with which role, and sign out.
 * Closes on Escape (returning focus to its button), outside click and navigation.
 */

import { useEffect, useId, useRef, useState } from 'react'

import { roleLabel } from '@/auth/permissions'
import { Icon } from '@/components/Icon'
import { useAuth } from '@/hooks/useAuth'

export function AccountMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  const menuId = useId()
  const initial = (user?.full_name ?? user?.email ?? '?').charAt(0).toUpperCase()

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setOpen(false); button.current?.focus() }
    }
    const onPointer = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('pointerdown', onPointer)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('pointerdown', onPointer)
    }
  }, [open])

  return (
    <div ref={root} className="relative">
      <button
        ref={button}
        type="button"
        aria-label="Account menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-1.5 rounded-full border border-border-hair bg-surface p-0.5 pr-2 text-muted transition-colors duration-200 ease-standard hover:border-accent hover:text-accent-text"
      >
        <span aria-hidden="true" className="grid size-7 place-items-center rounded-full bg-linear-to-br from-brand to-brand-deep text-xs font-semibold text-white">
          {initial}
        </span>
        <Icon name="chevron-down" className={`size-4 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div
          id={menuId}
          className="absolute right-0 z-40 mt-2 w-64 max-w-[calc(100vw-2.5rem)] rounded-panel border border-border-hair bg-surface-raised p-2 shadow-pop"
        >
          <div className="border-b border-border-hair px-3 pt-2 pb-3">
            <p className="truncate text-sm font-semibold">{user?.full_name ?? 'Signed in'}</p>
            <p className="mt-0.5 truncate text-xs text-subtle">{user?.email}</p>
            <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent-text">
              <Icon name="lock" className="size-3" />
              Role: {roleLabel(user?.role)}
            </p>
          </div>
          <button
            type="button"
            onClick={() => { setOpen(false); void logout() }}
            className="mt-1 flex w-full items-center gap-2.5 rounded-card px-3 py-2 text-sm text-muted transition-colors duration-200 hover:bg-signal-down/10 hover:text-signal-down"
          >
            <Icon name="logout" className="size-4" />
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
