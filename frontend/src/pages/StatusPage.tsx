/**
 * Phase 1 placeholder page.
 *
 * Its only job is to prove the frontend/backend wiring: env config, the
 * typed API client and CORS. It is replaced by the real landing page in
 * Phase 2 and carries no product content.
 */

import { Panel, StatusPill } from '@/components'
import { env } from '@/config/env'
import { useHealth } from '@/hooks/useHealth'

export function StatusPage() {
  const { data, error, status, reload } = useHealth()

  return (
    <main className="mx-auto flex min-h-screen max-w-shell flex-col justify-center px-6 py-16">
      <p className="text-xs font-medium tracking-[0.2em] text-subtle uppercase">
        Phase 1 — Project Foundation
      </p>

      <h1 className="mt-4 text-4xl font-semibold sm:text-5xl">
        {env.appName}
      </h1>
      <p className="mt-3 max-w-xl text-muted">
        Backend and frontend skeleton. The public landing page, authentication,
        marketplace collection and the ML pipeline are not implemented yet.
      </p>

      <Panel className="mt-10 max-w-xl">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-sm font-semibold">Backend connection</h2>

          {status === 'loading' && <StatusPill tone="idle">Checking…</StatusPill>}
          {status === 'ready' && <StatusPill tone="ok">Connected</StatusPill>}
          {status === 'error' && <StatusPill tone="down">Unreachable</StatusPill>}
        </div>

        {status === 'ready' && data && (
          <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            {[
              ['API', data.app],
              ['Version', data.version],
              ['Environment', data.environment],
              ['Database', data.database],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-subtle">{label}</dt>
                <dd className="mt-0.5 font-mono text-foreground">{value}</dd>
              </div>
            ))}
          </dl>
        )}

        {status === 'error' && (
          <div className="mt-5 text-sm">
            <p className="text-muted">{error}</p>
            <button
              type="button"
              onClick={reload}
              className="mt-4 rounded-card bg-accent px-4 py-2 text-sm font-medium text-accent-ink transition-colors hover:bg-accent-hover"
            >
              Retry
            </button>
          </div>
        )}
      </Panel>
    </main>
  )
}
