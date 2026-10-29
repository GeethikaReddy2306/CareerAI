import axios from 'axios'

const TOKEN_KEY = 'careerai_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export const api = axios.create({
  baseURL: (import.meta.env.VITE_API_URL || '').trim(),
  timeout: 60000,
})

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export function apiErrorMessage(error, fallback = 'Something went wrong. Please try again.') {
  const data = error?.response?.data
  if (typeof data?.message === 'string') return data.message
  if (typeof data?.detail === 'string') return data.detail
  if (Array.isArray(data?.detail)) {
    return data.detail.map((item) => item.msg || JSON.stringify(item)).join(' ')
  }
  if (error?.code === 'ERR_NETWORK') {
    return 'Cannot reach the API server. Please check your connection or try again.'
  }
  return fallback
}

export const authApi = {
  register: (payload) => api.post('/api/auth/register', payload),
  login: (payload) => api.post('/api/auth/login', payload),
  me: () => api.get('/api/auth/me'),
}

export const resumeApi = {
  list: () => api.get('/api/resumes'),
  get: (id) => api.get(`/api/resumes/${id}`),
  upload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/api/resumes/upload', form)
  },
  remove: (id) => api.delete(`/api/resumes/${id}`),
  analyze: (id, forceRefresh = false) =>
    api.post(`/api/resumes/${id}/analyze`, null, { params: { force_refresh: forceRefresh } }),
  ats: (id) => api.post(`/api/resumes/${id}/ats-score`),
  analysis: (id) => api.get(`/api/resumes/${id}/analysis`),
}

export const careerApi = {
  jobAnalysis: (payload) => api.post('/api/job-analysis', payload),
  skillGap: (payload) => api.post('/api/skill-gap', payload),
  readiness: (resumeId, targetRole) =>
    api.get('/api/career-readiness', { params: { resume_id: resumeId, target_role: targetRole } }),
  createRoadmap: (payload) => api.post('/api/career/roadmap', payload),
  getRoadmap: (resumeId) => api.get('/api/career/roadmap', { params: { resume_id: resumeId } }),
  updateRoadmapProgress: (roadmapId, completed_skills) => api.patch(`/api/career/roadmap/${roadmapId}/progress`, { completed_skills }),
  createQuestions: (payload) => api.post('/api/interview/questions', payload),
  getQuestions: (resumeId, filters = {}) => api.get('/api/interview/questions', {
    params: { resume_id: resumeId, ...filters },
  }),
  getInterviewSession: (sessionId) => api.get(`/api/interview/sessions/${sessionId}`),
  evaluateAnswer: (payload) => api.post('/api/interview/evaluate', payload),
}
