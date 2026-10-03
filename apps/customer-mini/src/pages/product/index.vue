<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { BASE, request } from '../../api'
import type { Product } from '../../../../shared/catalog'
const product = ref<Product | null>(null), selected = ref(0), error = ref(''), busy = ref(false)
let productId = 0
const sku = computed(() => product.value?.skus[selected.value])
async function load() { busy.value=true; error.value=''; try { product.value=await request<Product>(`/products/${productId}`) } catch(e) { product.value=null; error.value=e instanceof Error ? e.message : '加载失败' } finally { busy.value=false } }
onLoad(options => { productId=Number(options?.id); load() })
function preview(url: string) { uni.previewImage({ current: BASE+url, urls: sku.value?.images.map(x=>BASE+x) || [] }) }
</script>
<template><view class="screen"><view v-if="busy" class="notice">正在加载商品…</view><view v-if="error" class="notice">{{ error }}<button @click="load">重新加载</button></view><view v-if="product">
  <swiper v-if="sku?.images.length" class="gallery" indicator-dots><swiper-item v-for="url in sku.images" :key="url"><image :src="BASE+url" mode="aspectFit" @click="preview(url)" /></swiper-item></swiper>
  <view class="card"><text class="category">{{ product.category_name }} · {{ product.brand }}</text><text class="title">{{ product.name }}</text><text class="price">¥ {{ product.lowest_price?.toFixed(2) }} 起</text><text class="muted">{{ product.style }} {{ product.application_space }}</text><text class="description">{{ product.description }}</text></view>
  <view class="card"><text class="heading">选择规格</text><view class="options"><button v-for="(s,i) in product.skus" :key="s.id" :class="{active:selected===i}" @click="selected=i">{{ s.attributes.color || s.sku_code }} {{ s.attributes.size_spec }}</button></view><view v-if="sku" class="attributes"><text>规格编码：{{ sku.sku_code }}</text><text>材质：{{ sku.attributes.material || '未填写' }}</text><text>功率：{{ sku.attributes.power_watt ?? '未填写' }} W</text><text>色温：{{ sku.attributes.color_temperature || '未填写' }}</text></view></view>
  <view class="card"><text class="heading">商家报价</text><text v-if="!sku?.offers.length" class="muted">当前规格暂无有货报价，可查看其他规格。</text><view v-for="o in sku?.offers" :key="o.id" class="offer"><view><text class="shop">{{ o.shop_name }}</text><text class="muted">库存 {{ o.stock_qty }} {{ o.unit }}</text><text class="muted">{{ o.remark }}</text></view><text class="offer-price">¥ {{ o.price.toFixed(2) }}<text>/{{ o.unit }}</text></text></view></view>
</view></view></template>
<style scoped>
.screen{min-height:100vh;background:#f7f5ee;padding-bottom:40rpx;color:#2d493a}.gallery{height:620rpx;background:#eeebe1}.gallery image{width:100%;height:100%}.card{background:#fff;margin:24rpx;padding:32rpx;border-radius:18rpx}.category,.muted{display:block;color:#8a927f;font-size:24rpx;line-height:1.8}.title{display:block;font-size:42rpx;line-height:1.5;margin:18rpx 0}.price{display:block;font-size:40rpx;color:#b17b48;margin:22rpx 0}.description{display:block;line-height:1.9;font-size:27rpx;margin-top:25rpx;white-space:pre-wrap}.heading{font-size:31rpx;font-weight:600}.options{display:flex;gap:14rpx;flex-wrap:wrap;margin:25rpx 0}.options button{margin:0;background:#eff1e7;color:#62735a;font-size:24rpx}.options button.active{background:#365d44;color:#fff}.attributes{display:flex;flex-direction:column;gap:13rpx;font-size:25rpx;color:#87907b}.offer{display:flex;align-items:center;justify-content:space-between;border-top:1px solid #eff1e8;padding:28rpx 0;margin-top:20rpx;gap:20rpx}.shop{font-size:29rpx}.offer-price{color:#a36d3c;font-size:34rpx;white-space:nowrap}.offer-price text{font-size:22rpx;color:#929780}.notice{padding:80rpx 35rpx;color:#8a927f;font-size:28rpx;text-align:center}button::after{border:0}
</style>
