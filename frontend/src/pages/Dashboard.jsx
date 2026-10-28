import { Link } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Compass, FileSearch, Gauge, Map, Mic, ScanSearch, Sparkles, Target, Upload } from 'lucide-react'
import { careerApi, resumeApi } from '../api/client.js'
import { Alert, Card, Chip, PageHeader, ScoreBadge, Spinner } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const tiles = [
  { to: '/app/resumes', title: 'Upload resume', text: 'Add a PDF to build your verified profile.', icon: Upload },
  { to: '/app/analyzer', title: 'Resume analyzer', text: 'Review extracted strengths and evidence.', icon: Sparkles },
  { to: '/app/ats', title: 'ATS score', text: 'Check structure, keywords, and formatting.', icon: ScanSearch },
  { to: '/app/job-match', title: 'Resume + JD match', text: 'Compare against a specific opportunity.', icon: FileSearch },
  { to: '/app/skill-gap', title: 'Skill gap', text: 'Find role-specific evidence and gaps.', icon: Target },
  { to: '/app/readiness', title: 'Readiness', text: 'Calculate evidence-based role readiness.', icon: Gauge },
  { to: '/app/roadmap', title: 'Personalized roadmap', text: 'Plan and persist learning progress.', icon: Map },
  { to: '/app/explore', title: 'Career paths', text: 'Explore roles from your actual profile.', icon: Compass },
  { to: '/app/mock', title: 'Mock interview', text: 'Practice answers with structured feedback.', icon: Mic },
]

export default function Dashboard() {
  const { user } = useAuth()
  const [state, setState] = useState({ loading: true, error: '', resume: null, analysis: null, roadmap: null })
  useEffect(() => {
    let active = true
    async function load() {
      try {
        const { data: resumes } = await resumeApi.list()
        const resume = resumes[0] || null
        if (!resume) return active && setState({ loading: false, error: '', resume: null, analysis: null, roadmap: null })
        const [analysisResult, roadmapResult] = await Promise.allSettled([resumeApi.analysis(resume.id), careerApi.getRoadmap(resume.id)])
        if (active) setState({ loading: false, error: '', resume, analysis: analysisResult.status === 'fulfilled' ? analysisResult.value.data : null, roadmap: roadmapResult.status === 'fulfilled' ? roadmapResult.value.data : null })
      } catch {
        if (active) setState({ loading: false, error: 'Your workspace could not be loaded. Refresh to try again.', resume: null, analysis: null, roadmap: null })
      }
    }
    load(); return () => { active = false }
  }, [])
  const { resume, analysis, roadmap } = state
  const skills = analysis?.skills || []
  const gaps = analysis?.weaknesses || []
  const progress = roadmap?.roadmap?.flatMap((phase) => phase.skills || []) || []
  const completed = roadmap?.completed_skills?.length || 0

  return <div>
    <PageHeader eyebrow="Workspace" title={`Hello, ${user?.name?.split(' ')[0] || 'there'}`} description="Career intelligence built from your resume evidence—not generic role suggestions." />
    {state.loading ? <Spinner label="Loading your career workspace…" /> : null}
    {state.error ? <div className="mb-5"><Alert>{state.error}</Alert></div> : null}
    {!state.loading && !resume ? <Card className="mb-8 p-6"><h2 className="font-display text-2xl">Start with your resume</h2><p className="mt-2 max-w-xl text-white/60">Upload a readable PDF to extract your profile, then analyze it before requesting scores or recommendations.</p><Link className="mt-4 inline-flex rounded-xl bg-mint px-4 py-2.5 font-medium text-ink" to="/app/resumes">Upload a resume</Link></Card> : null}
    {resume ? <>
      <div className="mb-8 grid gap-4 lg:grid-cols-3">
        <Card className="p-5"><p className="text-xs uppercase tracking-[.16em] text-white/40">Career profile</p><h2 className="mt-2 font-display text-xl">{resume.original_filename}</h2><p className="mt-2 text-sm text-white/55">{analysis?.summary || 'Resume uploaded. Run the analyzer to build your career profile.'}</p></Card>
        <Card className="p-5"><p className="text-xs uppercase tracking-[.16em] text-white/40">ATS compatibility estimate</p>{analysis?.ats_score != null ? <div className="mt-3"><ScoreBadge score={analysis.ats_score} /></div> : <p className="mt-3 text-sm text-white/55">No ATS assessment yet—no score is shown until one is generated.</p>}</Card>
        <Card className="p-5"><p className="text-xs uppercase tracking-[.16em] text-white/40">Roadmap progress</p>{roadmap ? <><p className="mt-2 font-display text-3xl">{completed}/{progress.length}</p><p className="text-sm text-white/55">completed skills for {roadmap.target_role}</p></> : <p className="mt-3 text-sm text-white/55">Choose a target role to create a personalized roadmap.</p>}</Card>
      </div>
      <div className="mb-8 grid gap-4 lg:grid-cols-2"><Card className="p-5"><h2 className="font-display text-xl">Verified skill strengths</h2>{skills.length ? <div className="mt-3 flex flex-wrap gap-2">{skills.slice(0, 12).map((skill) => <Chip key={skill} tone="mint">{skill}</Chip>)}</div> : <p className="mt-3 text-sm text-white/55">Analyze the resume to extract verified skills.</p>}</Card><Card className="p-5"><h2 className="font-display text-xl">Improvement opportunities</h2>{gaps.length ? <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-white/65">{gaps.slice(0, 4).map((item) => <li key={item}>{item}</li>)}</ul> : <p className="mt-3 text-sm text-white/55">No analysis findings yet.</p>}</Card></div>
    </> : null}
    <h2 className="mb-4 font-display text-2xl">Career tools</h2><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{tiles.map(({ to, title, text, icon: Icon }) => <Link key={to} to={to}><Card className="h-full p-5 transition hover:border-mint/40"><Icon className="h-5 w-5 text-mint" /><h3 className="mt-3 font-display text-xl">{title}</h3><p className="mt-1 text-sm text-white/55">{text}</p></Card></Link>)}</div>
  </div>
}
