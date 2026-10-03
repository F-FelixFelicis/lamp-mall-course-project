export type User = { id: number; display_name: string; phone_masked?: string; roles: string[]; status: string }
type Token = { access_token: string; token_type: string; expires_in: number }
type ErrorBody = { message?: string }
export const BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const TOKEN_KEY = 'lamp_mall_customer_token'
export function request<T>(path: string, method: 'GET' | 'POST' = 'GET', data?: Record<string, string>, token?: string): Promise<T> {
  return new Promise((resolve, reject) => uni.request({
    url: `${BASE}/api/v1${path}`, method, data,
    header: token ? { Authorization: `Bearer ${token}` } : {},
    success(response) { if (response.statusCode >= 200 && response.statusCode < 300) resolve(response.data as T); else reject(new Error((response.data as ErrorBody)?.message || `请求失败 (${response.statusCode})`)) },
    fail(cause) { reject(new Error(cause.errMsg || '网络连接失败')) },
  }))
}
export function getToken(): string { return uni.getStorageSync(TOKEN_KEY) || '' }
export function clearToken(): void { uni.removeStorageSync(TOKEN_KEY) }
export async function register(phone: string, verification_code: string, password: string, display_name: string): Promise<User> { return request<User>('/auth/register', 'POST', { phone, verification_code, password, display_name }) }
export async function login(account: string, password: string): Promise<User> {
  const session = await request<Token>('/auth/login', 'POST', { account, password })
  try { const user = await request<User>('/auth/me', 'GET', undefined, session.access_token); if (!user.roles.includes('CUSTOMER')) throw new Error('此账号没有客户权限'); uni.setStorageSync(TOKEN_KEY, session.access_token); return user }
  catch (cause) { clearToken(); throw cause }
}
export function currentUser(): Promise<User> { return request<User>('/auth/me', 'GET', undefined, getToken()) }
