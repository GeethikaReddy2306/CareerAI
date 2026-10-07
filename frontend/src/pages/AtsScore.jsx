import { useState } from 'react'
import { apiErrorMessage, resumeApi } from '../api/client.js'
import { ResumeGate, ResumePicker } from '../components/ResumePicker.jsx'
import { Alert, Button, Card, Chip, PageHeader, ScoreBadge, Spinner } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { markProgress } from '../lib/progress.js'

export default function AtsScore() {
  return (
    <ResumeGate>
      {(state) => <AtsInner {...state} />}
    </ResumeGate>
  )
}

function CategoryCard({ category }) {
  const [open, setOpen] = useState(category.status === 'issues')
  const issues = category.issues || []
  const hasIssues = category.status === 'issues' || issues.length > 0

  return (
    <div className="rounded-xl border border-line px-4 py-3">
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="flex items-center gap-2 font-medium">
          {hasIssues ? (
            <span className="text-rose-500">✕</span>
          ) : (
            <span className="text-emerald-500">✓</span>
          )}
          {category.name}
        </span>
        <Chip tone={hasIssues ? 'rose' : 'mint'}>
          {hasIssues ? 'issues' : 'pass'}
        </Chip>
      </button>
      {open ? (
        <div className="mt-3 space-y-2 border-t border-line pt-3 text-sm">
          {hasIssues ? (
            <ul className="space-y-2">
              {issues.map((issue, i) => (
                <li key={i}>
                  <p className="font-medium text-white/90">{issue.message}</p>
                  {issue.detail ? <p className="mt-0.5 text-white/50">{issue.detail}</p> : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-white/50">No issues in this category.</p>
          )}
        </div>
      ) : null}
    </div>
  )
}

function AtsInner({ resumes, selectedId, select }) {
  const { user } = useAuth()
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function run() {
    if (!selectedId) return
    setBusy(true)
    setError('')
    try {
      const { data } = await resumeApi.ats(selectedId)
      setResult(data)
      markProgress(user.id, 'ats')
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const breakdown = result?.breakdown || {}
  const categories = result?.categories || []

  return (
    <div>
      <PageHeader
        eyebrow="ATS"
        title="ATS resume score"
        description="Deterministic compatibility score for keywords, formatting, skills, and resume structure."
        actions={
          <Button disabled={busy || !selectedId} onClick={run}>
            {busy ? 'Scoring…' : 'Generate ATS score'}
          </Button>
        }
      />
      <div className="mb-6 max-w-md">
        <ResumePicker resumes={resumes} selectedId={selectedId} onChange={select} />
      </div>
      {error ? <div className="mb-4"><Alert>{error}</Alert></div> : null}
      {busy ? <Spinner /> : null}
      {result ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="p-5">
            <ScoreBadge score={result.score} />
            <div className="mt-4 flex flex-wrap gap-2">
              {(result.detected_sections || []).map((s) => <Chip key={s} tone="mint">{s}</Chip>)}
            </div>
          </Card>

          <Card className="p-5 lg:col-span-2">
            <h2 className="font-display text-xl">Breakdown</h2>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {Object.entries(breakdown).map(([k, v]) => (
                <div key={k} className="rounded-xl border border-line px-3 py-2">
                  <p className="text-xs uppercase tracking-wide text-white/40">{k.replaceAll('_', ' ')}</p>
                  <p className="font-display text-lg">{v}</p>
                </div>
              ))}
            </div>
          </Card>

          {categories.length ? (
            <Card className="p-5 lg:col-span-3">
              <h2 className="font-display text-xl">Detailed checks</h2>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {categories.map((cat) => <CategoryCard key={cat.name} category={cat} />)}
              </div>
            </Card>
          ) : null}

          <Card className="p-5">
            <h2 className="font-display text-xl">Missing sections</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {(result.missing_sections || []).length
                ? result.missing_sections.map((s) => <Chip key={s} tone="rose">{s}</Chip>)
                : <p className="text-sm text-white/50">None detected.</p>}
            </div>
          </Card>

          <Card className="p-5 lg:col-span-2">
            <h2 className="font-display text-xl">Improvements</h2>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-white/70">
              {(result.suggestions || []).map((s) => <li key={s}>{s}</li>)}
            </ul>
          </Card>
        </div>
      ) : null}
    </div>
  )
}