import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiErrorMessage } from '../api/client.js'
import { Alert, Button, Card, Field, inputClass } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login({ email, password })
      navigate('/app')
    } catch (err) {
      setError(apiErrorMessage(err, 'Login failed. Check your email and password.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center px-4 py-10">
      <Card className="w-full max-w-md p-8">
        <p className="text-xs uppercase tracking-[0.2em] text-mint">Welcome back</p>
        <h1 className="mt-2 font-display text-3xl">Log in</h1>
        <p className="mt-2 text-sm text-white/55">Access your career workspace, resumes, and roadmaps.</p>
        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          {error ? <Alert>{error}</Alert> : null}
          <Field label="Email">
            <input className={inputClass()} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Password">
            <input
              className={inputClass()}
              type="password"
              required
              minLength={1}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <Button className="w-full" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
        <p className="mt-5 text-sm text-white/50">
          New here?{' '}
          <Link className="text-mint" to="/register">
            Create an account
          </Link>
        </p>
      </Card>
    </div>
  )
}
