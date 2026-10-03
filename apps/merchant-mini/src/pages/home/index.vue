<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { chooseUpload, clearToken, currentUser, getToken, previewFile, request, type User } from '../../api'
import { statusText, type Category, type Merchant, type Offer, type Product, type ProductPage, type Sku } from '../../../../shared/catalog'
const user = ref<User | null>(null), profile = ref<Merchant | null>(null)
const categories = ref<Category[]>([]), products = ref<Product[]>([]), offers = ref<Offer[]>([])
const tab = ref('application'), busy = ref(false), error = ref(''), message = ref('')
const approved = computed(() => profile.value?.certification_status === 'APPROVED')
const application = ref({ shop_name: '', legal_name: '', contact_phone: '', address: '', business_license_file_id: 0 })
function blankSku() { return { sku_code: '', color: '', size_spec: '', material: '', power_watt: '', color_temperature: '', image_file_ids: [] as number[] } }
function blankProduct() { return { category_id: 0, name: '', brand: '', style: '', application_space: '', description: '', skus: [blankSku()] } }
const form = ref(blankProduct()), editing = ref<Product | null>(null), showForm = ref(false)
const skuEdit = ref<{ product: Product; sku: Sku } | null>(null), skuForm = ref(blankSku())
const quoteSku = ref<Sku | null>(null), quoteName = ref(''), quote = ref({ price: '', stock_qty: '', unit: '件', remark: '' })
const market = ref<ProductPage>({ items: [], total: 0, page: 1, page_size: 20 }), keyword = ref(''), selectedMarket = ref<Product | null>(null)
async function load() {
  profile.value = await request<Merchant | null>('/merchant/application')
  categories.value = await request<Category[]>('/categories')
  if (profile.value) {
    const p = profile.value
    application.value = { shop_name: p.shop_name, legal_name: p.legal_name, contact_phone: p.contact_phone, address: p.address, business_license_file_id: p.business_license_file_id }
    ;[products.value, offers.value] = await Promise.all([request<Product[]>('/merchant/products'), request<Offer[]>('/merchant/offers')])
  }
}
async function run(action: () => Promise<void>) {
  if (busy.value) return
  busy.value = true; error.value = ''; message.value = ''
  try { await action() } catch (e) { error.value = e instanceof Error ? e.message : '操作失败' } finally { busy.value = false }
}
onShow(() => run(async () => {
  if (!getToken()) { uni.reLaunch({ url: '/pages/login/index' }); return }
  user.value = await currentUser(); await load()
}))
function logout() { clearToken(); uni.reLaunch({ url: '/pages/login/index' }) }
function refresh() { return run(load) }
function uploadLicense() { return run(async () => { application.value.business_license_file_id = (await chooseUpload('LICENSE')).id }) }
function submitApplication() { return run(async () => {
  if (!application.value.business_license_file_id) throw new Error('请上传营业执照图片')
  await request('/merchant/application', 'PUT', { ...application.value, ...(profile.value ? { version: profile.value.version } : {}) }); await load(); message.value = '申请已提交，请等待管理员审核'
}) }
function uploadSku(sku: ReturnType<typeof blankSku>) { return run(async () => { if (sku.image_file_ids.length >= 6) throw new Error('每个规格最多 6 张图片'); sku.image_file_ids.push((await chooseUpload('PRODUCT')).id) }) }
function preview(id: number) { return run(() => previewFile(id)) }
function startProduct(p?: Product) {
  editing.value = p || null; form.value = blankProduct()
  if (p) Object.assign(form.value, { category_id: p.category_id, name: p.name, brand: p.brand, style: p.style, application_space: p.application_space, description: p.description })
  else form.value.category_id = categories.value[0]?.id || 0
  showForm.value = true
  nextTick(() => uni.pageScrollTo({ selector: '.product-form', duration: 200 }))
}
function categoryChanged(e: { detail: { value: string | number } }) { form.value.category_id = categories.value[Number(e.detail.value)].id }
function skuPayload(sku: ReturnType<typeof blankSku>) { return { ...sku, power_watt: sku.power_watt === '' ? null : Number(sku.power_watt) } }
function saveProduct() { return run(async () => {
  if (editing.value) { const { skus: _, ...fields } = form.value; await request('/merchant/products/'+editing.value.id, 'PUT', { ...fields, version: editing.value.version }) }
  else await request('/merchant/products', 'POST', { ...form.value, skus: form.value.skus.map(skuPayload) })
  showForm.value = false; await load(); message.value = '草稿已保存，可提交商品审核'
}) }
function submitProduct(p: Product) { return run(async () => { await request('/merchant/products/'+p.id+'/submit', 'POST', { version: p.version }); await load(); message.value = '商品已提交审核' }) }
function sale(p: Product, on_sale: boolean) { return run(async () => { await request('/merchant/products/'+p.id+'/sale', 'POST', { version: p.version, on_sale }); await load() }) }
function editSku(p: Product, s: Sku) { quoteSku.value = null; skuEdit.value = { product: p, sku: s }; skuForm.value = { sku_code: s.sku_code, color: s.attributes.color || '', size_spec: s.attributes.size_spec || '', material: s.attributes.material || '', power_watt: String(s.attributes.power_watt ?? ''), color_temperature: s.attributes.color_temperature || '', image_file_ids: [...s.image_file_ids] }; nextTick(() => uni.pageScrollTo({ selector: '.editor', duration: 200 })) }
function saveSku() { return run(async () => { if (!skuEdit.value) return; await request('/merchant/skus/'+skuEdit.value.sku.id, 'PUT', { ...skuPayload(skuForm.value), version: skuEdit.value.product.version }); skuEdit.value = null; await load(); message.value = '规格已修改，原报价已失效，请重新提交商品和报价审核' }) }
function startQuote(name: string, sku: Sku) { skuEdit.value = null; quoteSku.value = sku; quoteName.value = name; quote.value = { price: '', stock_qty: '', unit: '件', remark: '' }; nextTick(() => uni.pageScrollTo({ selector: '.editor', duration: 200 })) }
function submitQuote() { return run(async () => {
  if (!quoteSku.value || quote.value.price === '' || quote.value.stock_qty === '') throw new Error('请填写价格和库存')
  const o = await request<Offer>('/merchant/skus/'+quoteSku.value.id+'/offers', 'POST', { ...quote.value, price: Number(quote.value.price), stock_qty: Number(quote.value.stock_qty) })
  await request('/merchant/offers/'+o.id+'/submit', 'POST', { version: o.version }); quoteSku.value = null; await load(); message.value = '报价已提交审核'
}) }
function submitDraft(o: Offer) { return run(async () => { await request('/merchant/offers/'+o.id+'/submit', 'POST', { version: o.version }); await load() }) }
function searchMarket() { return run(async () => { market.value = await request<ProductPage>('/products?keyword='+encodeURIComponent(keyword.value)) }) }
function viewMarket(id: number) { return run(async () => { selectedMarket.value = await request<Product>('/products/'+id) }) }
</script>
<template>
  <view class="screen">
    <view class="top"><text>◉ 灯具商城 · 商家工作台</text><text @click="logout">退出</text></view>
    <view class="hero"><text class="title">你好，{{ user?.display_name || '商家' }}</text><text class="muted">从一盏好灯开始，经营你的店铺。</text></view>
    <view class="tabs"><button v-for="entry in [{id:'application',name:'认证'},{id:'products',name:'商品'},{id:'offers',name:'报价'},{id:'market',name:'商城选品'}]" :key="entry.id" :class="{active:tab===entry.id}" @click="tab=entry.id">{{ entry.name }}</button></view>
    <view class="toolbar"><text v-if="busy">正在处理…</text><button size="mini" :disabled="busy" @click="refresh">刷新状态</button></view>
    <view v-if="error" class="error">{{ error }}</view><view v-if="message" class="success">{{ message }}</view>
    <view v-if="tab==='application'" class="card">
      <text class="heading">商家认证</text><text class="badge">{{ profile ? statusText(profile.certification_status) : '尚未提交' }}</text>
      <view v-if="profile?.audits[0]" class="notice">最近审核：{{ statusText(profile.audits[0].result) }} {{ profile.audits[0].reason }}</view>
      <view v-if="!profile || profile.certification_status==='REJECTED'">
        <text class="label">店铺名称</text><input v-model="application.shop_name" placeholder="请输入店铺名称" maxlength="120" />
        <text class="label">负责人</text><input v-model="application.legal_name" placeholder="请输入负责人姓名" maxlength="80" />
        <text class="label">联系电话</text><input v-model="application.contact_phone" type="number" placeholder="联系电话" maxlength="20" />
        <text class="label">经营地址</text><input v-model="application.address" placeholder="经营地址" maxlength="255" />
        <button class="secondary" :disabled="busy" @click="uploadLicense">{{ application.business_license_file_id ? '重新上传营业执照' : '上传营业执照' }}</button>
        <button v-if="application.business_license_file_id" class="link" @click="preview(application.business_license_file_id)">预览已上传证照</button>
        <text class="muted">支持 JPG、PNG、WebP，最大 5 MB；证照仅本人和管理员可查看。</text><button :disabled="busy" @click="submitApplication">提交认证申请</button>
      </view>
      <view v-else><text class="heading">{{ profile.shop_name }}</text><text class="muted">{{ profile.address }}</text><text class="notice">{{ approved ? '认证已通过，可以发布商品并提交报价。' : '申请已提交，审核结果将在这里显示。' }}</text><button class="secondary" @click="preview(profile.business_license_file_id)">查看证照</button></view>
    </view>
    <view v-if="tab!=='application' && !approved" class="card notice">请先完成商家认证，再发布商品与报价。</view>
    <view v-if="tab==='products' && approved">
      <button :disabled="busy" @click="startProduct()">＋ 新建灯具商品</button>
      <view v-if="showForm" class="card product-form"><text class="heading">{{ editing ? '修改商品资料' : '新建商品草稿' }}</text>
        <text class="label">商品名称</text><input v-model="form.name" placeholder="例如：暖光黄铜台灯" maxlength="160" />
        <text class="label">灯具分类</text><picker :range="categories" range-key="name" @change="categoryChanged"><view class="picker">{{ categories.find(c=>c.id===form.category_id)?.name || '选择分类' }} ▾</view></picker>
        <input v-model="form.brand" placeholder="品牌（选填）" /><input v-model="form.style" placeholder="风格，如现代简约（选填）" /><input v-model="form.application_space" placeholder="适用空间，如书房（选填）" /><textarea v-model="form.description" placeholder="商品介绍" maxlength="5000" />
        <view v-if="!editing"><view v-for="(s,index) in form.skus" :key="index" class="sku"><text class="heading">规格 {{ index+1 }}</text><input v-model="s.sku_code" placeholder="唯一规格编码，如 LAMP-001-A" /><input v-model="s.color" placeholder="颜色" /><input v-model="s.size_spec" placeholder="尺寸" /><input v-model="s.material" placeholder="材质" /><input v-model="s.power_watt" type="digit" placeholder="功率（W）" /><input v-model="s.color_temperature" placeholder="色温，如 3000K" /><button class="secondary" :disabled="busy" @click="uploadSku(s)">添加商品图片（{{ s.image_file_ids.length }}/6）</button><view class="actions"><text v-for="(id,i) in s.image_file_ids" :key="id" @click="preview(id)">预览 {{ i+1 }}</text></view><button v-if="form.skus.length>1" class="link" @click="form.skus.splice(index,1)">移除此规格</button></view><button v-if="form.skus.length<20" class="secondary" @click="form.skus.push(blankSku())">＋ 添加规格</button></view>
        <button :disabled="busy" @click="saveProduct">保存草稿</button><button class="link" @click="showForm=false">取消编辑</button>
      </view>
      <view v-if="!products.length && !showForm" class="card notice">还没有商品。添加灯具资料与图片，开始第一笔商品审核。</view>
      <view v-for="p in products" :key="p.id" class="card"><text class="heading">{{ p.name }}</text><text class="badge">{{ statusText(p.status) }}</text><text class="muted">{{ p.category_name }} · {{ p.brand }}</text><view v-if="p.audits?.[0]" class="notice">最近审核：{{ statusText(p.audits[0].result) }} {{ p.audits[0].reason }}</view>
        <view class="actions"><button v-if="['DRAFT','REJECTED','OFF_SALE'].includes(p.status)" size="mini" class="secondary" @click="startProduct(p)">修改资料</button><button v-if="['DRAFT','REJECTED','OFF_SALE'].includes(p.status)" size="mini" :disabled="busy" @click="submitProduct(p)">提交审核</button><button v-if="['APPROVED','OFF_SALE'].includes(p.status)" size="mini" :disabled="busy" @click="sale(p,true)">上架</button><button v-if="p.status==='ON_SALE'" size="mini" class="secondary" :disabled="busy" @click="sale(p,false)">下架</button></view>
        <view v-for="s in p.skus" :key="s.id" class="sku"><text>{{ s.sku_code }} · {{ s.attributes.color }} {{ s.attributes.power_watt }} W</text><view class="actions"><text v-for="(id,i) in s.image_file_ids" :key="id" @click="preview(id)">图片 {{ i+1 }}</text></view><button v-if="['DRAFT','REJECTED','OFF_SALE'].includes(p.status)" class="secondary" @click="editSku(p,s)">修改规格及图片</button><button v-if="['APPROVED','ON_SALE','OFF_SALE'].includes(p.status)" @click="startQuote(p.name,s)">提交新报价</button></view>
      </view>
    </view>
    <view v-if="tab==='offers' && approved"><view v-if="!offers.length" class="card notice">暂无报价。请在审核通过的商品规格下提交价格。</view><view v-for="o in offers" :key="o.id" class="card"><text class="heading">{{ o.product_name }}</text><text class="badge">{{ statusText(o.status) }}</text><text class="muted">{{ o.sku_code }}</text><text class="price">¥ {{ o.price.toFixed(2) }} / {{ o.unit }}</text><text>库存 {{ o.stock_qty }}</text><view v-if="o.audits?.[0]" class="notice">最近审核：{{ statusText(o.audits[0].result) }} {{ o.audits[0].reason }}</view><button v-if="o.status==='DRAFT'" :disabled="busy" @click="submitDraft(o)">提交报价审核</button><text v-if="o.status==='REJECTED'" class="muted">请回到对应商品规格，填写新报价后重新提交。</text></view></view>
    <view v-if="tab==='market' && approved"><view class="card"><text class="heading">为商城已有灯具报价</text><input v-model="keyword" placeholder="搜索灯具名称" @confirm="searchMarket" /><button :disabled="busy" @click="searchMarket">搜索商品</button><text class="muted">共 {{ market.total }} 件，显示前 20 件；可用更具体的名称搜索。</text></view><view v-for="p in market.items" :key="p.id" class="card"><text class="heading">{{ p.name }}</text><text class="price">¥ {{ p.lowest_price }} 起</text><button class="secondary" @click="viewMarket(p.id)">选择规格报价</button></view><view v-if="selectedMarket" class="card"><text class="heading">{{ selectedMarket.name }}</text><view v-for="s in selectedMarket.skus" :key="s.id" class="sku"><text>{{ s.sku_code }} · {{ s.attributes.color }} {{ s.attributes.size_spec }}</text><button @click="startQuote(selectedMarket.name,s)">为此规格报价</button></view></view></view>
    <view v-if="skuEdit" class="card editor"><text class="heading">修改规格：{{ skuEdit.sku.sku_code }}</text><text class="notice">保存后需重新审核商品，原规格报价将失效。</text><input v-model="skuForm.sku_code" placeholder="规格编码" /><input v-model="skuForm.color" placeholder="颜色" /><input v-model="skuForm.size_spec" placeholder="尺寸" /><input v-model="skuForm.material" placeholder="材质" /><input v-model="skuForm.power_watt" type="digit" placeholder="功率（W）" /><input v-model="skuForm.color_temperature" placeholder="色温" /><view v-for="(id,i) in skuForm.image_file_ids" :key="id" class="actions"><text @click="preview(id)">预览图片 {{ i+1 }}</text><text @click="skuForm.image_file_ids.splice(i,1)">移除</text></view><button class="secondary" :disabled="busy" @click="uploadSku(skuForm)">添加图片</button><button :disabled="busy" @click="saveSku">保存规格</button><button class="link" @click="skuEdit=null">取消</button></view>
    <view v-if="quoteSku" class="card editor"><text class="heading">{{ quoteName }} · 新报价</text><text class="muted">{{ quoteSku.sku_code }} · 审核通过后替代本店此规格的旧报价</text><input v-model="quote.price" type="digit" placeholder="销售价格（元）" /><input v-model="quote.stock_qty" type="number" placeholder="库存数量" /><input v-model="quote.unit" placeholder="计价单位，如件" maxlength="20" /><textarea v-model="quote.remark" placeholder="报价备注（选填）" maxlength="500" /><button :disabled="busy" @click="submitQuote">提交报价审核</button><button class="link" @click="quoteSku=null">取消</button></view>
  </view>
