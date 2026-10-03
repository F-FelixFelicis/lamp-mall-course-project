export type Audit = { result: string; reason: string; version: number; created_at: string }
export type Category = { id: number; name: string; code: string }
export type Merchant = { id: number; shop_name: string; legal_name: string; contact_phone: string; address: string; business_license_file_id: number; certification_status: string; version: number; audits: Audit[] }
export type Offer = { id: number; merchant_id: number; sku_id: number; sku_code: string; product_name: string; shop_name: string; price: number; stock_qty: number; unit: string; status: string; version: number; remark: string; audits?: Audit[] }
export type Sku = { id: number; sku_code: string; attributes: { color: string; size_spec: string; material: string; power_watt: number | string | null; color_temperature: string; luminous_flux_lm: number | null }; image_file_ids: number[]; images: string[]; offers: Offer[] }
export type Product = { id: number; category_id: number; category_name: string; name: string; brand: string; style: string; application_space: string; description: string; status: string; version: number; cover_url: string | null; lowest_price: number | null; skus: Sku[]; audits?: Audit[] }
export type ProductCard = Pick<Product, 'id' | 'name' | 'category_name' | 'status' | 'cover_url' | 'lowest_price'>
export type ProductPage = { items: ProductCard[]; total: number; page: number; page_size: number }
export type Uploaded = { id: number; url: string; purpose: string }
export function statusText(status: string) { return ({ DRAFT: '草稿', PENDING: '待审核', APPROVED: '审核通过', REJECTED: '已驳回', ON_SALE: '已上架', OFF_SALE: '已下架', ACTIVE: '生效中', EXPIRED: '已失效' } as Record<string, string>)[status] || status }
