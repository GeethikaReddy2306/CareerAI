import { useState } from 'react'
import { apiErrorMessage, resumeApi } from '../api/client.js'
import { ResumeGate, ResumePicker } from '../components/ResumePicker.jsx'
import { Alert, Button, Card, Chip, PageHeader, Spinner } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { markProgress } from '../lib/progress.js'

export default function Analyzer() {
  return (
    <ResumeGate>
      {(state) => <AnalyzerInner {...state} />}
    </ResumeGate>
  )
}

function AnalyzerInner({ resumes, selectedId, select }) {
  const { user } = useAuth()
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function run(force = false) {
    if (!selectedId) return
    setBusy(true)
    setError('')
    try {
      const { data } = await resumeApi.analyze(selectedId, force)
      setResult(data.data || data)
      markProgress(user.id, 'analyzed')
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const profile = result

  return (
    <div>
      <PageHeader
        eyebrow="Profile"
        title="AI resume analyzer"
        description="Extract skills, education, projects, certifications, experience, strengths, and improvement areas."
        actions={
          <div className="flex gap-2">
            <Button variant="ghost" disabled={busy || !selectedId} onClick={() => run(true)}>
              Refresh
            </Button>
            <Button disabled={busy || !selectedId} onClick={() => run(false)}>
              {busy ? 'Analyzing…' : 'Analyze'}
            </Button>
          </div>
        }
      />
      <div className="mb-6 max-w-md">
        <ResumePicker resumes={resumes} selectedId={selectedId} onChange={select} />
      </div>
      {error ? <div className="mb-4"><Alert>{error}</Alert></div> : null}
      {busy ? <Spinner label="Reading your resume…" /> : null}
      {profile ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="p-5 lg:col-span-2">
            <p className="text-xs uppercase tracking-[0.16em] text-mint">{profile.experience_level || 'Level'}</p>
            <p className="mt-2 text-white/75">{profile.summary || 'No summary extracted.'}</p>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-xl">Skills</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {(profile.skills || []).map((s) => (
                <Chip key={s} tone="mint">{s}</Chip>
              ))}
            </div>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-xl">Suggested roles</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {(profile.suggested_roles || []).map((s) => (
                <Chip key={s} tone="gold">{s}</Chip>
              ))}
            </div>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-xl">Strengths</h2>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-white/70">
              {(profile.strengths || []).map((s) => <li key={s}>{s}</li>)}
            </ul>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-xl">Improve</h2>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-white/70">
              {(profile.weaknesses || []).map((s) => <li key={s}>{s}</li>)}
            </ul>
          </Card>
          <Card className="p-5 lg:col-span-2">
            <h2 className="font-display text-xl">Work experience</h2>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              {(profile.work_experience || []).map((job, i) => (
                <div key={i} className="rounded-xl border border-line p-3">
                  <p className="font-medium">{job.role} · {job.company}</p>
                  <p className="text-xs text-white/40">{job.duration}</p>
                  <ul className="mt-2 list-disc pl-4 text-sm text-white/65">
                    {(job.responsibilities || []).slice(0, 4).map((r) => <li key={r}>{r}</li>)}
                  </ul>
                </div>
              ))}
            </div>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-xl">Projects</h2>
            <div className="mt-3 space-y-3">
              {(profile.projects || []).map((p, i) => (
                <div key={i}>
                  <p className="font-medium">{p.name}</p>
                  <p className="text-sm text-white/60">{p.description}</p>
                </div>
              ))}
            </div>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-xl">Education & certifications</h2>
            <ul className="mt-3 space-y-2 text-sm text-white/70">
              {(profile.education || []).map((e, i) => (
                <li key={i}>{e.degree} — {e.institution} {e.year ? `(${e.year})` : ''}</li>
              ))}
            </ul>
            <div className="mt-3 flex flex-wrap gap-2">
              {(profile.certifications || []).map((c) => (
                <Chip key={String(c)}>{typeof c === 'string' ? c : JSON.stringify(c)}</Chip>
              ))}
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  )
}