</template>
<style scoped>
.screen{min-height:100vh;background:#f4f5ef;padding:40rpx 28rpx;color:#25453c}.top,.actions,.toolbar{display:flex;align-items:center;justify-content:space-between;gap:18rpx}.top{font-size:26rpx;font-weight:600}.hero{padding:60rpx 6rpx 38rpx;display:flex;flex-direction:column;gap:16rpx}.title{font-size:44rpx;font-weight:600}.muted{display:block;color:#7b8a80;font-size:24rpx;line-height:1.8;margin:14rpx 0}.tabs{display:flex;gap:10rpx}.tabs button{font-size:24rpx;padding:0 16rpx;margin:0;background:#e6ebe1;color:#42624c;flex:1}.tabs button.active{background:#285447;color:#fff}.toolbar{justify-content:flex-end;font-size:23rpx;padding:18rpx 0}.card{padding:30rpx;background:#fff;border-radius:20rpx;margin:22rpx 0;box-shadow:0 10rpx 30rpx #284d3810}.heading{display:block;font-size:31rpx;font-weight:600;margin-bottom:18rpx}.badge{display:inline-block;background:#edf0df;color:#747d42;padding:8rpx 20rpx;border-radius:30rpx;font-size:22rpx}.label{display:block;margin:22rpx 0 10rpx;font-size:25rpx}input,textarea,.picker{box-sizing:border-box;background:#f6f7f3;border:1px solid #e0e6dc;border-radius:10rpx;padding:20rpx;font-size:26rpx;margin:16rpx 0;width:100%}input{height:85rpx}textarea{height:160rpx}button{background:#2b5749;color:white;font-size:27rpx;border-radius:10rpx;margin:18rpx 0 0}button::after{border:0}button.secondary{background:#eaf0e7;color:#365c43}button.link{background:transparent;color:#6d806e;font-size:24rpx}.actions{justify-content:flex-start;flex-wrap:wrap;font-size:23rpx;color:#488762;margin:18rpx 0}.actions button{margin:0}.sku{background:#f8f8f2;padding:23rpx;border-radius:12rpx;margin:22rpx 0}.notice{display:block;background:#faf7ec;color:#8b774e;padding:20rpx;font-size:24rpx;line-height:1.8;margin:18rpx 0}.error{padding:22rpx;color:#a04436;background:#fbece6;border-radius:12rpx}.success{padding:22rpx;color:#356948;background:#e6f1e3;border-radius:12rpx}.price{display:block;color:#b16b39;font-size:38rpx;margin:20rpx 0}.editor{border:2px solid #b3c7a4}
</style>
