import { useState } from 'react'
import { apiErrorMessage, careerApi } from '../api/client.js'
import { ResumeGate, ResumePicker } from '../components/ResumePicker.jsx'
import { Alert, Button, Card, Chip, Field, inputClass, PageHeader, Spinner } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { markProgress } from '../lib/progress.js'

export default function InterviewPrep() {
  return (
    <ResumeGate>
      {(state) => <PrepInner {...state} />}
    </ResumeGate>
  )
}

function PrepInner({ resumes, selectedId, select }) {
  const { user } = useAuth()
  const [role, setRole] = useState('Backend Developer')
  const [jd, setJd] = useState('')
  const [questions, setQuestions] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function run(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = {
        resume_id: selectedId,
        target_role: role,
        question_count: 15,
      }
      if (jd.trim().length >= 10) payload.job_description = jd.trim()
      const { data } = await careerApi.createQuestions(payload)
      setQuestions(data.questions || [])
      markProgress(user.id, 'interview')
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
      const { data } = await careerApi.getQuestions(selectedId)
      setQuestions(data.questions || [])
    } catch (err) {
      setError(apiErrorMessage(err, 'No saved questions yet.'))
    } finally {
      setBusy(false)
    }
  }

  const grouped = questions.reduce((acc, q) => {
    acc[q.category] = acc[q.category] || []
    acc[q.category].push(q)
    return acc
  }, {})

  return (
    <div>
      <PageHeader
        eyebrow="Prep"
        title="Personalized interview preparation"
        description="Technical questions from the JD, resume/project questions, plus HR and behavioral prompts with topic-wise coverage."
      />
      <form className="mb-8 grid gap-4" onSubmit={run}>
        <div className="grid gap-4 md:grid-cols-2">
          <ResumePicker resumes={resumes} selectedId={selectedId} onChange={select} />
          <Field label="Target role">
            <input className={inputClass()} required minLength={2} value={role} onChange={(e) => setRole(e.target.value)} />
          </Field>
        </div>
        <Field label="Optional job description">
          <textarea className={inputClass('min-h-28')} value={jd} onChange={(e) => setJd(e.target.value)} />
        </Field>
        <div className="flex gap-2">
          <Button disabled={busy || !selectedId}>{busy ? 'Generating…' : 'Generate questions'}</Button>
          <Button type="button" variant="ghost" disabled={busy || !selectedId} onClick={loadSaved}>
            Load saved
          </Button>
        </div>
      </form>
      {error ? <div className="mb-4"><Alert>{error}</Alert></div> : null}
      {busy ? <Spinner /> : null}
      <div className="space-y-4">
        {Object.entries(grouped).map(([cat, items]) => (
          <Card key={cat} className="p-5">
            <h2 className="font-display text-xl">{cat}</h2>
            <div className="mt-3 space-y-3">
              {items.map((q, i) => (
                <div key={`${q.question}-${i}`} className="rounded-xl border border-line p-3">
                  <div className="mb-1 flex gap-2">
                    <Chip>{q.difficulty}</Chip>
                    <Chip tone="blue">{q.topic}</Chip>
                  </div>
                  <p>{q.question}</p>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
