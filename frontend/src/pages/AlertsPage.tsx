import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bell, Plus, Trash2, ToggleLeft, ToggleRight } from 'lucide-react'

import { DashboardLayout } from '@/components/dashboard/DashboardLayout'
import { EmptyState } from '@/components/dashboard/StateViews'
import { Panel } from '@/components/Panel'
import { Button } from '@/components/Button'
import { Field } from '@/components/Field'
import { FormAlert } from '@/components/FormAlert'
import { useAuth } from '@/hooks/useAuth'
import { PLATFORM_KEYS } from '@/lib/platforms'
import { title } from '@/lib/predictionFormat'
import * as alertService from '@/services/alertService'
import type { Alert } from '@/services/alertService'

export function AlertsPage() {
  const { token } = useAuth()
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const [productName, setProductName] = useState('')
  const [platform, setPlatform] = useState('amazon')
  const [condition, setCondition] = useState<'below' | 'above'>('below')
  const [threshold, setThreshold] = useState('')
  const [creating, setCreating] = useState(false)

  async function load() {
    if (!token) return
    try {
      const res = await alertService.fetchAlerts(token)
      setAlerts(res.alerts)
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load alerts')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [token])

  async function handleCreate() {
    if (!token || !productName || !threshold) return
    setCreating(true)
    try {
      await alertService.createAlert(token, {
        product_name: productName,
        platform,
        condition,
        threshold: parseFloat(threshold),
      })
      setProductName('')
      setThreshold('')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create alert')
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(id: number) {
    if (!token) return
    await alertService.deleteAlert(token, id)
    await load()
  }

  async function handleToggle(alert: Alert) {
    if (!token) return
    await alertService.updateAlert(token, alert.id, { active: !alert.active })
    await load()
  }

  const control = 'w-full rounded-card border border-border-hair bg-background px-3 py-2.5 text-sm text-foreground transition-colors duration-200 focus:border-accent'

  return (
    <DashboardLayout title="Price Alerts">
      <div className="space-y-6">
        <Panel>
          <h2 className="text-lg font-semibold">Create Alert</h2>
          <p className="mt-1 text-sm text-muted">Get notified when a product price crosses your threshold.</p>

          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Product name" name="alert-product" value={productName} onChange={setProductName} />
            <label className="text-sm text-muted">
              Platform
              <select className={control} value={platform} onChange={(e) => setPlatform(e.target.value)}>
                {PLATFORM_KEYS.map((p) => <option key={p} value={p}>{title(p)}</option>)}
              </select>
            </label>
            <label className="text-sm text-muted">
              Condition
              <select className={control} value={condition} onChange={(e) => setCondition(e.target.value as 'below' | 'above')}>
                <option value="below">Price drops below</option>
                <option value="above">Price rises above</option>
              </select>
            </label>
            <Field label="Threshold (INR)" name="alert-threshold" type="number" value={threshold} onChange={setThreshold} />
          </div>

          <Button className="mt-4" onClick={handleCreate} disabled={creating || !productName || !threshold}>
            <Plus className="size-4" />
            {creating ? 'Creating...' : 'Create Alert'}
          </Button>
        </Panel>

        {error && <FormAlert>{error}</FormAlert>}

        {!loading && alerts.length === 0 && (
          <EmptyState icon="alert" title="No alerts yet" action={{ label: 'Create your first alert', onClick: () => document.querySelector<HTMLInputElement>('[name=alert-product]')?.focus() }}>
            Set up price alerts to get notified when marketplace prices change.
          </EmptyState>
        )}

        <AnimatePresence>
          {alerts.map((alert) => (
            <motion.div
              key={alert.id}
              className="surface-card flex flex-wrap items-center gap-4 p-5"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, height: 0 }}
              layout
            >
              <div className="flex items-center gap-3">
                <Bell className={`size-5 ${alert.triggered_at ? 'text-signal-warn' : 'text-muted'}`} />
                <div>
                  <p className="text-sm font-semibold">{alert.product_name}</p>
                  <p className="text-xs text-muted">
                    {title(alert.platform)} · {alert.condition === 'below' ? 'Below' : 'Above'} {alert.threshold} {alert.currency}
                  </p>
                </div>
              </div>

              <div className="ml-auto flex items-center gap-3">
                {alert.triggered_at && (
                  <span className="rounded-full bg-signal-warn/10 px-2.5 py-1 text-xs font-medium text-signal-warn">
                    Triggered: {alert.triggered_value?.toLocaleString()} {alert.currency}
                  </span>
                )}
                <button onClick={() => handleToggle(alert)} className="text-muted transition-colors hover:text-foreground" title={alert.active ? 'Disable' : 'Enable'}>
                  {alert.active ? <ToggleRight className="size-6 text-signal-ok" /> : <ToggleLeft className="size-6" />}
                </button>
                <button onClick={() => handleDelete(alert.id)} className="text-muted transition-colors hover:text-signal-down" title="Delete">
                  <Trash2 className="size-4" />
                </button>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </DashboardLayout>
  )
}
