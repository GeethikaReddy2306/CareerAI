import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import { useAuth } from './context/AuthContext.jsx'
import Analyzer from './pages/Analyzer.jsx'
import AtsScore from './pages/AtsScore.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Explore from './pages/Explore.jsx'
import InterviewPrep from './pages/InterviewPrep.jsx'
import JobMatch from './pages/JobMatch.jsx'
import Landing from './pages/Landing.jsx'
import Login from './pages/Login.jsx'
import MockInterview from './pages/MockInterview.jsx'
import Readiness from './pages/Readiness.jsx'
import Register from './pages/Register.jsx'
import Resumes from './pages/Resumes.jsx'
import Roadmap from './pages/Roadmap.jsx'
import SkillGap from './pages/SkillGap.jsx'

export default function App() {
  const { user, loading } = useAuth()

  return (
    <Routes>
      <Route path="/" element={user && !loading ? <Navigate to="/app" replace /> : <Landing />} />
      <Route path="/login" element={user && !loading ? <Navigate to="/app" replace /> : <Login />} />
      <Route path="/register" element={user && !loading ? <Navigate to="/app" replace /> : <Register />} />
      <Route
        path="/app"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="resumes" element={<Resumes />} />
        <Route path="analyzer" element={<Analyzer />} />
        <Route path="ats" element={<AtsScore />} />
        <Route path="job-match" element={<JobMatch />} />
        <Route path="skill-gap" element={<SkillGap />} />
        <Route path="readiness" element={<Readiness />} />
        <Route path="roadmap" element={<Roadmap />} />
        <Route path="explore" element={<Explore />} />
        <Route path="interview" element={<InterviewPrep />} />
        <Route path="mock" element={<MockInterview />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
