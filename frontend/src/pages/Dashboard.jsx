import { Link } from 'react-router-dom'
import { Compass, FileSearch, Gauge, Map, Mic, ScanSearch, Sparkles, Target, Upload } from 'lucide-react'
import { Card, PageHeader } from '../components/ui.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { getProgress } from '../lib/progress.js'

const tiles = [
  { to: '/app/resumes', title: 'Upload resume', text: 'PDF parsing and skill extraction.', icon: Upload },
  { to: '/app/analyzer', title: 'AI resume analyzer', text: 'Strengths, gaps, and experience level.', icon: Sparkles },
  { to: '/app/ats', title: 'ATS score', text: 'Keyword, structure, and formatting score.', icon: ScanSearch },
  { to: '/app/job-match', title: 'Resume + JD match', text: 'Matched, missing skills and interview topics.', icon: FileSearch },
  { to: '/app/skill-gap', title: 'Skill gap', text: 'Strong, intermediate, weak, missing.', icon: Target },
  { to: '/app/readiness', title: 'Career readiness', text: 'Five-factor readiness for a target role.', icon: Gauge },
  { to: '/app/roadmap', title: 'Personalized roadmap', text: 'Phases from core skills to interviews.', icon: Map },
  { to: '/app/explore', title: 'Career paths', text: 'Switch careers or upskill without beginner noise.', icon: Compass },
  { to: '/app/mock', title: 'Mock interview', text: 'Answer questions and get feedback.', icon: Mic },
]

export default function Dashboard() {
  const { user } = useAuth()
  const progress = getProgress(user?.id)

  const actions = [
    progress.analyzed,
    progress.ats,
    progress.jobMatch,
    progress.skillGap,
    progress.roadmap,
    progress.interview,
    progress.mock,
  ]
  const done = actions.filter(Boolean).length

  return (
    <div>
      <PageHeader
        eyebrow="Workspace"
        title={`Hello, ${user?.name?.split(' ')[0] || 'there'}`}
        description="This is a career intelligence platform — not a job portal. Start with a resume, then pick the scenario that matches your goal."
      />

      <div className="mb-8 grid gap-4 md:grid-cols-3">
        <Card className="p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-white/40">Workspace progress</p>
          <p className="mt-2 font-display text-3xl">{done}/7</p>
          <p className="text-sm text-white/50">Core tools used this session</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-white/40">Skills marked complete</p>
          <p className="mt-2 font-display text-3xl">{progress.completedSkills?.length || 0}</p>
          <p className="text-sm text-white/50">Tracked from your roadmaps</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs uppercase tracking-[0.16em] text-white/40">Recommended path</p>
          <p className="mt-2 font-display text-xl">Resume → Analyze → Gap → Roadmap</p>
          <p className="text-sm text-white/50">Then interview prep and mock rounds</p>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {tiles.map(({ to, title, text, icon: Icon }) => (
          <Link key={to} to={to}>
            <Card className="h-full p-5 transition hover:border-mint/40">
              <Icon className="h-5 w-5 text-mint" />
              <h2 className="mt-3 font-display text-xl">{title}</h2>
              <p className="mt-1 text-sm text-white/55">{text}</p>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
