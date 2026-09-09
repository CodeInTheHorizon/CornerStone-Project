import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { HomePage } from '@/pages/HomePage'
import { NotAvailablePage } from '@/pages/NotAvailablePage'
import { StatusPage } from '@/pages/StatusPage'
import { ThemeProvider } from '@/theme/ThemeProvider'

/**
 * Application routes.
 *
 * Phase 2 adds the public landing page. Real auth routes and the protected
 * dashboard replace the placeholders in Phase 3.
 */
export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/status" element={<StatusPage />} />

          {/* Linked from the navbar; implemented in Phase 3. */}
          <Route path="/login" element={<NotAvailablePage />} />
          <Route path="/register" element={<NotAvailablePage />} />
          <Route path="/dashboard" element={<NotAvailablePage />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  )
}
