# M0-3-T4 — Auth Frontend Package
**Milestone:** M0 — Foundations
**Epic:** M0-3 — Authentication System
**Task ID:** M0-3-T4
**Mode:** Code (MiniMax)
**Estimated effort:** 3–4 hours

---

## Context

This task builds the shared frontend auth package used by all three apps (teacher, student, parent). It handles token storage, the `useAuth` hook, Axios interceptors for auto-refresh, and route guard components — including the new `OnboardingRoute` guard for students.

**Depends on:** M0-1-T1 (frontend workspace structure exists)

---

## User Story

As a frontend developer, I want a single shared auth package so that login state, token refresh, and route protection work identically across all three apps.

---

## What To Build

All files live in `/frontend/packages/auth/src/`.

---

### `/frontend/packages/auth/src/tokenStore.ts`

Zustand store for auth state:

```typescript
import { create } from 'zustand'

interface User {
  id: string
  email: string
  role: 'STUDENT' | 'TEACHER' | 'SCHOOL_ADMIN' | 'PARENT' | 'KAIHLE_ADMIN'
  school_id: string | null
}

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: User | null
  isAuthenticated: boolean
  setTokens: (access: string, refresh: string, user: User) => void
  clearTokens: () => void
  updateAccessToken: (access: string) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  refreshToken: null,
  user: null,
  isAuthenticated: false,

  setTokens: (access, refresh, user) =>
    set({ accessToken: access, refreshToken: refresh, user, isAuthenticated: true }),

  clearTokens: () =>
    set({ accessToken: null, refreshToken: null, user: null, isAuthenticated: false }),

  updateAccessToken: (access) =>
    set({ accessToken: access }),
}))
```

**Note:** Tokens are stored in memory only (Zustand state). On page refresh, the user must log in again. This is intentional for security — no localStorage. If persistence across refreshes is needed later, use an httpOnly cookie strategy (deferred to v2).

---

### `/frontend/packages/auth/src/apiClient.ts`

Shared Axios instance with auto-attach and auto-refresh:

```typescript
import axios, { AxiosInstance, AxiosRequestConfig } from 'axios'
import { useAuthStore } from './tokenStore'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const apiClient: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor — attach Bearer token
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor — auto-refresh on 401
let isRefreshing = false
let failedQueue: Array<{
  resolve: (value: string) => void
  reject: (reason?: unknown) => void
}> = []

const processQueue = (error: unknown, token: string | null) => {
  failedQueue.forEach((p) => {
    if (error) p.reject(error)
    else p.resolve(token!)
  })
  failedQueue = []
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean }

    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error)
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject })
      }).then((token) => {
        originalRequest.headers = {
          ...originalRequest.headers,
          Authorization: `Bearer ${token}`,
        }
        return apiClient(originalRequest)
      })
    }

    originalRequest._retry = true
    isRefreshing = true

    const { refreshToken, updateAccessToken, clearTokens } = useAuthStore.getState()

    if (!refreshToken) {
      clearTokens()
      return Promise.reject(error)
    }

    try {
      const response = await axios.post(`${BASE_URL}/api/v1/auth/refresh`, {
        refresh_token: refreshToken,
      })
      const newAccessToken = response.data.access_token
      updateAccessToken(newAccessToken)
      processQueue(null, newAccessToken)
      originalRequest.headers = {
        ...originalRequest.headers,
        Authorization: `Bearer ${newAccessToken}`,
      }
      return apiClient(originalRequest)
    } catch (refreshError) {
      processQueue(refreshError, null)
      clearTokens()
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  }
)
```

---

### `/frontend/packages/auth/src/useAuth.ts`

```typescript
import { useCallback } from 'react'
import { useAuthStore } from './tokenStore'
import { apiClient } from './apiClient'

interface LoginCredentials {
  email: string
  password: string
}

export function useAuth() {
  const { user, isAuthenticated, setTokens, clearTokens } = useAuthStore()

  const login = useCallback(async (credentials: LoginCredentials) => {
    const response = await apiClient.post('/api/v1/auth/login', credentials)
    const { access_token, refresh_token, user: userData } = response.data
    setTokens(access_token, refresh_token, userData)
    return userData
  }, [setTokens])

  const logout = useCallback(async () => {
    const { refreshToken } = useAuthStore.getState()
    if (refreshToken) {
      try {
        await apiClient.post('/api/v1/auth/logout', { refresh_token: refreshToken })
      } catch {
        // Ignore errors on logout
      }
    }
    clearTokens()
  }, [clearTokens])

  const sendMagicLink = useCallback(async (email: string) => {
    await apiClient.post('/api/v1/auth/magic-link', { email })
  }, [])

  return { user, isAuthenticated, login, logout, sendMagicLink }
}
```

---

### `/frontend/packages/auth/src/guards.tsx`

Route guard components:

