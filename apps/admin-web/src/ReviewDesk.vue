<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { privateImage, request } from './api'
import { statusText, type Merchant, type Offer, type Product } from '../../shared/catalog'
defineProps<{ name: string }>()
defineEmits<{ logout: [] }>()
const tab = ref('merchants')
const merchants = ref<Merchant[]>([])
const products = ref<Product[]>([])
const offers = ref<Offer[]>([])
const reasons = ref<Record<string, string>>({})
const error = ref(''), busy = ref(false), preview = ref('')
const pending = computed(() => [merchants.value.filter(x => x.certification_status === 'PENDING').length, products.value.filter(x => x.status === 'PENDING').length, offers.value.filter(x => x.status === 'PENDING').length])
async function load() {
  const data = await Promise.all([request<Merchant[]>('/admin/merchants'), request<Product[]>('/admin/products'), request<Offer[]>('/admin/offers')])
  ;[merchants.value, products.value, offers.value] = data
}
async function run(action: () => Promise<void>) {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { await action() } catch (e) { error.value = e instanceof Error ? e.message : '操作失败' } finally { busy.value = false }
}
function refresh() { return run(load) }
function review(kind: string, item: { id: number; version: number }, result: string) {
  return run(async () => {
    const reason = reasons.value[`${kind}-${item.id}`] || ''
    if (result === 'REJECTED' && !reason.trim()) throw new Error('请填写驳回原因，方便商家修改')
    await request(`/admin/${kind}/${item.id}/audit`, 'POST', { version: item.version, result, reason })
    await load()
  })
}
function closePreview() { if (preview.value) URL.revokeObjectURL(preview.value); preview.value = '' }
function showImage(path: string) { return run(async () => { closePreview(); preview.value = await privateImage(path) }) }
onMounted(refresh); onUnmounted(closePreview)
</script>
<template>
  <div class="desk">
    <header><div><span class="eyebrow dark">LUMIÈRE · 商城管理</span><h1>审核工作台</h1><p>你好，{{ name }}。查看申请资料，确认商品与报价。</p></div><div class="header-actions"><button class="secondary" :disabled="busy" @click="refresh">刷新</button><button class="secondary" @click="$emit('logout')">退出登录</button></div></header>
    <div class="metrics"><div v-for="(label, i) in ['商家待审核', '商品待审核', '报价待审核']" :key="label"><strong>{{ pending[i] }}</strong><span>{{ label }}</span></div></div>
    <nav><button v-for="entry in [{ id: 'merchants', label: '商家认证' }, { id: 'products', label: '商品资料' }, { id: 'offers', label: '销售报价' }]" :key="entry.id" :class="{ active: tab === entry.id }" @click="tab = entry.id">{{ entry.label }}</button></nav>
    <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="busy" class="muted" role="status">正在处理…</p>
    <section v-if="tab === 'merchants'">
      <p v-if="!merchants.length" class="empty">暂无商家申请。商家提交认证后，会显示在这里。</p>
      <article v-for="m in merchants" :key="m.id"><div class="row"><h2>{{ m.shop_name }}</h2><span class="badge">{{ statusText(m.certification_status) }}</span></div><p>负责人：{{ m.legal_name }} · 联系电话：{{ m.contact_phone }}</p><p>{{ m.address }}</p><button class="link" :disabled="busy" @click="showImage(`/api/v1/files/${m.business_license_file_id}/content`)">查看营业执照</button>
        <p v-if="m.audits[0]" class="muted">最近审核：{{ statusText(m.audits[0].result) }} {{ m.audits[0].reason }}</p>
        <div v-if="m.certification_status === 'PENDING'" class="review"><input v-model="reasons[`merchants-${m.id}`]" aria-label="商家审核意见" placeholder="审核意见（驳回时必填）" maxlength="500" /><button :disabled="busy" @click="review('merchants', m, 'APPROVED')">通过认证</button><button class="reject" :disabled="busy" @click="review('merchants', m, 'REJECTED')">驳回</button></div>
      </article>
    </section>
    <section v-if="tab === 'products'">
      <p v-if="!products.length" class="empty">暂无商品。认证通过的商家可提交灯具资料。</p>
      <article v-for="p in products" :key="p.id"><div class="row"><h2>{{ p.name }}</h2><span class="badge">{{ statusText(p.status) }}</span></div><p>{{ p.category_name }} · {{ p.brand || '未填写品牌' }} · {{ p.style }} {{ p.application_space }}</p><p>{{ p.description }}</p>
        <div v-for="sku in p.skus" :key="sku.id" class="sku"><strong>{{ sku.sku_code }}</strong><p>{{ sku.attributes.color }} {{ sku.attributes.size_spec }} {{ sku.attributes.material }} {{ sku.attributes.power_watt }} W · {{ sku.attributes.color_temperature }}</p><div class="row"><button v-for="(url, i) in sku.images" :key="url" class="link" :disabled="busy" @click="showImage(url)">查看图片 {{ i + 1 }}</button></div></div>
        <p v-if="p.audits?.[0]" class="muted">最近审核：{{ statusText(p.audits[0].result) }} {{ p.audits[0].reason }}</p>
        <div v-if="p.status === 'PENDING'" class="review"><input v-model="reasons[`products-${p.id}`]" aria-label="商品审核意见" placeholder="审核意见（驳回时必填）" maxlength="500" /><button :disabled="busy" @click="review('products', p, 'APPROVED')">通过商品</button><button class="reject" :disabled="busy" @click="review('products', p, 'REJECTED')">驳回</button></div>
      </article>
    </section>
    <section v-if="tab === 'offers'">
      <p v-if="!offers.length" class="empty">暂无报价。商品审核通过后，商家可提交价格。</p>
      <article v-for="o in offers" :key="o.id"><div class="row"><h2>{{ o.product_name }}</h2><span class="badge">{{ statusText(o.status) }}</span></div><p>{{ o.shop_name }} · {{ o.sku_code }}</p><p class="price">¥ {{ o.price.toFixed(2) }} / {{ o.unit }} <small>库存 {{ o.stock_qty }}</small></p><p>{{ o.remark }}</p>
        <p v-if="o.audits?.[0]" class="muted">最近审核：{{ statusText(o.audits[0].result) }} {{ o.audits[0].reason }}</p>
        <div v-if="o.status === 'PENDING'" class="review"><input v-model="reasons[`offers-${o.id}`]" aria-label="报价审核意见" placeholder="审核意见（驳回时必填）" maxlength="500" /><button :disabled="busy" @click="review('offers', o, 'APPROVED')">通过报价</button><button class="reject" :disabled="busy" @click="review('offers', o, 'REJECTED')">驳回</button></div>
      </article>
    </section>
    <div v-if="preview" class="overlay" role="dialog" aria-label="审核图片预览" @click.self="closePreview"><div><button class="secondary" @click="closePreview">关闭预览</button><img :src="preview" alt="审核资料图片" /></div></div>
  </div>
