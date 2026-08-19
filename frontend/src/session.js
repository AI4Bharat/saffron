/** Who is signed in, and which team workspace they are looking at. One annotator can belong to seve. */
import { reactive, computed } from 'vue'
import { API_BASE_URL } from '@/config'

export const ORG_NAME = 'Saffron'

const TEAM_KEY = 'activeTeam'

export const session = reactive({
  loaded: false,
  loading: false,
  role: null,          // 'annotator' | 'admin'
  scope: null,         // admins: 'org' | 'team'
  name: '',
  username: '',
  email: '',
  organization: ORG_NAME,
  teams: [],           // [{key,name,workflow,accent,description,languages,pull_size}]
  team: null,          // admins pinned to one team
  activeTeamKey: localStorage.getItem(TEAM_KEY) || '',
  error: '',
})

export function authToken() {
  return localStorage.getItem('authToken') || sessionStorage.getItem('authToken') || ''
}

export function authHeaders(extra = {}) {
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${authToken()}`, ...extra }
}

/** fetch() wrapper that always sends the token and unwraps JSON errors. */
export async function api(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: authHeaders(options.headers || {}),
  })
  let data = null
  try { data = await res.json() } catch { /* empty body */ }
  if (!res.ok) {
    // An expired or missing token is not a page failure. Without this, every
    // caller renders its own red "failed to load" box and the only offered action
    // (Try Again) reuses the same dead token. /login is exempt: a 401 there means
    // wrong credentials, and that form shows the message itself.
    if (res.status === 401 && !path.startsWith('/login')) {
      localStorage.removeItem('authToken')
      sessionStorage.removeItem('authToken')
      session.loaded = false
      if (!window.location.pathname.startsWith('/login')) {
        window.location.assign('/login')
      }
    }
    const err = new Error((data && (data.message || data.error)) || `Request failed (${res.status})`)
    err.status = res.status
    err.data = data
    throw err
  }
  return data
}

export const activeTeam = computed(() =>
  session.teams.find(t => t.key === session.activeTeamKey) || session.teams[0] || null
)

export function setActiveTeam(key) {
  session.activeTeamKey = key
  localStorage.setItem(TEAM_KEY, key)
}

export async function loadIdentity(force = false) {
  if (session.loaded && !force) return session
  if (!authToken()) return session
  session.loading = true
  try {
    const me = await api('/me')
    session.role = me.role
    session.scope = me.scope || null
    session.name = me.name || me.username || ''
    session.username = me.username || ''
    session.email = me.email || ''
    session.organization = me.organization || ORG_NAME
    session.teams = me.teams || []
    session.team = me.team || null
    if (!session.teams.some(t => t.key === session.activeTeamKey)) {
      setActiveTeam((session.team && session.team.key) || (session.teams[0] && session.teams[0].key) || '')
    }
    session.loaded = true
    session.error = ''
  } catch (e) {
    session.error = e.message
  } finally {
    session.loading = false
  }
  return session
}

export function clearSession() {
  localStorage.removeItem('authToken')
  sessionStorage.removeItem('authToken')
  localStorage.removeItem(TEAM_KEY)
  Object.assign(session, {
    loaded: false, role: null, scope: null, name: '', username: '', email: '',
    teams: [], team: null, activeTeamKey: '', error: '',
  })
}

/** Where a freshly signed-in user belongs. */
export function landingPath(identity = session) {
  if (identity.role === 'admin') {
    // An organisation admin starts at the overview and picks a team from there;
    if (identity.scope === 'org') return '/org'
    return dashboardPath(identity.team || identity.teams[0])
  }
  const teams = identity.teams || []
  if (teams.length === 0) return '/no-workspace'
  if (teams.length === 1) return workspacePath(teams[0])
  return '/workspaces'
}

/** Where a team's annotators work. Pool teams get their own page; the classic batch workflow lives at the site root. */
export function workspacePath(team) {
  if (!team) return '/'
  return team.workflow === 'pool' ? `/pool/${team.key}` : '/'
}

/** A team's admin dashboard. Every team follows the same '/<key>/admin' shape, so adding a team nee. */
export function dashboardPath(team) {
  if (!team) return '/tts/admin'
  return `/${team.key}/admin`
}
