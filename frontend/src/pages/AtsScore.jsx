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

// ─── AI Review section ───────────────────────────────────────────────────────

function AIReview({ review }) {
  if (!review) return null

  const isUnavailable =
    review.clarity_score == null &&
    review.impact_score == null &&
    !review.grammar_issues?.length &&
    !review.weak_bullets?.length

  if (isUnavailable) {
    return (
      <Card className="p-5 lg:col-span-3">
        <h2 className="font-display text-xl">AI Review</h2>
        <p className="mt-3 text-sm text-white/50">{review.overall_feedback}</p>
      </Card>
    )
  }

  return (
    <Card className="p-5 lg:col-span-3">
      <h2 className="font-display text-xl">AI Review</h2>

      {/* Clarity / Impact scores */}
      {(review.clarity_score != null || review.impact_score != null) && (
        <div className="mt-3 flex flex-wrap gap-3">
          {review.clarity_score != null && (
            <div className="rounded-xl border border-line px-3 py-2">
              <p className="text-xs uppercase tracking-wide text-white/40">Clarity</p>
              <p className="font-display text-lg">{review.clarity_score}</p>
            </div>
          )}
          {review.impact_score != null && (
            <div className="rounded-xl border border-line px-3 py-2">
              <p className="text-xs uppercase tracking-wide text-white/40">Impact</p>
              <p className="font-display text-lg">{review.impact_score}</p>
            </div>
          )}
        </div>
      )}

      {/* Overall feedback */}
      {review.overall_feedback && (
        <p className="mt-4 text-sm text-white/70">{review.overall_feedback}</p>
      )}

      {/* Weak bullets */}
      {review.weak_bullets?.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-white/40">
            Weak bullets
          </h3>
          <ul className="mt-2 space-y-3">
            {review.weak_bullets.map((b, i) => (
              <li key={i} className="rounded-lg border border-line p-3 text-sm">
                <p className="text-white/50 line-through">{b.line}</p>
                <p className="mt-1 text-white/70 italic">{b.why_weak}</p>
                <p className="mt-1 text-emerald-400">→ {b.improved_version}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Grammar issues */}
      {review.grammar_issues?.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-white/40">
            Grammar &amp; spelling
          </h3>
          <ul className="mt-2 space-y-3">
            {review.grammar_issues.map((g, i) => (
              <li key={i} className="rounded-lg border border-line p-3 text-sm">
                <p className="text-white/50">{g.line}</p>
                <p className="mt-1 text-rose-400">{g.issue}</p>
                <p className="mt-1 text-emerald-400">Fix: {g.fix}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Missing impact keywords */}
      {review.missing_impact_keywords?.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-white/40">
            Missing impact keywords
          </h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {review.missing_impact_keywords.map((kw) => (
              <Chip key={kw} tone="rose">{kw}</Chip>
            ))}
          </div>
        </div>
      )}
    </Card>
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
        description="AI-powered compatibility score for keywords, formatting, skills, structure, and itemized per-line feedback."
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
                  <p className="font-display text-lg">{v}</p>
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
                : <p className="text-sm text-white/50">None detected.</p>}
            </div>
          </Card>

          {/* Suggestions */}
          <Card className="p-5 lg:col-span-2">
            <h2 className="font-display text-xl">Improvements</h2>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-white/70">
              {(result.suggestions || []).map((s) => <li key={s}>{s}</li>)}
            </ul>
          </Card>

          {/* AI deep-review (optional — shown only when ai_review is present) */}
          <AIReview review={result.ai_review} />
        </div>
      ) : null}
    </div>
  )
}