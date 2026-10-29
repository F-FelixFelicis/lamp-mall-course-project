<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getToken, request } from '../../api'
import type { Offer, Product } from '../../../../shared/catalog'
import type { Address, Order } from '../../../../shared/orders'
const product = ref<Product | null>(null), offer = ref<Offer | null>(null), addresses = ref<Address[]>([])
const addressId = ref(0), quantity = ref('1'), busy = ref(false), error = ref(''), placed = ref<Order | null>(null)
const form = ref({ recipient: '', phone: '', address: '' }), editing = ref(0)
let productId = 0, offerId = 0, submitKey = '', lastPayload = ''
const total = computed(() => ((offer.value?.price || 0) * Number(quantity.value || 0)).toFixed(2))
async function run(action: () => Promise<void>) { if (busy.value) return; busy.value = true; error.value = ''; try { await action() } catch(e) { error.value = e instanceof Error ? e.message : '操作失败' } finally { busy.value = false } }
async function load() {
  product.value = await request<Product>('/products/'+productId)
  offer.value = product.value.skus.flatMap(s => s.offers).find(o => o.id === offerId) || null
  if (!offer.value) throw new Error('该报价已失效，请返回商品页重新选择商家')
  addresses.value = await request<Address[]>('/addresses')
  if (!addresses.value.some(a => a.id === addressId.value)) addressId.value = addresses.value[0]?.id || 0
}
onLoad(options => { productId = Number(options?.product); offerId = Number(options?.offer); if (!getToken()) { uni.navigateTo({ url: '/pages/login/index' }); error.value = '请先登录，返回后刷新报价'; return }; run(load) })
function edit(a?: Address) { editing.value = a?.id || 0; form.value = a ? { recipient:a.recipient, phone:a.phone, address:a.address } : { recipient:'',phone:'',address:'' } }
function saveAddress() { return run(async () => { const a = await request<Address>(editing.value ? '/addresses/'+editing.value : '/addresses', editing.value ? 'PUT' : 'POST', form.value); addressId.value = a.id; edit(); await load() }) }
function removeAddress(a: Address) { uni.showModal({ title:'删除地址',content:'已创建订单中的地址快照会保留。',success:r => { if(r.confirm) run(async () => { await request('/addresses/'+a.id,'DELETE'); await load() }) } }) }
function submit() { return run(async () => {
  if (!offer.value || !addressId.value) throw new Error('请选择有效报价和收货地址')
  const qty = Number(quantity.value)
  if (!Number.isInteger(qty) || qty < 1 || qty > 999) throw new Error('数量请输入 1 到 999 的整数')
  const payload = { address_id:addressId.value,items:[{ offer_id:offer.value.id,quantity:qty,expected_price:offer.value.price.toFixed(2) }] }
  const signature = JSON.stringify(payload)
  if (signature !== lastPayload) { submitKey = 'checkout_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2); lastPayload = signature }
  placed.value = await request<Order>('/orders','POST',{ ...payload,idempotency_key:submitKey })
}) }
function orders() { uni.navigateTo({url:'/pages/orders/index'}) }
</script>
<template><view class="screen">
  <text class="title">确认模拟订单</text><text class="notice">课程履约演示，不收取款项。请使用测试收货信息。</text>
  <view v-if="error" class="error">{{ error }}</view>
  <view v-if="placed" class="card"><text class="heading">订单已提交 · 待商家确认</text><text>{{ placed.order_no }}</text><text>合计 ¥ {{ Number(placed.total_amount).toFixed(2) }}</text><button @click="orders">查看我的订单</button></view>
  <view v-else>
    <view class="card"><text class="heading">{{ product?.name || '商品信息' }}</text><text v-if="offer">{{ offer.shop_name }} · 单价 ¥ {{ offer.price.toFixed(2) }} / {{ offer.unit }} · 库存 {{ offer.stock_qty }}</text><text class="label">购买数量</text><input v-model="quantity" type="number" maxlength="3" /><text class="total">合计 ¥ {{ total }}</text><button class="secondary" :disabled="busy" @click="run(load)">刷新报价与地址</button></view>
    <view class="card"><text class="heading">收货地址</text><text v-if="!addresses.length">请先添加测试地址。</text><view v-for="a in addresses" :key="a.id" class="address"><text @click="addressId=a.id">{{ addressId===a.id ? '●' : '○' }} {{ a.recipient }} · {{ a.phone }}<br/>{{ a.address }}</text><view class="row"><button size="mini" class="secondary" :disabled="busy" @click="edit(a)">编辑</button><button size="mini" class="secondary" :disabled="busy" @click="removeAddress(a)">删除</button></view></view></view>
    <view class="card"><text class="heading">{{ editing ? '编辑地址' : '添加测试地址' }}</text><input v-model="form.recipient" placeholder="收货人" maxlength="80"/><input v-model="form.phone" placeholder="联系电话" maxlength="20"/><textarea v-model="form.address" placeholder="详细地址（至少 5 个字符）" maxlength="255"/><view class="row"><button :disabled="busy" @click="saveAddress">保存地址</button><button v-if="editing" class="secondary" @click="edit()">取消编辑</button></view></view>
    <button :disabled="busy || !offer || !addressId" @click="submit">{{ busy ? '正在处理…' : '确认并提交模拟订单' }}</button><button class="secondary" @click="orders">我的订单</button>
  </view>
</view></template>
<style scoped>
.screen{max-width:720px;margin:auto;padding:32rpx;background:#f7f5ee;min-height:100vh;color:#2c4238}.title{display:block;font-size:40rpx;font-weight:700;margin:20rpx 0}.card{background:white;padding:30rpx;border-radius:16rpx;margin:24rpx 0;display:flex;flex-direction:column;gap:18rpx;font-size:26rpx;line-height:1.7}.heading{font-size:30rpx;font-weight:600}.notice{display:block;color:#88714d;font-size:24rpx;line-height:1.8}.error{padding:24rpx;background:#fcece6;color:#a04436;margin:20rpx 0}.label{font-size:24rpx}input,textarea{box-sizing:border-box;width:100%;padding:18rpx;background:#f5f5ef;border-radius:8rpx;font-size:26rpx}input{height:80rpx}textarea{height:150rpx}.total{color:#a26b39;font-size:34rpx}.row{display:flex;gap:18rpx}.address{padding:20rpx 0;border-bottom:1px solid #e9eddf}button{background:#315745;color:white;font-size:26rpx;margin:20rpx 0;border-radius:10rpx}button::after{border:0}button.secondary{background:#e5ecdf;color:#315745}
</style>
