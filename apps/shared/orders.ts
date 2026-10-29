export type Address = { id: number; recipient: string; phone: string; address: string }
export type Review = { id: number; rating: number; content: string; created_at: string }
export type OrderItem = { id: number; product_id: number; product_name: string; sku_code: string; specification: Record<string, string | null>; cover_file_id: number | null; unit_price: string; unit: string; quantity: number; review: Review | null }
export type Order = { id: number; order_no: string; shop_name: string; status: string; version: number; total_amount: string; address_snapshot: Omit<Address, 'id'>; cancellation_reason: string | null; created_at: string; items: OrderItem[]; simulated: boolean; shipment: { carrier: string; tracking_no: string; proof_file_id: number } | null; events: { action: string; from_status: string | null; to_status: string; reason: string | null; created_at: string }[] }
export type OrderPage = { items: Order[]; total: number; page: number; page_size: number }
export function orderStatus(status: string) { return ({ PENDING_CONFIRM: '待确认', TO_SHIP: '待发货', SHIPPED: '已发货', COMPLETED: '已完成', CANCELLED: '已取消' } as Record<string, string>)[status] || status }
export function money(value: string | number) { return Number(value).toFixed(2) }
// API/database timestamps are UTC. Show the project's China-local time explicitly.
export function orderTime(value: string) { const stamp = new Date(/[zZ]$|[+-]\d\d:\d\d$/.test(value) ? value : value+'Z').getTime(); return Number.isNaN(stamp) ? value : new Date(stamp+8*3600000).toISOString().slice(0,19).replace('T',' ')+'（北京时间）' }
