<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { BASE,getToken,request } from '../../api'
import type { Category } from '../../../../shared/catalog'
import ImageSearchPanel from '../../components/ImageSearchPanel.vue'
const categories=ref<Category[]>([]),error=ref('')
onShow(async()=>{try{categories.value=await request<Category[]>('/categories')}catch{error.value='分类加载失败，仍可直接按图片搜索。'}})
function open(id:number){uni.navigateTo({url:'/pages/product/index?id='+id})}
</script>
<template><view class="screen"><text v-if="error" class="notice">{{ error }}</text><ImageSearchPanel :base="BASE" :token="getToken()" :categories="categories" @open="open"/></view></template>
<style scoped>.screen{min-height:100vh;background:#f7f5ee}.notice{display:block;padding:24rpx;color:#8a7250}</style>
