import { Routes, Route, Link } from 'react-router-dom'
import HomePage from './pages/HomePage'
import ResultManagerPage from './pages/ResultManagerPage'
import SubmissionStatus from './components/SubmissionStatus'
import SubmissionBar from './components/SubmissionBar'
import QaDialog from './components/QaDialog'

export default function App() {
  return (
    <div className="min-h-screen bg-base-200">
      <header className="navbar bg-base-100 shadow-sm px-4">
        <div className="flex-1">
          <span className="text-lg font-semibold">Random42</span>
        </div>
        <SubmissionBar />
        <Link to="/" className="btn btn-link btn-sm">
          Search Page
        </Link>
        <Link to="/result-manager" className="btn btn-link btn-sm">
          Result Manager
        </Link>
      </header>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/result-manager" element={<ResultManagerPage />} />
      </Routes>
      {/* Global DRES status toast (connection + last verdict). */}
      <SubmissionStatus />
      {/* a card's Q */}
      <QaDialog />
    </div>
  )
}
