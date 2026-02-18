import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ErrorBoundary } from './components/common'
import {
  Dashboard,
  ScanResults,
  ScanDetail,
  DebateDetail,
  TickerDeepDive,
  Watchlist,
  Universe,
  Settings,
} from './pages'

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
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
      </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App
