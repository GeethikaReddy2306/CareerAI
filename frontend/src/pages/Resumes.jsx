import { useState } from 'react'
import { apiErrorMessage, resumeApi } from '../api/client.js'
import { ResumeGate } from '../components/ResumePicker.jsx'
import { Alert, Button, Card, PageHeader, Spinner } from '../components/ui.jsx'

export default function Resumes() {
  return (
    <ResumeGate>
      {(state) => <ResumeWorkspace {...state} />}
    </ResumeGate>
  )
}

function ResumeWorkspace({ resumes, selectedId, select, setResumes, error, setError }) {
  const [busy, setBusy] = useState(false)
  const [detail, setDetail] = useState(null)
  const [message, setMessage] = useState('')

  async function onUpload(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const { data } = await resumeApi.upload(file)
      const list = await resumeApi.list()
      setResumes(list.data)
      select(data.id)
      setMessage(`Uploaded ${data.filename}. Extracted ${data.text_length} characters.`)
    } catch (err) {
      setError(apiErrorMessage(err, 'Upload failed. Use a PDF under 5 MB.'))
    } finally {
      setBusy(false)
    }
  }

  async function view(id) {
    setBusy(true)
    setError('')
    try {
      const { data } = await resumeApi.get(id)
      setDetail(data)
      select(id)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function remove(id) {
    if (!window.confirm('Delete this resume?')) return
    setBusy(true)
    setError('')
    try {
      await resumeApi.remove(id)
      const list = await resumeApi.list()
      setResumes(list.data)
      setDetail(null)
      if (list.data[0]) select(list.data[0].id)
    } catch (err) {
      setError(apiErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Library"
        title="Resumes"
        description="Upload a PDF resume. The backend extracts text with PyMuPDF so every other tool can use your profile."
        actions={
          <label className="inline-flex cursor-pointer">
            <input type="file" accept="application/pdf,.pdf" className="hidden" onChange={onUpload} />
            <span className="inline-flex items-center rounded-xl bg-mint px-4 py-2.5 font-medium text-ink">
              {busy ? 'Working…' : 'Upload PDF'}
            </span>
          </label>
        }
      />
      {error ? <div className="mb-4"><Alert>{error}</Alert></div> : null}
      {message ? <div className="mb-4"><Alert type="ok">{message}</Alert></div> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="font-display text-xl">Your files</h2>
          <div className="mt-4 space-y-3">
            {!resumes.length ? <p className="text-sm text-white/50">No resumes yet.</p> : null}
            {resumes.map((r) => (
              <div
                key={r.id}
                className={`rounded-xl border p-3 ${selectedId === r.id ? 'border-mint/50 bg-mint/5' : 'border-line'}`}
              >
                <p className="font-medium">{r.original_filename}</p>
                <p className="text-xs text-white/40">
                  {Math.round(r.file_size / 1024)} KB · {new Date(r.uploaded_at).toLocaleString()}
                </p>
                <div className="mt-2 flex gap-2">
                  <Button variant="ghost" className="px-3 py-1.5 text-sm" onClick={() => view(r.id)}>
                    Open
                  </Button>
                  <Button variant="danger" className="px-3 py-1.5 text-sm" onClick={() => remove(r.id)}>
                    Delete
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="font-display text-xl">Extracted text</h2>
          {busy ? <div className="mt-4"><Spinner /></div> : null}
          {detail ? (
            <pre className="mt-4 max-h-[480px] overflow-auto whitespace-pre-wrap text-sm text-white/70">
              {detail.extracted_text || 'No text extracted.'}
            </pre>
          ) : (
            <p className="mt-4 text-sm text-white/50">Select a resume to preview parsed content.</p>
          )}
        </Card>
      </div>
    </div>
  )
}
