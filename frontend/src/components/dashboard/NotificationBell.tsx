import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Bell, X } from 'lucide-react'

import { useAuth } from '@/hooks/useAuth'
import * as alertService from '@/services/alertService'
import type { Alert } from '@/services/alertService'

export function NotificationBell() {
  const { token } = useAuth()
  const [triggered, setTriggered] = useState<Alert[]>([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!token) return
    alertService.fetchTriggered(token).then(setTriggered).catch(() => {})
    const id = setInterval(() => {
      alertService.fetchTriggered(token).then(setTriggered).catch(() => {})
    }, 30_000)
    return () => clearInterval(id)
  }, [token])

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-label="Notifications"
        className="relative grid size-9 shrink-0 place-items-center rounded-full text-muted transition-colors hover:bg-background-alt hover:text-foreground"
      >
        <Bell className="size-[18px]" />
        {triggered.length > 0 && (
          <motion.span
            className="absolute right-1 top-1 grid size-4 place-items-center rounded-full bg-signal-warn text-[9px] font-bold text-white"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 400, damping: 15 }}
          >
            {triggered.length > 9 ? '9+' : triggered.length}
          </motion.span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="absolute right-0 top-full z-50 mt-2 w-80 overflow-hidden rounded-xl border border-border-hair bg-surface shadow-pop"
            initial={{ opacity: 0, y: -4, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.95 }}
            transition={{ duration: 0.15 }}
          >
            <div className="flex items-center justify-between border-b border-border-hair px-4 py-3">
              <h3 className="text-sm font-semibold">Triggered Alerts</h3>
              <button onClick={() => setOpen(false)} className="text-muted hover:text-foreground">
                <X className="size-4" />
              </button>
            </div>

            <div className="max-h-64 overflow-y-auto">
              {triggered.length === 0 ? (
                <p className="px-4 py-6 text-center text-xs text-muted">No triggered alerts</p>
              ) : (
                triggered.slice(0, 10).map((alert) => (
                  <div key={alert.id} className="border-b border-border-hair px-4 py-3 last:border-0">
                    <p className="text-sm font-medium">{alert.product_name}</p>
                    <p className="text-xs text-muted">
                      {alert.condition === 'below' ? 'Dropped below' : 'Rose above'} {alert.threshold} {alert.currency}
                      {alert.triggered_value != null && ` · Now: ${alert.triggered_value.toLocaleString()}`}
                    </p>
                  </div>
                ))
              )}
            </div>

            <Link
              to="/dashboard/alerts"
              onClick={() => setOpen(false)}
              className="block border-t border-border-hair px-4 py-2.5 text-center text-xs font-medium text-accent-text transition-colors hover:bg-background-alt"
            >
              View all alerts
            </Link>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
