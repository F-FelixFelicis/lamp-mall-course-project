<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { BASE,getToken,request } from '../../api'
import type { Category,Product } from '../../../../shared/catalog'
import ImageSearchPanel from '../../components/ImageSearchPanel.vue'
const categories=ref<Category[]>([]),product=ref<Product|null>(null),error=ref('')
onShow(async()=>{try{categories.value=await request<Category[]>('/categories')}catch{error.value='分类加载失败'}})
async function open(id:number){try{product.value=await request<Product>('/products/'+id)}catch(e){error.value=e instanceof Error?e.message:'商品加载失败'}}
</script>
<template><view class="screen"><text v-if="error" class="error">{{ error }}</text><view v-if="product" class="detail"><button @click="product=null">返回图搜结果</button><text class="title">{{ product.name }}</text><text>{{ product.description }}</text><view v-for="s in product.skus" :key="s.id"><text>{{ s.sku_code }} · {{ s.attributes.color }}</text><image v-for="url in s.images" :key="url" :src="BASE+url" mode="aspectFit"/><text v-for="o in s.offers" :key="o.id">{{ o.shop_name }} · ¥ {{ o.price.toFixed(2) }} · 库存 {{ o.stock_qty }}</text></view><text>需要为商品报价时，可回商家工作台的“商城选品”查看并提交。</text></view><ImageSearchPanel v-show="!product" :base="BASE" :token="getToken()" :categories="categories" @open="open"/></view></template>
<style scoped>.screen{min-height:100vh;background:#f5f6ef}.detail{max-width:900px;margin:auto;padding:32rpx;display:flex;flex-direction:column;gap:24rpx;color:#2c4238}.title{font-size:34rpx;font-weight:700}.detail text{display:block;font-size:26rpx;line-height:1.8;margin:20rpx 0}.detail image{width:100%;height:360rpx}button{background:#315745;color:white;font-size:26rpx}.error{padding:24rpx;color:#a04436}</style>
