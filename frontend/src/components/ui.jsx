import { Loader2 } from 'lucide-react'

export function Button({ children, className = '', variant = 'primary', disabled, ...props }) {
  const styles = {
    primary:
      'bg-mint text-ink hover:bg-[#6aead3] disabled:opacity-50 disabled:cursor-not-allowed',
    ghost:
      'bg-transparent text-white/80 border border-line hover:border-mint/50 hover:text-white',
    danger: 'bg-rose-500/90 text-white hover:bg-rose-400',
  }
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 font-medium transition ${styles[variant]} ${className}`}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  )
}

export function Card({ children, className = '' }) {
  return (
    <div className={`rounded-2xl border border-line bg-panel/80 shadow-[0_20px_60px_rgba(0,0,0,0.25)] ${className}`}>
      {children}
    </div>
  )
}

export function Field({ label, children, hint }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm text-white/70">{label}</span>
      {children}
      {hint ? <span className="text-xs text-white/40">{hint}</span> : null}
    </label>
  )
}

export function inputClass(extra = '') {
  return `w-full rounded-xl border border-line bg-ink px-3.5 py-2.5 text-white outline-none transition placeholder:text-white/30 focus:border-mint ${extra}`
}

export function Alert({ children, type = 'error' }) {
  const color = type === 'error' ? 'border-rose-400/40 bg-rose-500/10 text-rose-100' : 'border-mint/30 bg-mint/10 text-mint'
  return <div className={`rounded-xl border px-3 py-2 text-sm ${color}`}>{children}</div>
}

export function Spinner({ label = 'Working…' }) {
  return (
    <div className="flex items-center gap-2 text-white/70">
      <Loader2 className="h-4 w-4 animate-spin" />
      <span>{label}</span>
    </div>
  )
}

export function ScoreBadge({ score }) {
  const value = Number.isFinite(score) ? score : 0
  const tone = value >= 75 ? 'text-mint' : value >= 50 ? 'text-gold' : 'text-rose-300'
  return (
    <div className="flex items-center gap-3">
      <div
        className="score-ring grid h-16 w-16 place-items-center rounded-full p-1"
        style={{ '--p': `${value * 3.6}deg` }}
      >
        <div className="grid h-full w-full place-items-center rounded-full bg-panel text-sm font-semibold">{value}</div>
      </div>
      <div>
        <p className={`font-display text-2xl ${tone}`}>{value}/100</p>
        <p className="text-xs text-white/50">Score</p>
      </div>
    </div>
  )
}

export function Chip({ children, tone = 'neutral' }) {
  const tones = {
    mint: 'bg-mint/15 text-mint border-mint/20',
    gold: 'bg-gold/15 text-gold border-gold/20',
    rose: 'bg-rose-400/15 text-rose-200 border-rose-400/20',
    blue: 'bg-sky-400/15 text-sky-200 border-sky-400/20',
    neutral: 'bg-white/5 text-white/80 border-white/10',
  }
  return <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs ${tones[tone]}`}>{children}</span>
}

export function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        {eyebrow ? <p className="mb-1 text-xs uppercase tracking-[0.2em] text-mint">{eyebrow}</p> : null}
        <h1 className="font-display text-3xl font-semibold tracking-tight md:text-4xl">{title}</h1>
        {description ? <p className="mt-2 max-w-2xl text-white/60">{description}</p> : null}
      </div>
      {actions}
    </div>
  )
}
