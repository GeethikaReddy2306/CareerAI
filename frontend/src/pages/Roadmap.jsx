import { useState } from 'react'
import { apiErrorMessage, careerApi } from '../api/client.js'
import { ResumeGate, ResumePicker } from '../components/ResumePicker.jsx'
import { Alert, Button, Card, Chip, Field, inputClass, PageHeader, Spinner } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { getProgress, markProgress, toggleCompletedSkill } from '../lib/progress.js'

export default function Roadmap() {
  return (
    <ResumeGate>
      {(state) => <MapInner {...state} />}
    </ResumeGate>
  )
}

function MapInner({ resumes, selectedId, select }) {
  const { user } = useAuth()
  const [role, setRole] = useState('Senior Backend Developer')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(getProgress(user.id).completedSkills || [])

  async function run(e) {
    e?.preventDefault?.()
    setBusy(true)
    setError('')
    try {
      const { data } = await careerApi.createRoadmap({ resume_id: selectedId, target_role: role })
      setResult(data)
      markProgress(user.id, 'roadmap')
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function loadSaved() {
    setBusy(true)
    setError('')
    try {
      const { data } = await careerApi.getRoadmap(selectedId)
      setResult(data)
    } catch (err) {
      setError(apiErrorMessage(err, 'No saved roadmap yet. Generate one first.'))
    } finally {
      setBusy(false)
    }
  }

  function toggle(skill) {
    setDone(toggleCompletedSkill(user.id, skill))
  }

  return (
    <div>
      <PageHeader
        eyebrow="Plan"
        title="Personalized career roadmap"
        description="A step-by-step path based on your current level. Beginner skills you already have are skipped."
      />
      <form className="mb-8 grid gap-4 md:grid-cols-3" onSubmit={run}>
        <ResumePicker resumes={resumes} selectedId={selectedId} onChange={select} />
        <Field label="Target career / role">
          <input className={inputClass()} required minLength={2} value={role} onChange={(e) => setRole(e.target.value)} />
        </Field>
        <div className="flex items-end gap-2">
          <Button disabled={busy || !selectedId}>{busy ? 'Building…' : 'Generate roadmap'}</Button>
          <Button type="button" variant="ghost" disabled={busy || !selectedId} onClick={loadSaved}>
            Load saved
          </Button>
        </div>
      </form>
      {error ? <div className="mb-4"><Alert>{error}</Alert></div> : null}
      {busy ? <Spinner /> : null}
      {result ? (
        <div className="space-y-4">
          <p className="text-sm text-white/55">
            Current level: <span className="text-mint">{result.current_level}</span> → {result.target_role}
          </p>
          {(result.roadmap || []).map((phase) => (
            <Card key={phase.phase} className="p-5">
              <div className="flex flex-wrap items-center gap-2">
                <Chip tone="mint">Phase {phase.phase}</Chip>
                <Chip>{phase.priority} priority</Chip>
                <Chip tone="gold">{phase.estimated_weeks} weeks</Chip>
              </div>
              <h2 className="mt-3 font-display text-2xl">{phase.title}</h2>
              <p className="mt-1 text-white/65">{phase.description}</p>
              <div className="mt-4 grid gap-4 md:grid-cols-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-white/40">Skills</p>
                  <div className="mt-2 space-y-2">
                    {(phase.skills || []).map((s) => (
                      <label key={s} className="flex items-center gap-2 text-sm">
                        <input type="checkbox" checked={done.includes(s)} onChange={() => toggle(s)} />
                        <span className={done.includes(s) ? 'text-mint line-through' : ''}>{s}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-white/40">Topics</p>
                  <ul className="mt-2 list-disc pl-5 text-sm text-white/70">
                    {(phase.topics || []).map((t) => <li key={t}>{t}</li>)}
                  </ul>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-white/40">Projects</p>
                  <ul className="mt-2 list-disc pl-5 text-sm text-white/70">
                    {(phase.projects || []).map((t) => <li key={t}>{t}</li>)}
                  </ul>
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : null}
    </div>
  )
}
