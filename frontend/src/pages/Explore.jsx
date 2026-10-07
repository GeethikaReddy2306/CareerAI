import { useState } from 'react'
import { apiErrorMessage, careerApi } from '../api/client.js'
import { ResumeGate, ResumePicker } from '../components/ResumePicker.jsx'
import { Alert, Button, Card, Chip, Field, inputClass, PageHeader, ScoreBadge, Spinner } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { markProgress } from '../lib/progress.js'

const starters = [
  'Data Analyst',
  'Frontend Developer',
  'DevOps Engineer',
  'Machine Learning Engineer',
  'Product Manager',
  'Senior Backend Developer',
]

export default function Explore() {
  return (
    <ResumeGate>
      {(state) => <ExploreInner {...state} />}
    </ResumeGate>
  )
}

function ExploreInner({ resumes, selectedId, select }) {
  const { user } = useAuth()
  const [role, setRole] = useState('Data Analyst')
  const [mode, setMode] = useState('switch')
  const [gap, setGap] = useState(null)
  const [ready, setReady] = useState(null)
  const [map, setMap] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function run(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const [gapRes, readyRes, mapRes] = await Promise.all([
        careerApi.skillGap({ resume_id: selectedId, target_role: role }),
        careerApi.readiness(selectedId, role),
        careerApi.createRoadmap({ resume_id: selectedId, target_role: role }),
      ])
      setGap(gapRes.data)
      setReady(readyRes.data)
      setMap(mapRes.data)
      markProgress(user.id, 'skillGap')
      markProgress(user.id, 'roadmap')
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Exploration"
        title="Career paths & switching"
        description="Pick a target career. The system uses your current resume so transferable skills stay, missing skills surface, and the roadmap skips what you already know."
      />
      <div className="mb-4 flex flex-wrap gap-2">
        <Button type="button" variant={mode === 'switch' ? 'primary' : 'ghost'} onClick={() => setMode('switch')}>
          Career switch
        </Button>
        <Button type="button" variant={mode === 'upskill' ? 'primary' : 'ghost'} onClick={() => setMode('upskill')}>
          Experienced upskilling
        </Button>
      </div>
      <p className="mb-6 max-w-3xl text-sm text-white/55">
        {mode === 'switch'
          ? 'Starting something new? We map transferable skills and the shortest path into the new role.'
          : 'Already experienced? Recommendations emphasize advanced topics such as system design, cloud, and performance — not beginner tutorials.'}
      </p>
      <form className="mb-8 grid gap-4 md:grid-cols-3" onSubmit={run}>
        <ResumePicker resumes={resumes} selectedId={selectedId} onChange={select} />
        <Field label="Target career">
          <input className={inputClass()} required minLength={2} value={role} onChange={(e) => setRole(e.target.value)} />
        </Field>
        <div className="flex items-end">
          <Button disabled={busy || !selectedId}>{busy ? 'Mapping path…' : 'Build path'}</Button>
        </div>
      </form>
      <div className="mb-6 flex flex-wrap gap-2">
        {starters.map((s) => (
          <button key={s} type="button" onClick={() => setRole(s)} className="rounded-full border border-line px-3 py-1 text-xs hover:border-mint">
            {s}
          </button>
        ))}
      </div>
      {error ? <Alert>{error}</Alert> : null}
      {busy ? <Spinner label="Analyzing transferable skills…" /> : null}
      {ready && gap ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="p-5">
            <ScoreBadge score={ready.overall_score} />
            <p className="mt-2 text-sm text-white/50">Readiness for {ready.target_role}</p>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-lg">Transferable / strong</h2>
            <div className="mt-2 flex flex-wrap gap-2">{gap.strong?.map((s) => <Chip key={s} tone="mint">{s}</Chip>)}</div>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-lg">Must learn</h2>
            <div className="mt-2 flex flex-wrap gap-2">{gap.missing?.map((s) => <Chip key={s} tone="rose">{s}</Chip>)}</div>
          </Card>
          <Card className="p-5 lg:col-span-3">
            <h2 className="font-display text-lg">Personalized learning</h2>
            <p className="mt-1 text-sm text-white/50">
              Priority list changes as you tick skills complete on the Roadmap page.
            </p>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {gap.prioritized_skills?.slice(0, 8).map((item) => (
                <div key={item.skill} className="rounded-xl border border-line p-3">
                  <p className="font-medium">{item.skill}</p>
                  <p className="text-sm text-white/55">{item.reason}</p>
                </div>
              ))}
            </div>
          </Card>
          {(map?.roadmap || []).map((phase) => (
            <Card key={phase.phase} className="p-5">
              <Chip tone="mint">Phase {phase.phase}</Chip>
              <h3 className="mt-2 font-display text-xl">{phase.title}</h3>
              <p className="mt-1 text-sm text-white/60">{phase.description}</p>
            </Card>
          ))}
        </div>
      ) : null}
    </div>
  )
}
