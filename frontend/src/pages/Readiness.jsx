import { useState } from 'react'
import { apiErrorMessage, careerApi } from '../api/client.js'
import { ResumeGate, ResumePicker } from '../components/ResumePicker.jsx'
import { Alert, Button, Card, Field, inputClass, PageHeader, ScoreBadge, Spinner } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { markProgress } from '../lib/progress.js'

export default function Readiness() {
  return (
    <ResumeGate>
      {(state) => <ReadyInner {...state} />}
    </ResumeGate>
  )
}

function ReadyInner({ resumes, selectedId, select }) {
  const { user } = useAuth()
  const [role, setRole] = useState('Backend Developer')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function run(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const { data } = await careerApi.readiness(selectedId, role)
      setResult(data)
      markProgress(user.id, 'readiness')
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const b = result?.breakdown || {}

  return (
    <div>
      <PageHeader
        eyebrow="Score"
        title="Career readiness"
        description="Overall readiness for a selected role, with strengths and areas that still need work."
      />
      <form className="mb-8 grid gap-4 md:grid-cols-3" onSubmit={run}>
        <ResumePicker resumes={resumes} selectedId={selectedId} onChange={select} />
        <Field label="Target role">
          <input className={inputClass()} required minLength={2} value={role} onChange={(e) => setRole(e.target.value)} />
        </Field>
        <div className="flex items-end">
          <Button disabled={busy || !selectedId}>{busy ? 'Scoring…' : 'Compute score'}</Button>
        </div>
      </form>
      {error ? <Alert>{error}</Alert> : null}
      {busy ? <Spinner /> : null}
      {result ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="p-5">
            <ScoreBadge score={result.overall_score} />
            <p className="mt-3 text-sm text-white/50">{result.target_role}</p>
          </Card>
          <Card className="p-5 lg:col-span-2">
            <h2 className="font-display text-lg">Factor breakdown</h2>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {Object.entries(b).map(([k, v]) => (
                <div key={k} className="rounded-xl border border-line px-3 py-2">
                  <p className="text-xs uppercase tracking-wide text-white/40">{k.replaceAll('_', ' ')}</p>
                  <p className="font-display text-lg">{v}</p>
                </div>
              ))}
            </div>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-lg">Strengths</h2>
            <ul className="mt-2 list-disc pl-5 text-sm text-white/70">
              {result.strengths?.map((s) => <li key={s}>{s}</li>)}
            </ul>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-lg">Improve</h2>
            <ul className="mt-2 list-disc pl-5 text-sm text-white/70">
              {result.areas_to_improve?.map((s) => <li key={s}>{s}</li>)}
            </ul>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-lg">Recommendations</h2>
            <ul className="mt-2 list-disc pl-5 text-sm text-white/70">
              {result.recommendations?.map((s) => <li key={s}>{s}</li>)}
            </ul>
          </Card>
        </div>
      ) : null}
    </div>
  )
}
