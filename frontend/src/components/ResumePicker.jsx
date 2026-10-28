import { useEffect, useState } from 'react'
import { apiErrorMessage, resumeApi } from '../api/client.js'
import { Alert, Field, inputClass, Spinner } from './ui.jsx'

const STORAGE_KEY = 'careerai_selected_resume'

export function useSelectedResume() {
  const [resumes, setResumes] = useState([])
  const [selectedId, setSelectedId] = useState(() => {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw || null
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true
    resumeApi
      .list()
      .then(({ data }) => {
        if (!mounted) return
        setResumes(data || [])
        if (!selectedId && data?.[0]?.id) {
          setSelectedId(data[0].id)
          sessionStorage.setItem(STORAGE_KEY, String(data[0].id))
        }
      })
      .catch((err) => mounted && setError(apiErrorMessage(err)))
      .finally(() => mounted && setLoading(false))
    return () => {
      mounted = false
    }
  }, [])

  const select = (id) => {
    setSelectedId(id)
    sessionStorage.setItem(STORAGE_KEY, String(id))
  }

  return { resumes, selectedId, select, loading, error, setError, setResumes }
}

export function ResumePicker({ resumes, selectedId, onChange, label = 'Resume' }) {
  if (!resumes.length) {
    return <Alert>Upload a resume first from the Resumes page.</Alert>
  }
  return (
    <Field label={label}>
      <select className={inputClass()} value={selectedId || ''} onChange={(e) => onChange(e.target.value)}>
        {resumes.map((r) => (
          <option key={r.id} value={r.id}>
            #{r.id} · {r.original_filename}
          </option>
        ))}
      </select>
    </Field>
  )
}

export function ResumeGate({ children }) {
  const state = useSelectedResume()
  if (state.loading) return <Spinner label="Loading resumes…" />
  if (state.error) return <Alert>{state.error}</Alert>
  return children(state)
}
