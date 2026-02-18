import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ErrorBoundary } from './components/common'
import { Spinner } from './components/common'

// Code-split all page components for smaller initial bundle
const Dashboard = lazy(() =>
  import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })),
)
const ScanResults = lazy(() =>
  import('./pages/ScanResults').then((m) => ({ default: m.ScanResults })),
)
const ScanDetail = lazy(() =>
  import('./pages/ScanDetail').then((m) => ({ default: m.ScanDetail })),
)
const DebateDetail = lazy(() =>
  import('./pages/DebateDetail').then((m) => ({ default: m.DebateDetail })),
)
const TickerDeepDive = lazy(() =>
  import('./pages/TickerDeepDive').then((m) => ({
    default: m.TickerDeepDive,
  })),
)
const Watchlist = lazy(() =>
  import('./pages/Watchlist').then((m) => ({ default: m.Watchlist })),
)
const Universe = lazy(() =>
  import('./pages/Universe').then((m) => ({ default: m.Universe })),
)
const Settings = lazy(() =>
  import('./pages/Settings').then((m) => ({ default: m.Settings })),
)

function PageLoader() {
  return (
    <div className="flex h-screen w-full items-center justify-center">
      <Spinner size="lg" />
    </div>
  )
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/scan" element={<ScanResults />} />
            <Route path="/scan/:id" element={<ScanDetail />} />
            <Route path="/debate/:id" element={<DebateDetail />} />
            <Route path="/ticker/:symbol" element={<TickerDeepDive />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/universe" element={<Universe />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App
