import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider } from '@/auth/AuthProvider'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { DashboardPage } from '@/pages/DashboardPage'
import { DashboardSectionPage } from '@/pages/DashboardSectionPage'
import { HomePage } from '@/pages/HomePage'
import { MarketplaceDataPage } from '@/pages/MarketplaceDataPage'
import { LoginPage } from '@/pages/LoginPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { StatusPage } from '@/pages/StatusPage'
import { TrainModelPage } from '@/pages/TrainModelPage'
import { dashboardNav } from '@/config/dashboard'
import { ThemeProvider } from '@/theme/ThemeProvider'

/**
 * Application routes.
 *
 * Phase 3 adds authentication and the protected dashboard shell. The dashboard
 * sections beyond the overview render an honest placeholder until their
 * feature phase lands.
 */
export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/status" element={<StatusPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard/marketplace-data"
              element={
                <ProtectedRoute>
                  <MarketplaceDataPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard/train"
              element={
                <ProtectedRoute>
                  <TrainModelPage />
                </ProtectedRoute>
              }
            />

            {dashboardNav
              .filter((item) => !item.available)
              .map((item) => (
                <Route
                  key={item.to}
                  path={item.to}
                  element={
                    <ProtectedRoute>
                      <DashboardSectionPage />
                    </ProtectedRoute>
                  }
                />
              ))}

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}
