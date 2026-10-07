const KEY = 'careerai_progress'

function readAll() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '{}')
  } catch {
    return {}
  }
}

function writeAll(data) {
  localStorage.setItem(KEY, JSON.stringify(data))
}

export function getProgress(userId) {
  const all = readAll()
  return (
    all[userId] || {
      analyzed: 0,
      ats: 0,
      jobMatch: 0,
      skillGap: 0,
      roadmap: 0,
      interview: 0,
      mock: 0,
      completedSkills: [],
    }
  )
}

export function markProgress(userId, field) {
  if (!userId) return
  const all = readAll()
  const current = getProgress(userId)
  all[userId] = { ...current, [field]: (current[field] || 0) + 1, updatedAt: new Date().toISOString() }
  writeAll(all)
}

export function toggleCompletedSkill(userId, skill) {
  const all = readAll()
  const current = getProgress(userId)
  const set = new Set(current.completedSkills || [])
  if (set.has(skill)) set.delete(skill)
  else set.add(skill)
  all[userId] = { ...current, completedSkills: [...set] }
  writeAll(all)
  return [...set]
}
