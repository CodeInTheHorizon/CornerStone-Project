import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { StatusPage } from '@/pages/StatusPage'

/**
 * Application routes.
 *
 * Phase 1 exposes a single placeholder route. The landing page (Phase 2),
 * auth routes (Phase 3) and the protected dashboard are added later.
 */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<StatusPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
