export type User = { id: number; display_name: string; phone_masked?: string; roles: string[]; status: string }
type Token = { access_token: string; token_type: string; expires_in: number }
type ErrorBody = { message?: string }
const BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const TOKEN_KEY = 'lamp_mall_merchant_token'
export function request<T>(path: string, method: 'GET' | 'POST' | 'PUT' = 'GET', data?: object, token: string = getToken()): Promise<T> {
  return new Promise((resolve, reject) => uni.request({
    url: `${BASE}/api/v1${path}`, method, data,
    header: token ? { Authorization: `Bearer ${token}` } : {},
    success(response) { if (response.statusCode >= 200 && response.statusCode < 300) resolve(response.data as T); else reject(new Error((response.data as ErrorBody)?.message || `请求失败 (${response.statusCode})`)) },
    fail(cause) { reject(new Error(cause.errMsg || '网络连接失败')) },
  }))
}
export function getToken(): string { return uni.getStorageSync(TOKEN_KEY) || '' }
export function clearToken(): void { uni.removeStorageSync(TOKEN_KEY) }
export async function login(account: string, password: string): Promise<User> {
  const session = await request<Token>('/auth/login', 'POST', { account, password })
  try { const user = await request<User>('/auth/me', 'GET', undefined, session.access_token); uni.setStorageSync(TOKEN_KEY, session.access_token); return user }
  catch (cause) { clearToken(); throw cause }
}
export function currentUser(): Promise<User> { return request<User>('/auth/me', 'GET', undefined, getToken()) }
export function chooseUpload(purpose: 'LICENSE' | 'PRODUCT'): Promise<import('../../shared/catalog').Uploaded> {
  return new Promise((resolve, reject) => uni.chooseImage({ count: 1, sizeType: ['compressed'], success(selection) {
    uni.uploadFile({ url: `${BASE}/api/v1/files`, filePath: selection.tempFilePaths[0], name: 'file', formData: { purpose }, header: { Authorization: `Bearer ${getToken()}` },
      success(response) { try { const body = JSON.parse(response.data); if (response.statusCode >= 200 && response.statusCode < 300) resolve(body); else reject(new Error(body.message || '上传失败')) } catch { reject(new Error('上传响应无效')) } }, fail(e) { reject(new Error(e.errMsg || '上传失败')) } })
  }, fail(e) { reject(new Error(e.errMsg.includes('cancel') ? '已取消选择' : '无法选择图片')) } }))
}
export function previewFile(id: number): Promise<void> {
  return new Promise((resolve, reject) => uni.downloadFile({ url: `${BASE}/api/v1/files/${id}/content`, header: { Authorization: `Bearer ${getToken()}` }, success(r) { if (r.statusCode === 200) { uni.previewImage({ urls: [r.tempFilePath] }); resolve() } else reject(new Error('图片读取失败')) }, fail(e) { reject(new Error(e.errMsg)) } }))
}
