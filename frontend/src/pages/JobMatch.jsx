import { useState } from 'react'
import { apiErrorMessage, careerApi } from '../api/client.js'
import { ResumeGate, ResumePicker } from '../components/ResumePicker.jsx'
import { Alert, Button, Card, Chip, Field, inputClass, PageHeader, ScoreBadge, Spinner } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { markProgress } from '../lib/progress.js'

export default function JobMatch() {
  return (
    <ResumeGate>
      {(state) => <JobInner {...state} />}
    </ResumeGate>
  )
}

function JobInner({ resumes, selectedId, select }) {
  const { user } = useAuth()
  const [jd, setJd] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function run(e) {
    e.preventDefault()
    if (!selectedId) return
    setBusy(true)
    setError('')
    try {
      const { data } = await careerApi.jobAnalysis({ resume_id: selectedId, job_description: jd })
      setResult(data)
      markProgress(user.id, 'jobMatch')
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Job opportunity"
        title="Resume + job description"
        description="Compare your resume with a specific JD. See match score, missing skills, and interview topics."
      />
      <form className="mb-8 grid gap-4 lg:grid-cols-[280px_1fr]" onSubmit={run}>
        <ResumePicker resumes={resumes} selectedId={selectedId} onChange={select} />
        <Field label="Paste the job description">
          <textarea
            className={inputClass('min-h-40')}
            minLength={10}
            required
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            placeholder="Paste the role, required skills, and responsibilities…"
          />
        </Field>
        <div className="lg:col-span-2">
          <Button disabled={busy || !selectedId}>{busy ? 'Comparing…' : 'Analyze match'}</Button>
        </div>
      </form>
      {error ? <div className="mb-4"><Alert>{error}</Alert></div> : null}
      {busy ? <Spinner /> : null}
      {result ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="p-5">
            <ScoreBadge score={result.match_score} />
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-lg">Matched</h2>
            <div className="mt-2 flex flex-wrap gap-2">
              {(result.matched_skills || []).map((s) => <Chip key={s} tone="mint">{s}</Chip>)}
            </div>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-lg">Missing</h2>
            <div className="mt-2 flex flex-wrap gap-2">
              {(result.missing_skills || []).map((s) => <Chip key={s} tone="rose">{s}</Chip>)}
            </div>
          </Card>
          <Card className="p-5">
            <h2 className="font-display text-lg">Partial</h2>
            <div className="mt-2 flex flex-wrap gap-2">
              {(result.partial_skills || []).map((s) => <Chip key={s} tone="gold">{s}</Chip>)}
            </div>
          </Card>
          <Card className="p-5 lg:col-span-2">
            <h2 className="font-display text-lg">Interview topics</h2>
            <ul className="mt-2 list-disc pl-5 text-sm text-white/70">
              {(result.interview_topics || []).map((s) => <li key={s}>{s}</li>)}
            </ul>
          </Card>
          <Card className="p-5 lg:col-span-3">
            <h2 className="font-display text-lg">Recommendations</h2>
            <ul className="mt-2 list-disc pl-5 text-sm text-white/70">
              {(result.recommendations || []).map((s) => <li key={s}>{s}</li>)}
            </ul>
          </Card>
        </div>
      ) : null}
    </div>
  )
}
