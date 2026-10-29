import { useEffect, useRef, useState } from 'react'
import { apiErrorMessage, careerApi } from '../api/client.js'
import { ResumeGate, ResumePicker } from '../components/ResumePicker.jsx'
import { Alert, Button, Card, Chip, Field, inputClass, PageHeader, ScoreBadge, Spinner } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { markProgress } from '../lib/progress.js'

export default function MockInterview() {
  return (
    <ResumeGate>
      {(state) => <MockInner {...state} />}
    </ResumeGate>
  )
}

function isValidEvaluation(value) {
  return Number.isFinite(value?.score)
    && value.score >= 0
    && value.score <= 100
    && typeof value.verdict === 'string'
    && value.verdict.length > 0
    && typeof value.feedback === 'string'
    && value.feedback.trim().length >= 20
    && Array.isArray(value.strengths)
    && Array.isArray(value.improvements)
    && Array.isArray(value.missing_concepts)
}

function MockInner({ resumes, selectedId, select }) {
  const { user } = useAuth()
  const [role, setRole] = useState('Backend Developer')
  const [jd, setJd] = useState('')
  const [questions, setQuestions] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [generationMode, setGenerationMode] = useState('')
  const [generationNotice, setGenerationNotice] = useState('')
  const [evaluationNotice, setEvaluationNotice] = useState('')
  const [restoreNotice, setRestoreNotice] = useState('')
  const [index, setIndex] = useState(0)
  const [answer, setAnswer] = useState('')
  const [evals, setEvals] = useState([])
  const [currentEval, setCurrentEval] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [started, setStarted] = useState(false)
  const restoredKey = useRef('')
  const storageKey = selectedId && user?.id ? `careerai_mock_session_${user.id}_${selectedId}` : ''

  useEffect(() => {
    if (!storageKey || restoredKey.current === storageKey) return
    restoredKey.current = storageKey
    const savedSessionId = sessionStorage.getItem(storageKey)
    if (!savedSessionId) return
    let cancelled = false

    async function restore() {
      setBusy(true)
      try {
        const { data } = await careerApi.getInterviewSession(savedSessionId)
        if (cancelled || data.resume_id !== selectedId || !data.questions?.length) return
        const savedAnswers = data.answers || []
        const answeredQuestions = new Set(savedAnswers.map((item) => item.question))
        const nextIndex = data.questions.findIndex((item) => !answeredQuestions.has(item.question))
        setRole(data.target_role)
        setJd(data.job_description || '')
        setQuestions(data.questions)
        setSessionId(data.id)
        setGenerationMode(data.generation_mode || 'saved')
        setGenerationNotice(data.generation_notice || '')
        setEvals(savedAnswers.filter((item) => item.evaluation).map((item) => ({ ...item.evaluation, question: item.question })))
        setIndex(nextIndex === -1 ? data.questions.length : nextIndex)
        setCurrentEval(null)
        setAnswer('')
        setStarted(true)
        setRestoreNotice('Your saved mock interview session was restored.')
      } catch {
        sessionStorage.removeItem(storageKey)
        if (!cancelled) setRestoreNotice('A saved mock interview session could not be restored. Start a new one to continue.')
      } finally {
        if (!cancelled) setBusy(false)
      }
    }
    restore()
    return () => { cancelled = true }
  }, [selectedId, storageKey])

  async function start(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setGenerationNotice('')
    setEvaluationNotice('')
    setRestoreNotice('')
    setGenerationMode('')
    try {
      const payload = {
        resume_id: selectedId,
        target_role: role,
        question_count: 6,
      }
      if (jd.trim().length >= 10) payload.job_description = jd.trim()
      const { data } = await careerApi.createQuestions(payload)
      const generatedQuestions = data.questions || []
      if (!generatedQuestions.length || !data.session_id) {
        setStarted(false)
        setError(data.generation_notice || 'No valid interview questions could be generated for this profile.')
        return
      }
      setQuestions(generatedQuestions)
      setSessionId(data.session_id)
      setGenerationMode(data.generation_mode || 'ai')
      setGenerationNotice(data.generation_notice || '')
      setIndex(0)
      setEvals([])
      setCurrentEval(null)
      setAnswer('')
      setStarted(true)
      if (storageKey) sessionStorage.setItem(storageKey, data.session_id)
      markProgress(user.id, 'interview')
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const q = questions[index]
  const finished = started && questions.length > 0 && index >= questions.length

  async function submitAnswer(e) {
    e.preventDefault()
    if (!q) return
    setBusy(true)
    setError('')
    setEvaluationNotice('')
    try {
      const { data } = await careerApi.evaluateAnswer({
        question: q.question,
        answer,
        category: q.category,
        topic: q.topic,
        target_role: role,
        session_id: sessionId,
      })
      if (!isValidEvaluation(data)) {
        setError('The evaluation response was incomplete, so this answer was not marked as evaluated. Please try again.')
        return
      }
      const next = [...evals, { ...data, question: q.question }]
      setEvals(next)
      setCurrentEval(data)
      setEvaluationNotice(data.evaluation_notice || '')
      markProgress(user.id, 'mock')
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  function nextQuestion() {
    setCurrentEval(null)
    setAnswer('')
    setIndex((i) => i + 1)
  }

  function startNewSession() {
    if (storageKey) sessionStorage.removeItem(storageKey)
    setStarted(false)
    setQuestions([])
    setEvals([])
    setSessionId(null)
    setGenerationMode('')
    setGenerationNotice('')
    setEvaluationNotice('')
    setRestoreNotice('')
    setError('')
    setIndex(0)
    setAnswer('')
    setCurrentEval(null)
  }

  const avg = evals.length ? Math.round(evals.reduce((s, x) => s + x.score, 0) / evals.length) : 0
  const weak = evals.filter((x) => x.score < 60)
  const isProfileBased = generationMode === 'profile_based'
  const isDemo = generationMode === 'demo'
  const sourceLabel = isDemo
    ? 'Demo mode — not AI-generated'
    : isProfileBased
    ? 'Profile-based fallback'
    : generationMode === 'mixed'
      ? 'Mixed sources'
      : generationMode === 'saved'
        ? 'Saved questions'
        : generationMode === 'ai'
          ? 'AI-generated'
          : 'Generation source unavailable'

  return (
    <div>
      <PageHeader
        eyebrow="Practice"
        title="Mock interview"
        description="Uses the configured AI provider for role-specific questions and feedback. Any profile-based fallback is clearly identified."
      />
      {!started ? (
        <form className="grid gap-4 md:grid-cols-3" onSubmit={start}>
          <ResumePicker resumes={resumes} selectedId={selectedId} onChange={select} />
          <Field label="Target role">
            <input className={inputClass()} required minLength={2} value={role} onChange={(e) => setRole(e.target.value)} />
          </Field>
          <Field label="Optional job description">
            <textarea className={inputClass('min-h-24')} value={jd} onChange={(e) => setJd(e.target.value)} />
          </Field>
          <div className="flex items-end">
            <Button disabled={busy || !selectedId}>{busy ? 'Preparing…' : 'Start mock interview'}</Button>
          </div>
        </form>
      ) : null}
      {error ? <div className="mt-4"><Alert>{error}</Alert></div> : null}
      {restoreNotice ? <div className="mt-4"><Alert type="success">{restoreNotice}</Alert></div> : null}
      {generationNotice ? <div className="mt-4"><Alert type={generationMode === 'error' ? 'error' : 'success'}>{generationNotice}</Alert></div> : null}
      {evaluationNotice ? <div className="mt-4"><Alert type="success">{evaluationNotice}</Alert></div> : null}
      {busy && !q ? <Spinner /> : null}

      {started && q && !finished ? (
        <Card className="mt-6 p-6">
          <div className="flex flex-wrap gap-2">
            <Chip tone="mint">Question {index + 1} of {questions.length}</Chip>
            <Chip tone={isDemo || isProfileBased || generationMode === 'mixed' ? 'gold' : 'mint'}>{sourceLabel}</Chip>
            <Chip>{q.category}</Chip>
            <Chip tone="gold">{q.difficulty}</Chip>
            <Chip tone="blue">{q.topic}</Chip>
          </div>
          <h2 className="mt-4 font-display text-2xl">{q.question}</h2>
          {!currentEval ? (
            <form className="mt-4 space-y-3" onSubmit={submitAnswer}>
              <textarea
                className={inputClass('min-h-40')}
                required
                minLength={8}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Answer as you would in an interview…"
              />
              <Button disabled={busy}>{busy ? 'Evaluating…' : 'Submit answer'}</Button>
            </form>
          ) : (
            <div className="mt-4 space-y-3">
              <ScoreBadge score={currentEval.score} />
              <div className="flex flex-wrap gap-2">
                <p className="text-sm text-mint">{currentEval.verdict}</p>
                <Chip tone={currentEval.evaluation_mode === 'demo' || currentEval.evaluation_mode === 'profile_based' ? 'gold' : 'mint'}>
                  {currentEval.evaluation_mode === 'demo' ? 'Demo evaluation — rule-based' : currentEval.evaluation_mode === 'profile_based' ? 'Profile-based evaluation' : 'AI evaluation'}
                </Chip>
              </div>
              <p className="text-white/70">{currentEval.feedback}</p>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase text-white/40">Strengths</p>
                  <ul className="mt-1 list-disc pl-5 text-sm">{currentEval.strengths?.map((s) => <li key={s}>{s}</li>)}</ul>
                </div>
                <div>
                  <p className="text-xs uppercase text-white/40">Improve</p>
                  <ul className="mt-1 list-disc pl-5 text-sm">{currentEval.improvements?.map((s) => <li key={s}>{s}</li>)}</ul>
                </div>
                {currentEval.missing_concepts?.length ? (
                  <div>
                    <p className="text-xs uppercase text-white/40">Missing concepts</p>
                    <ul className="mt-1 list-disc pl-5 text-sm">{currentEval.missing_concepts.map((s) => <li key={s}>{s}</li>)}</ul>
                  </div>
                ) : null}
              </div>
              {index < questions.length - 1 ? (
                <Button onClick={nextQuestion}>Next question</Button>
              ) : (
                <Button onClick={() => setIndex(questions.length)}>See summary</Button>
              )}
            </div>
          )}
        </Card>
      ) : null}
      {started && !finished ? (
        <Button className="mt-4" type="button" variant="ghost" disabled={busy} onClick={startNewSession}>
          Start a new session
        </Button>
      ) : null}

      {finished ? (
        <Card className="mt-6 p-6">
          <h2 className="font-display text-2xl">Session summary</h2>
          <div className="mt-4">
            <ScoreBadge score={avg} />
          </div>
          <p className="mt-3 text-white/65">
            Weak areas: {weak.length ? weak.map((w) => w.question).join(' · ') : 'None — keep practicing advanced topics.'}
          </p>
          <div className="mt-4 space-y-2">
            {evals.map((item, i) => (
              <div key={i} className="rounded-xl border border-line p-3 text-sm">
                <p className="font-medium">{item.question}</p>
                <p className="text-white/50">{item.verdict} · {item.score}/100</p>
              </div>
            ))}
          </div>
          <Button className="mt-4" variant="ghost" onClick={startNewSession}>
            New session
          </Button>
        </Card>
      ) : null}
    </div>
  )
}
