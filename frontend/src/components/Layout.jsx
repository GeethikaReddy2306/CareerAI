import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  Compass,
  FileSearch,
  Gauge,
  LayoutDashboard,
  LogOut,
  Map,
  MessageSquareQuote,
  Mic,
  ScanSearch,
  Sparkles,
  Target,
  Upload,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'

const links = [
  { to: '/app', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/app/resumes', label: 'Resumes', icon: Upload },
  { to: '/app/analyzer', label: 'AI Analyzer', icon: Sparkles },
  { to: '/app/ats', label: 'ATS Score', icon: ScanSearch },
  { to: '/app/job-match', label: 'Resume + JD', icon: FileSearch },
  { to: '/app/skill-gap', label: 'Skill Gap', icon: Target },
  { to: '/app/readiness', label: 'Readiness', icon: Gauge },
  { to: '/app/roadmap', label: 'Roadmap', icon: Map },
  { to: '/app/explore', label: 'Career Paths', icon: Compass },
  
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[260px_1fr]">
      <aside className="border-b border-line bg-panel/70 lg:border-b-0 lg:border-r">
        <div className="flex items-center justify-between px-5 py-5">
          <button onClick={() => navigate('/app')} className="text-left">
            <p className="font-display text-lg font-semibold">CareerAI</p>
            <p className="text-[11px] uppercase tracking-[0.18em] text-mint">Career intelligence</p>
          </button>
        </div>
        <nav className="grid gap-1 px-3 pb-6">
          {links.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${
                  isActive ? 'bg-mint/15 text-mint' : 'text-white/70 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="hidden border-t border-line px-5 py-4 lg:block">
          <p className="truncate text-sm font-medium">{user?.name}</p>
          <p className="truncate text-xs text-white/40">{user?.email}</p>
          <button
            onClick={() => {
              logout()
              navigate('/login')
            }}
            className="mt-3 inline-flex items-center gap-2 text-sm text-white/60 hover:text-white"
          >
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      </aside>
      <main className="px-4 py-6 md:px-8 md:py-8">
        <div className="mb-4 flex items-center justify-between lg:hidden">
          <p className="text-sm text-white/60">{user?.name}</p>
          <button
            onClick={() => {
              logout()
              navigate('/login')
            }}
            className="text-sm text-mint"
          >
            Sign out
          </button>
        </div>
        <Outlet />
      </main>
    </div>
  )
}
