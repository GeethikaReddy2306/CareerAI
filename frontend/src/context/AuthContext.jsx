import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { apiErrorMessage, authApi, getToken, setToken } from '../api/client.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadMe = useCallback(async () => {
    if (!getToken()) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const { data } = await authApi.me()
      setUser(data)
      setError('')
    } catch {
      setToken(null)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadMe()
  }, [loadMe])

  const login = useCallback(async ({ email, password }) => {
    setError('')
    const { data } = await authApi.login({ email, password })
    setToken(data.access_token)
    const me = await authApi.me()
    setUser(me.data)
    return me.data
  }, [])

  const register = useCallback(async ({ name, email, password }) => {
    setError('')
    await authApi.register({ name, email, password })
    return login({ email, password })
  }, [login])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({ user, loading, error, setError, login, register, logout, apiErrorMessage }),
    [user, loading, error, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
