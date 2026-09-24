import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, BarChart3, Compass, Database, Layers, TrendingUp, Bell, ArrowRight } from 'lucide-react'

import { dashboardNav } from '@/config/dashboard'

const navResults = dashboardNav.map((item) => ({
  id: item.to,
  label: item.label,
  description: item.description,
  to: item.to,
  type: 'page' as const,
}))

const iconMap: Record<string, React.ElementType> = {
  '/dashboard': BarChart3,
  '/dashboard/predictor': Compass,
  '/dashboard/compare': BarChart3,
  '/dashboard/trends': TrendingUp,
  '/dashboard/analytics': BarChart3,
  '/dashboard/marketplace-data': Database,
  '/dashboard/train': Layers,
  '/dashboard/alerts': Bell,
}

export function GlobalSearch() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    if (open) {
      setQuery('')
      setSelected(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  const filtered = query
    ? navResults.filter((r) => r.label.toLowerCase().includes(query.toLowerCase()) || r.description.toLowerCase().includes(query.toLowerCase()))
    : navResults

  function go(to: string) {
    navigate(to)
    setOpen(false)
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelected((s) => Math.min(s + 1, filtered.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSelected((s) => Math.max(s - 1, 0)) }
    else if (e.key === 'Enter' && filtered[selected]) { go(filtered[selected].to) }
    else if (e.key === 'Escape') setOpen(false)
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[60] flex items-start justify-center pt-[15vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
        >
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setOpen(false)} />

          <motion.div
            className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-border-hair bg-surface shadow-pop"
            initial={{ opacity: 0, scale: 0.95, y: -8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -8 }}
            transition={{ duration: 0.15 }}
          >
            <div className="flex items-center gap-3 border-b border-border-hair px-4 py-3">
              <Search className="size-4 text-muted" />
              <input
                ref={inputRef}
                type="text"
                placeholder="Search pages, features..."
                value={query}
                onChange={(e) => { setQuery(e.target.value); setSelected(0) }}
                onKeyDown={onKeyDown}
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-subtle"
              />
              <kbd className="rounded border border-border-hair bg-background-alt px-1.5 py-0.5 text-[10px] font-medium text-subtle">
                ESC
              </kbd>
            </div>

            <div className="max-h-72 overflow-y-auto py-2">
              {filtered.length === 0 && (
                <p className="px-4 py-6 text-center text-sm text-muted">No results found</p>
              )}
              {filtered.map((result, i) => {
                const Icon = iconMap[result.to] ?? BarChart3
                return (
                  <button
                    key={result.id}
                    onClick={() => go(result.to)}
                    onMouseEnter={() => setSelected(i)}
                    className={`flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors ${i === selected ? 'bg-accent-soft text-accent-text' : 'text-foreground hover:bg-background-alt'}`}
                  >
                    <Icon className="size-4 shrink-0 text-muted" />
                    <div className="min-w-0 flex-1">
                      <span className="font-medium">{result.label}</span>
                      <p className="truncate text-xs text-muted">{result.description}</p>
                    </div>
                    <ArrowRight className="size-3 shrink-0 text-subtle" />
                  </button>
                )
              })}
            </div>

            <div className="border-t border-border-hair px-4 py-2 text-[11px] text-subtle">
              <span className="mr-3">
                <kbd className="rounded border border-border-hair px-1 py-0.5 text-[9px]">↑↓</kbd> navigate
              </span>
              <span className="mr-3">
                <kbd className="rounded border border-border-hair px-1 py-0.5 text-[9px]">↵</kbd> open
              </span>
              <span>
                <kbd className="rounded border border-border-hair px-1 py-0.5 text-[9px]">esc</kbd> close
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
