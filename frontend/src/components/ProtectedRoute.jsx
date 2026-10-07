import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { Spinner } from './ui.jsx'

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner label="Loading your session…" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return children
}
