export type User = {
  id: number
  display_name: string
  phone_masked?: string | null
  roles: string[]
  status: string
}

type Token = { access_token: string; token_type: 'bearer'; expires_in: number }
type ApiError = { code?: string; message?: string }

const TOKEN_KEY = 'lamp_mall_admin_token'

async function json<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init.headers || {}) },
  })
  const body = (await response.json()) as T & ApiError
  if (!response.ok) throw new Error(body.message || `请求失败 (${response.status})`)
  return body
}

export function token() { return sessionStorage.getItem(TOKEN_KEY) }
export function clearToken() { sessionStorage.removeItem(TOKEN_KEY) }

export async function login(account: string, password: string): Promise<void> {
  const result = await json<Token>('/auth/login', {
    method: 'POST', body: JSON.stringify({ account, password }),
  })
  sessionStorage.setItem(TOKEN_KEY, result.access_token)
}

export async function currentAdmin(): Promise<User> {
  const value = token()
  if (!value) throw new Error('请先登录')
  return json<User>('/admin/me', { headers: { Authorization: `Bearer ${value}` } })
}

export function request<T>(path: string, method = 'GET', data?: unknown): Promise<T> {
  return json<T>(path, { method, headers: { Authorization: `Bearer ${token() || ''}` }, body: data === undefined ? undefined : JSON.stringify(data) })
}

export async function privateImage(path: string): Promise<string> {
  const response = await fetch(path, { headers: { Authorization: `Bearer ${token() || ''}` } })
  if (!response.ok) throw new Error('图片读取失败，请刷新后重试')
  return URL.createObjectURL(await response.blob())
}