```typescript
import React from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from './tokenStore'

/**
 * PrivateRoute — redirects unauthenticated users to /login
 */
export function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return <>{children}</>
}

/**
 * RoleRoute — redirects users whose role is not in allowedRoles to /unauthorised
 */
export function RoleRoute({
  children,
  allowedRoles,
}: {
  children: React.ReactNode
  allowedRoles: string[]
}) {
  const user = useAuthStore((s) => s.user)

  if (!user || !allowedRoles.includes(user.role)) {
    return <Navigate to="/unauthorised" replace />
  }
  return <>{children}</>
}

/**
 * OnboardingRoute (NEW v2.1) — for STUDENT role only.
 * Redirects to /student/onboarding if onboarding is not complete.
 *
 * Uses the /api/v1/onboarding/status endpoint to determine completion.
 * Shows a loading spinner while checking.
 *
 * Only applies to STUDENT role. Other roles pass through immediately.
 */
import { useEffect, useState } from 'react'
import { apiClient } from './apiClient'

type OnboardingStatus = {
  learning_profile_complete: boolean
  diagnostics_complete: boolean
  overall: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED'
}

export function OnboardingRoute({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user)
  const [status, setStatus] = useState<OnboardingStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user || user.role !== 'STUDENT') {
      setLoading(false)
      return
    }
    apiClient
      .get<OnboardingStatus>('/api/v1/onboarding/status')
      .then((res) => setStatus(res.data))
      .catch(() => setStatus(null))
      .finally(() => setLoading(false))
  }, [user])

  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'STUDENT') return <>{children}</>
  if (loading) return <div className="flex items-center justify-center h-screen">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600" />
  </div>
  if (!status || status.overall !== 'COMPLETED') {
    return <Navigate to="/student/onboarding" replace />
  }
  return <>{children}</>
}
```

---

### `/frontend/packages/auth/src/index.ts`

```typescript
export { useAuthStore } from './tokenStore'
export { apiClient } from './apiClient'
export { useAuth } from './useAuth'
export { PrivateRoute, RoleRoute, OnboardingRoute } from './guards'
export type { } // types exported as needed
```

---

### `/frontend/packages/auth/package.json`

```json
{
  "name": "@kaihle/auth",
  "version": "0.1.0",
  "main": "src/index.ts",
  "dependencies": {
    "axios": "^1.7.0",
    "zustand": "^4.5.0",
    "react": "^18.3.0",
    "react-router-dom": "^6.26.0"
  }
}
```

---

## Files To Create

```
/frontend/packages/auth/src/tokenStore.ts
/frontend/packages/auth/src/apiClient.ts
/frontend/packages/auth/src/useAuth.ts
/frontend/packages/auth/src/guards.tsx
/frontend/packages/auth/src/index.ts
/frontend/packages/auth/package.json
```

---

## Tests To Write

**`/frontend/packages/auth/src/__tests__/tokenStore.test.ts`:**
```typescript
test('setTokens stores tokens and sets isAuthenticated true')
test('clearTokens resets all state')
test('updateAccessToken replaces access token without clearing refresh')
```

**`/frontend/packages/auth/src/__tests__/guards.test.tsx`:**
```typescript
test('PrivateRoute redirects unauthenticated user to /login')
test('PrivateRoute renders children when authenticated')
test('RoleRoute redirects when role not in allowedRoles')
test('OnboardingRoute redirects STUDENT with incomplete onboarding to /student/onboarding')
test('OnboardingRoute passes STUDENT with COMPLETED onboarding through')
test('OnboardingRoute passes TEACHER through without checking onboarding status')
```

**`/frontend/packages/auth/src/__tests__/apiClient.test.ts`:**
```typescript
test('request interceptor attaches Bearer token when accessToken exists')
test('response interceptor retries with refreshed token on 401')
test('response interceptor clears tokens when refresh fails')
```

---

## Acceptance Criteria

- [ ] Unit test: `useAuth().login()` stores `accessToken`, `refreshToken`, `user` in store
- [ ] Unit test: `PrivateRoute` redirects unauthenticated user to `/login`
- [ ] Unit test: `OnboardingRoute` redirects STUDENT with incomplete onboarding to `/student/onboarding`
- [ ] Unit test: `OnboardingRoute` passes TEACHER through without API call
- [ ] Unit test: Axios interceptor retries request with refreshed token on 401
- [ ] Unit test: Axios interceptor calls `clearTokens()` when refresh request itself fails
- [ ] TypeScript: `tsc --noEmit` passes with zero errors

---

## Dependencies

- M0-1-T1 — frontend workspace structure
- M0-3-T2 — auth API endpoints (used at runtime, not compile time)
- M0-6-T1 — `/api/v1/onboarding/status` endpoint (used by `OnboardingRoute` at runtime)

## Output (What Next Tasks Can Use)

- `@kaihle/auth` importable in all three apps
- `useAuth()` hook used by M0-3-T5 (login UI)
- `PrivateRoute`, `RoleRoute`, `OnboardingRoute` used in all app routers
- `apiClient` used by all API calls throughout the frontend