</template>
<style scoped>
.desk{max-width:1200px;margin:auto;padding:40px 32px}.desk header,.row{display:flex;align-items:center;justify-content:space-between;gap:16px}.desk h1{margin:12px 0;font-size:34px}.desk h2{font-size:21px;margin:0}.desk p{line-height:1.7;color:#657773}.header-actions{display:flex;gap:10px}.desk button{width:auto;margin:0;padding:10px 20px;min-height:42px;white-space:nowrap}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:28px 0}.metrics>div{background:#fff;padding:25px;border-radius:14px;display:flex;align-items:center;gap:20px}.metrics strong{font-size:34px;color:#24564e}.metrics span,.muted{color:#74877e}.desk nav{display:flex;gap:12px;margin-bottom:24px}.desk nav button{background:#e5eae5;color:#466355}.desk nav button.active{background:#244f49;color:white}.desk article{padding:25px;background:white;border-radius:14px;margin:16px 0}.badge{font-size:13px;background:#eef1e7;color:#586646;padding:6px 12px;border-radius:20px}.review{display:flex;gap:10px;border-top:1px solid #edf0e9;padding-top:20px;margin-top:18px}.review input{flex:1;min-width:100px}.reject{background:#f7e9e4;color:#a15444}.link{background:#ecf3ee;color:#356652;font-size:13px}.sku{background:#f7f8f4;padding:18px;margin:12px 0;border-radius:10px}.sku .row{justify-content:flex-start}.price{font-size:25px;color:#995d35!important}.price small{font-size:14px;margin-left:20px}.empty{padding:60px;text-align:center;background:#fff;border-radius:14px}.overlay{position:fixed;inset:0;background:#172923cc;display:grid;place-items:center;z-index:10}.overlay>div{background:white;padding:20px;max-width:90vw}.overlay img{display:block;max-width:85vw;max-height:75vh;margin-top:15px}@media(max-width:700px){.desk{padding:20px}.desk header,.review{flex-wrap:wrap}.metrics{gap:8px}.metrics>div{padding:15px;display:grid;gap:2px}.metrics span{font-size:12px}}
</style>
