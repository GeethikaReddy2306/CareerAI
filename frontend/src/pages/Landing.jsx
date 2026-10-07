import { Link } from 'react-router-dom'
import { ArrowRight, Brain, Map, Mic, ScanSearch } from 'lucide-react'
import { Button } from '../components/ui.jsx'

const pillars = [
  {
    icon: ScanSearch,
    title: 'Applying for a job',
    text: 'Resume + JD → ATS analysis → skill gap → interview prep → mock interview.',
  },
  {
    icon: Map,
    title: 'Starting a new career',
    text: 'Current profile → target career → skill gap → personalized roadmap → readiness.',
  },
  {
    icon: Brain,
    title: 'Experienced upskilling',
    text: 'Skip beginner advice. Get advanced gaps for your next level, from backend to senior.',
  },
]

export default function Landing() {
  return (
    <div className="mx-auto max-w-6xl px-5 py-10 md:py-16">
      <header className="mb-16 flex items-center justify-between">
        <div>
          <p className="font-display text-xl font-semibold">CareerAI</p>
          <p className="text-xs uppercase tracking-[0.2em] text-mint">Not a job portal</p>
        </div>
        <div className="flex gap-3">
          <Link to="/login">
            <Button variant="ghost">Log in</Button>
          </Link>
          <Link to="/register">
            <Button>Create account</Button>
          </Link>
        </div>
      </header>

      <section className="grid items-center gap-12 lg:grid-cols-2">
        <div>
          <p className="mb-3 text-sm uppercase tracking-[0.22em] text-mint">Career intelligence platform</p>
          <h1 className="font-display text-4xl font-semibold leading-tight md:text-6xl">
            Know your position. Close the gap. Prepare with intent.
          </h1>
          <p className="mt-5 max-w-xl text-lg text-white/65">
            An AI-powered career intelligence, preparation, and upskilling system. It adapts to who you are, what you
            already know, and what you want next.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/register">
              <Button className="px-5 py-3">
                Start with your resume <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link to="/login">
              <Button variant="ghost" className="px-5 py-3">
                I already have an account
              </Button>
            </Link>
          </div>
        </div>
        <div className="grid gap-4 rounded-3xl border border-line bg-panel/70 p-6">
          {pillars.map(({ icon: Icon, title, text }) => (
            <div key={title} className="rounded-2xl border border-line bg-ink/40 p-4">
              <Icon className="mb-2 h-5 w-5 text-mint" />
              <h2 className="font-display text-lg">{title}</h2>
              <p className="mt-1 text-sm text-white/55">{text}</p>
            </div>
          ))}
          <div className="flex items-center gap-3 rounded-2xl border border-mint/20 bg-mint/10 p-4 text-sm">
            <Mic className="h-5 w-5 text-mint" />
            Personalized mock interviews with answer feedback — not a job board.
          </div>
        </div>
      </section>
    </div>
  )
}
