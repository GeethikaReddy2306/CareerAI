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

// ─── Category cards (expandable, per-line issue feedback) ───────────────────

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

// ─── Main inner component ────────────────────────────────────────────────────

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
        description="A deterministic compatibility estimate with documented weighted components and actionable improvements."
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
          {/* Score + detected sections */}
          <Card className="p-5">
            <ScoreBadge score={result.score} />
            <p className="mt-3 text-xs text-white/45">{result.calculation_note}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {(result.detected_sections || []).map((s) => <Chip key={s} tone="mint">{s}</Chip>)}
            </div>
          </Card>

          {/* Breakdown grid */}
          <Card className="p-5 lg:col-span-2">
            <h2 className="font-display text-xl">Breakdown</h2>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {Object.entries(breakdown).map(([k, v]) => (
                <div key={k} className="rounded-xl border border-line px-3 py-2">
                  <p className="text-xs uppercase tracking-wide text-white/40">{k.replaceAll('_', ' ')}</p>
                  <p className="font-display text-lg">{v}/100</p>
                </div>
              ))}
            </div>
          </Card>

          {/* Itemized category feedback (Quantifying Impact, Repetition, etc.) */}
          {categories.length ? (
            <Card className="p-5 lg:col-span-3">
              <h2 className="font-display text-xl">Detailed checks</h2>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {categories.map((cat) => <CategoryCard key={cat.name} category={cat} />)}
              </div>
            </Card>
          ) : null}

          {/* Missing sections */}
          <Card className="p-5">
            <h2 className="font-display text-xl">Missing sections</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {(result.missing_sections || []).length
                ? result.missing_sections.map((s) => <Chip key={s} tone="rose">{s}</Chip>)
                : <p className="text-sm text-white/50">No standard sections are missing based on the extracted text.</p>}
            </div>
          </Card>

          {/* Suggestions */}
          <Card className="p-5 lg:col-span-2">
            <h2 className="font-display text-xl">Improvements</h2>
            <div className="mt-3 space-y-3">
              {(result.improvements || []).map((item) => (
                <div key={item.issue} className="rounded-xl border border-line p-3 text-sm">
                  <div className="flex items-center gap-2"><p className="font-medium">{item.issue}</p><Chip tone={item.priority === 'High' ? 'rose' : item.priority === 'Medium' ? 'gold' : 'neutral'}>{item.priority}</Chip></div>
                  <p className="mt-1 text-white/55">Why it matters: {item.why_it_matters}</p>
                  <p className="mt-1 text-mint">Next step: {item.suggested_correction}</p>
                </div>
              ))}
              {!result.improvements?.length ? <p className="text-sm text-white/50">No improvements were returned. Retry the analysis; no result is being inferred.</p> : null}
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  )
}
