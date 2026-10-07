import { useState } from 'react'
import { apiErrorMessage, careerApi } from '../api/client.js'
import { ResumeGate, ResumePicker } from '../components/ResumePicker.jsx'
import { Alert, Button, Card, Chip, Field, inputClass, PageHeader, Spinner } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { markProgress } from '../lib/progress.js'

export default function SkillGap() {
  return (
    <ResumeGate>
      {(state) => <GapInner {...state} />}
    </ResumeGate>
  )
}

function GapInner({ resumes, selectedId, select }) {
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
      const { data } = await careerApi.skillGap({ resume_id: selectedId, target_role: role })
      setResult(data)
      markProgress(user.id, 'skillGap')
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Gaps"
        title="Skill gap analysis"
        description="Compare current skills with a target role. Skills are grouped as strong, intermediate, weak, or missing — then prioritized."
      />
      <form className="mb-8 grid gap-4 md:grid-cols-3" onSubmit={run}>
        <ResumePicker resumes={resumes} selectedId={selectedId} onChange={select} />
        <Field label="Target role">
          <input className={inputClass()} required minLength={2} value={role} onChange={(e) => setRole(e.target.value)} />
        </Field>
        <div className="flex items-end">
          <Button disabled={busy || !selectedId}>{busy ? 'Analyzing…' : 'Find gaps'}</Button>
        </div>
      </form>
      {error ? <Alert>{error}</Alert> : null}
      {busy ? <Spinner /> : null}
      {result ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="p-5">
            <h2 className="font-display text-lg">Strong</h2>
            <div className="mt-2 flex flex-wrap gap-2">{result.strong?.map((s) => <Chip key={s} tone="mint">{s}</Chip>)}</div>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-lg">Intermediate</h2>
            <div className="mt-2 flex flex-wrap gap-2">{result.intermediate?.map((s) => <Chip key={s} tone="blue">{s}</Chip>)}</div>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-lg">Weak</h2>
            <div className="mt-2 flex flex-wrap gap-2">{result.weak?.map((s) => <Chip key={s} tone="gold">{s}</Chip>)}</div>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-lg">Missing</h2>
            <div className="mt-2 flex flex-wrap gap-2">{result.missing?.map((s) => <Chip key={s} tone="rose">{s}</Chip>)}</div>
          </Card>
          <Card className="p-5 lg:col-span-2">
            <h2 className="font-display text-lg">Learn first</h2>
            <div className="mt-3 space-y-2">
              {(result.prioritized_skills || []).map((item) => (
                <div key={item.skill} className="rounded-xl border border-line p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium">{item.skill}</p>
                    <Chip tone={item.priority === 'High' ? 'rose' : item.priority === 'Medium' ? 'gold' : 'neutral'}>
                      {item.priority}
                    </Chip>
                    <Chip>{item.category}</Chip>
                  </div>
                  <p className="mt-1 text-sm text-white/60">{item.reason}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  )
}
