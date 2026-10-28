import { useState } from 'react'
import { apiErrorMessage, careerApi } from '../api/client.js'
import { ResumeGate, ResumePicker } from '../components/ResumePicker.jsx'
import { Alert, Button, Card, Chip, Field, inputClass, PageHeader, Spinner } from '../components/ui.jsx'

export default function Roadmap() {
  return <ResumeGate>{(state) => <MapInner {...state} />}</ResumeGate>
}

function MapInner({ resumes, selectedId, select }) {
  const [role, setRole] = useState('Backend Developer')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState([])

  async function run(event) {
    event?.preventDefault()
    setBusy(true); setError('')
    try {
      const { data } = await careerApi.createRoadmap({ resume_id: selectedId, target_role: role })
      setResult(data); setDone(data.completed_skills || [])
    } catch (err) { setError(apiErrorMessage(err)) } finally { setBusy(false) }
  }

  async function loadSaved() {
    setBusy(true); setError('')
    try {
      const { data } = await careerApi.getRoadmap(selectedId)
      setResult(data); setDone(data.completed_skills || [])
    } catch (err) { setError(apiErrorMessage(err, 'No saved roadmap yet. Generate one first.')) } finally { setBusy(false) }
  }

  async function toggle(skill) {
    if (!result?.id) return
    const previous = done
    const next = done.includes(skill) ? done.filter((item) => item !== skill) : [...done, skill]
    setDone(next)
    try {
      const { data } = await careerApi.updateRoadmapProgress(result.id, next)
      setDone(data.completed_skills || [])
    } catch (err) {
      setDone(previous); setError(apiErrorMessage(err, 'Could not save progress. Please try again.'))
    }
  }

  return <div>
    <PageHeader eyebrow="Plan" title="Personalized career roadmap" description="Phases are generated from verified skill gaps. Estimates assume 6–8 focused hours per week." />
    <form className="mb-8 grid gap-4 md:grid-cols-3" onSubmit={run}>
      <ResumePicker resumes={resumes} selectedId={selectedId} onChange={select} />
      <Field label="Target career / role"><input className={inputClass()} required minLength={2} value={role} onChange={(event) => setRole(event.target.value)} /></Field>
      <div className="flex items-end gap-2"><Button disabled={busy || !selectedId}>{busy ? 'Building…' : 'Generate roadmap'}</Button><Button type="button" variant="ghost" disabled={busy || !selectedId} onClick={loadSaved}>Load saved</Button></div>
    </form>
    {error ? <div className="mb-4"><Alert>{error}</Alert></div> : null}
    {busy ? <Spinner /> : null}
    {result ? <div className="space-y-4">
      <p className="text-sm text-white/55">Current level: <span className="text-mint">{result.current_level}</span> → {result.target_role}</p>
      {(result.roadmap || []).map((phase) => <Card key={phase.phase} className="p-5">
        <div className="flex flex-wrap items-center gap-2"><Chip tone="mint">Phase {phase.phase}</Chip><Chip>{phase.priority} priority</Chip><Chip tone="gold">{phase.estimated_weeks} weeks</Chip></div>
        <h2 className="mt-3 font-display text-2xl">{phase.title}</h2><p className="mt-1 text-white/65">{phase.description}</p>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div><p className="text-xs uppercase tracking-wide text-white/40">Skills</p><div className="mt-2 space-y-2">{(phase.skills || []).map((skill) => <label key={skill} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={done.includes(skill)} onChange={() => toggle(skill)} /><span className={done.includes(skill) ? 'text-mint line-through' : ''}>{skill}</span></label>)}</div></div>
          <List title="Topics" items={phase.topics} />
          <List title="Projects" items={phase.projects} />
          <List title="Completion criteria" items={phase.completion_criteria} />
        </div>
      </Card>)}
    </div> : null}
  </div>
}

function List({ title, items = [] }) {
  return <div><p className="text-xs uppercase tracking-wide text-white/40">{title}</p><ul className="mt-2 list-disc pl-5 text-sm text-white/70">{items.map((item) => <li key={item}>{item}</li>)}</ul></div>
}
