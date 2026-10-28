import { useState } from 'react'
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

function MockInner({ resumes, selectedId, select }) {
  const { user } = useAuth()
  const [role, setRole] = useState('Backend Developer')
  const [questions, setQuestions] = useState([])
  const [sessionId, setSessionId] = useState(null)
  const [index, setIndex] = useState(0)
  const [answer, setAnswer] = useState('')
  const [evals, setEvals] = useState([])
  const [currentEval, setCurrentEval] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [started, setStarted] = useState(false)

  async function start(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const { data } = await careerApi.createQuestions({
        resume_id: selectedId,
        target_role: role,
        question_count: 6,
      })
      setQuestions(data.questions || [])
      setSessionId(data.session_id || null)
      setIndex(0)
      setEvals([])
      setCurrentEval(null)
      setAnswer('')
      setStarted(true)
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
    try {
      const { data } = await careerApi.evaluateAnswer({
        question: q.question,
        answer,
        category: q.category,
        topic: q.topic,
        target_role: role,
        session_id: sessionId,
      })
      const next = [...evals, { ...data, question: q.question }]
      setEvals(next)
      setCurrentEval(data)
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

  const avg = evals.length ? Math.round(evals.reduce((s, x) => s + x.score, 0) / evals.length) : 0
  const weak = evals.filter((x) => x.score < 60)

  return (
    <div>
      <PageHeader
        eyebrow="Practice"
        title="AI mock interview"
        description="Questions are generated from your resume and target role. Each answer is scored with feedback and weak areas."
      />
      {!started ? (
        <form className="grid gap-4 md:grid-cols-3" onSubmit={start}>
          <ResumePicker resumes={resumes} selectedId={selectedId} onChange={select} />
          <Field label="Target role">
            <input className={inputClass()} required minLength={2} value={role} onChange={(e) => setRole(e.target.value)} />
          </Field>
          <div className="flex items-end">
            <Button disabled={busy || !selectedId}>{busy ? 'Preparing…' : 'Start mock interview'}</Button>
          </div>
        </form>
      ) : null}
      {error ? <div className="mt-4"><Alert>{error}</Alert></div> : null}
      {busy && !q ? <Spinner /> : null}

      {started && q && !finished ? (
        <Card className="mt-6 p-6">
          <div className="flex flex-wrap gap-2">
            <Chip tone="mint">Question {index + 1} of {questions.length}</Chip>
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
              <p className="text-sm text-mint">{currentEval.verdict}</p>
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
          <Button className="mt-4" variant="ghost" onClick={() => { setStarted(false); setQuestions([]); setEvals([]); setSessionId(null) }}>
            New session
          </Button>
        </Card>
      ) : null}
    </div>
  )
}
