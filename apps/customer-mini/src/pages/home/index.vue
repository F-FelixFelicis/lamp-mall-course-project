<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { BASE, request } from '../../api'
import type { Category, ProductCard, ProductPage } from '../../../../shared/catalog'
const categories = ref<Category[]>([]), items = ref<ProductCard[]>([])
const keyword = ref(''), category = ref(0), sort = ref('newest'), total = ref(0), page = ref(1), busy = ref(false), error = ref('')
const sorts = [{ name: '最新上架', value: 'newest' }, { name: '价格从低到高', value: 'price_asc' }, { name: '价格从高到低', value: 'price_desc' }]
async function load(reset = true) {
  if (busy.value) return
  busy.value = true; error.value = ''
  const next = reset ? 1 : page.value + 1
  try {
    const query = '/products?page='+next+'&page_size=12&keyword='+encodeURIComponent(keyword.value)+'&sort='+sort.value+(category.value ? '&category_id='+category.value : '')
    const result = await request<ProductPage>(query)
    items.value = reset ? result.items : [...items.value, ...result.items]; total.value = result.total; page.value = next
  } catch (e) { error.value = e instanceof Error ? e.message : '商品加载失败' } finally { busy.value = false }
}
onShow(async () => { try { categories.value = await request<Category[]>('/categories') } catch { error.value = '分类加载失败，请刷新重试' }; await load() })
function selectCategory(id: number) { if (busy.value) return; category.value = id; load() }
function selectSort(e: { detail: { value: string | number } }) { sort.value = sorts[Number(e.detail.value)].value; load() }
function open(id: number) { uni.navigateTo({ url: '/pages/product/index?id='+id }) }
function account() { uni.navigateTo({ url: '/pages/login/index' }) }
</script>
<template>
  <view class="screen"><view class="top"><text>◉ LUMIÈRE · 灯具商城</text><text @click="account">账号登录</text></view><view class="hero"><text class="eyebrow">LIGHT FOR EVERYDAY LIVING</text><text class="title">把好光，带回家。</text><text class="subtitle">挑选适合空间的灯，比较值得信赖的报价。</text></view>
    <view class="search"><input v-model="keyword" placeholder="搜索台灯、吊灯、吸顶灯…" confirm-type="search" @confirm="load()" /><button size="mini" :disabled="busy" @click="load()">搜索</button></view>
    <scroll-view scroll-x class="categories"><text :class="{ selected: category===0 }" @click="selectCategory(0)">全部灯具</text><text v-for="c in categories" :key="c.id" :class="{selected:category===c.id}" @click="selectCategory(c.id)">{{ c.name }}</text></scroll-view>
    <view class="bar"><text>{{ total }} 件灯具</text><picker :range="sorts" range-key="name" :disabled="busy" @change="selectSort"><text>{{ sorts.find(s=>s.value===sort)?.name }} ▾</text></picker></view>
    <view v-if="error" class="empty">{{ error }}<button :disabled="busy" @click="load()">重新加载</button></view><view v-if="!busy && !error && !items.length" class="empty"><text>还没找到合适的灯。</text><text>试试其他分类或关键词；新商品审核上架后会出现在这里。</text></view>
    <view class="grid"><view v-for="p in items" :key="p.id" class="product" @click="open(p.id)"><image v-if="p.cover_url" :src="BASE+p.cover_url" mode="aspectFill" /><view class="copy"><text class="category">{{ p.category_name }}</text><text class="name">{{ p.name }}</text><text class="price">¥ {{ p.lowest_price?.toFixed(2) }} <text>起</text></text></view></view></view>
    <view v-if="busy" class="empty">正在寻找好灯…</view><button v-if="items.length<total" :disabled="busy" @click="load(false)">加载更多</button><text class="foot">好光照亮日常，每一盏都认真挑选。</text>
  </view>
</template>
<style scoped>
.screen{min-height:100vh;background:#f7f5ee;padding:42rpx 30rpx;color:#2c4238}.top{display:flex;justify-content:space-between;font-size:24rpx;font-weight:600}.hero{padding:72rpx 5rpx 52rpx;display:flex;flex-direction:column}.eyebrow{font-size:18rpx;letter-spacing:3rpx;color:#b09060}.title{font-size:57rpx;margin:20rpx 0}.subtitle{font-size:24rpx;line-height:1.8;color:#7e897a}.search{display:flex;gap:18rpx;padding:16rpx;background:white;border-radius:16rpx}.search input{flex:1;min-width:0;font-size:26rpx;height:65rpx;padding-left:12rpx}.search button{margin:0}.categories{white-space:nowrap;margin:32rpx 0}.categories text{display:inline-block;padding:13rpx 24rpx;margin-right:12rpx;border-radius:30rpx;font-size:24rpx;color:#7b8271;background:#edece3}.categories .selected{background:#315745;color:#fff}.bar{display:flex;justify-content:space-between;color:#87907f;font-size:23rpx;margin:25rpx 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:22rpx}.product{background:#fff;border-radius:18rpx;overflow:hidden}.product image{width:100%;height:300rpx;background:#eeebe1}.copy{padding:23rpx;display:flex;flex-direction:column;gap:12rpx}.category{font-size:20rpx;color:#9a9d8c}.name{font-size:28rpx;font-weight:600;line-height:1.5}.price{font-size:31rpx;color:#a77042}.price text{font-size:21rpx;color:#949a85}button{background:#315745;color:#fff;border-radius:10rpx;font-size:25rpx;margin:28rpx 0}button::after{border:0}.empty{display:flex;flex-direction:column;gap:20rpx;text-align:center;line-height:1.8;color:#8b947f;font-size:25rpx;padding:65rpx 30rpx}.foot{display:block;text-align:center;padding:55rpx 0;color:#9eaa95;font-size:21rpx}
</style>
