import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiErrorMessage } from '../api/client.js'
import { Alert, Button, Card, Field, inputClass } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters.')
      return
    }
    setBusy(true)
    try {
      await register({ name, email, password })
      navigate('/app')
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not create the account.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center px-4 py-10">
      <Card className="w-full max-w-md p-8">
        <p className="text-xs uppercase tracking-[0.2em] text-mint">Get started</p>
        <h1 className="mt-2 font-display text-3xl">Create account</h1>
        <p className="mt-2 text-sm text-white/55">Sign up to upload a resume and get a personalized career plan.</p>
        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          {error ? <Alert>{error}</Alert> : null}
          <Field label="Full name">
            <input className={inputClass()} required minLength={1} value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Email">
            <input className={inputClass()} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Password" hint="At least 6 characters">
            <input
              className={inputClass()}
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          <Field label="Confirm password">
            <input
              className={inputClass()}
              type="password"
              required
              minLength={6}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </Field>
          <Button className="w-full" disabled={busy}>
            {busy ? 'Creating account…' : 'Sign up'}
          </Button>
        </form>
        <p className="mt-5 text-sm text-white/50">
          Already registered?{' '}
          <Link className="text-mint" to="/login">
            Log in
          </Link>
        </p>
      </Card>
    </div>
  )
}
