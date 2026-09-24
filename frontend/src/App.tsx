import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'

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
import { PredictorPage } from '@/pages/PredictorPage'
import { AnalyticsPage } from '@/pages/AnalyticsPage'
import { AlertsPage } from '@/pages/AlertsPage'
import { ComparePage } from '@/pages/ComparePage'
import { dashboardNav } from '@/config/dashboard'
import { ThemeProvider } from '@/theme/ThemeProvider'
import { SearchPage } from '@/pages/SearchPage'
import { ProductCatalogPage } from '@/pages/ProductCatalogPage'
import { ProductDetailPage } from '@/pages/ProductDetailPage'

const pageVariants = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.25, ease: [0.2, 0, 0, 1] as const } },
  exit: { opacity: 0, y: -4, transition: { duration: 0.15, ease: [0.4, 0, 1, 1] as const } },
} as const

function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <motion.div variants={pageVariants} initial="initial" animate="animate" exit="exit">
      {children}
    </motion.div>
  )
}

function AnimatedRoutes() {
  const location = useLocation()

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/" element={<PageShell><HomePage /></PageShell>} />
        <Route path="/status" element={<PageShell><StatusPage /></PageShell>} />
        <Route path="/login" element={<PageShell><LoginPage /></PageShell>} />
        <Route path="/register" element={<PageShell><RegisterPage /></PageShell>} />

        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <PageShell><DashboardPage /></PageShell>
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/marketplace-data"
          element={
            <ProtectedRoute>
              <PageShell><MarketplaceDataPage /></PageShell>
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/train"
          element={
            <ProtectedRoute>
              <PageShell><TrainModelPage /></PageShell>
            </ProtectedRoute>
          }
        />

        <Route path="/dashboard/predictor" element={<ProtectedRoute><PageShell><PredictorPage /></PageShell></ProtectedRoute>} />
        <Route path="/dashboard/compare" element={<ProtectedRoute><PageShell><ComparePage /></PageShell></ProtectedRoute>} />
        <Route path="/dashboard/alerts" element={<ProtectedRoute><PageShell><AlertsPage /></PageShell></ProtectedRoute>} />
        <Route path="/dashboard/trends" element={<ProtectedRoute><PageShell><AnalyticsPage key="trends" mode="trends" /></PageShell></ProtectedRoute>} />
        <Route path="/dashboard/analytics" element={<ProtectedRoute><PageShell><AnalyticsPage key="comparison" mode="comparison" /></PageShell></ProtectedRoute>} />
        <Route path="/dashboard/search" element={<ProtectedRoute><PageShell><SearchPage /></PageShell></ProtectedRoute>} />
        <Route path="/dashboard/products" element={<ProtectedRoute><PageShell><ProductCatalogPage /></PageShell></ProtectedRoute>} />
        <Route path="/dashboard/product/:productId" element={<ProtectedRoute><PageShell><ProductDetailPage /></PageShell></ProtectedRoute>} />

        {dashboardNav
          .filter((item) => !item.available)
          .map((item) => (
            <Route
              key={item.to}
              path={item.to}
              element={
                <ProtectedRoute>
                  <PageShell><DashboardSectionPage /></PageShell>
                </ProtectedRoute>
              }
            />
          ))}

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AnimatePresence>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <AnimatedRoutes />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}
