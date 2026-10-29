<script setup lang="ts">
import { ref } from 'vue'
import type { Category } from './catalog'
import type { ImageSearchResult } from './image-search'
const props=defineProps<{base:string;token:string;categories:Category[]}>()
const emit=defineEmits<{open:[id:number]}>()
const selected=ref(''),busy=ref(false),error=ref(''),result=ref<ImageSearchResult|null>(null),category=ref(0),method=ref(0)
const methods=['整体外观','颜色分布']
function submit(path=selected.value){
  if(!path||busy.value)return
  selected.value=path;busy.value=true;error.value='';result.value=null
  const formData:Record<string,string>={method:method.value===0?'deep':'color',k:'5'}
  if(category.value)formData.category_id=String(category.value)
  uni.uploadFile({url:props.base+'/api/v1/search/image',filePath:path,name:'file',formData,
    header:props.token?{Authorization:'Bearer '+props.token}:{},
    success:r=>{try{const body=JSON.parse(r.data);if(r.statusCode<200||r.statusCode>=300)throw new Error(body.message||'图搜暂时不可用');result.value=body}catch(e){error.value=e instanceof Error?e.message:'无法读取图搜结果'}},
    fail:()=>{error.value='连接失败，请稍后重试；仍可返回使用文字搜索。'},complete:()=>{busy.value=false}})
}
function choose(){if(busy.value)return;uni.chooseImage({count:1,sizeType:['compressed'],success:r=>submit(r.tempFilePaths[0]),fail:r=>{if(!r.errMsg.includes('cancel'))error.value='无法选择图片，请检查相册权限'}})}
function categoryChanged(e:{detail:{value:string|number}}){category.value=Number(e.detail.value)===0?0:props.categories[Number(e.detail.value)-1].id;submit()}
function methodChanged(e:{detail:{value:string|number}}){method.value=Number(e.detail.value);submit()}
</script>
<template><view class="panel"><text class="title">图片找相似灯具</text><text class="intro">上传单盏灯的清晰照片，比较灯具外观与当前报价。</text><text class="privacy">参考图片仅用于本次检索，服务端不保存原图。支持 JPG、PNG、WebP，最大 5 MB。</text>
<view class="controls"><picker :range="['全部灯型',...categories.map(c=>c.name)]" :disabled="busy" @change="categoryChanged"><text>{{ category?categories.find(c=>c.id===category)?.name:'全部灯型' }} ▾</text></picker><picker :range="methods" :disabled="busy" @change="methodChanged"><text>{{ methods[method] }} ▾</text></picker></view>
<image v-if="selected" class="query" :src="selected" mode="aspectFit"/><view class="actions"><button :disabled="busy" @click="choose">{{ selected?'更换图片':'选择参考图片' }}</button><button v-if="selected" class="secondary" :disabled="busy" @click="submit()">重新检索</button></view>
<view v-if="busy" class="notice">正在比较灯具外观…</view><view v-if="error" class="error">{{ error }}</view>
<view v-if="result"><text class="notice">{{ result.warning }}</text><view v-if="!result.items.length" class="empty">暂无可购买候选，试试其他图片或文字搜索。</view><view class="grid"><view v-for="item in result.items" :key="item.sku_id" class="item" @click="emit('open',item.product_id)"><image :src="base+item.matched_image_url" mode="aspectFit"/><view class="copy"><text class="category">{{ item.category_name }} · {{ item.sku_code }}</text><text class="name">{{ item.product_name }}</text><text class="price">{{ item.is_demo?'演示价 ':'' }}¥ {{ item.lowest_price.toFixed(2) }} 起</text><text class="score">相似分数 {{ item.score.toFixed(3) }} · 查看商品 →</text></view></view></view></view>
<text class="foot">相似分数用于排序，不能确认同款、品牌或技术参数。背景较复杂时，可先裁剪到单盏灯再上传。</text></view></template>
<style scoped>
.panel{max-width:1000px;margin:auto;padding:32rpx;color:#2c4238}.title{display:block;font-size:42rpx;font-weight:700;margin:20rpx 0}.intro,.privacy,.notice,.foot{display:block;font-size:25rpx;line-height:1.8;margin:20rpx 0}.privacy,.foot{color:#7b8872;font-size:23rpx}.controls,.actions{display:flex;gap:20rpx;flex-wrap:wrap;align-items:center}.controls picker{background:white;border:1px solid #e5e8df;padding:20rpx;border-radius:12rpx;font-size:25rpx}.query{width:100%;height:300rpx;background:#eceee5;margin-top:24rpx;border-radius:16rpx}.actions button{margin:24rpx 0}button{background:#315745;color:white;font-size:25rpx;padding:0 30rpx;border-radius:10rpx}button::after{border:0}button.secondary{background:#e4ebdc;color:#315745}.notice{color:#6c775e}.error{padding:24rpx;border-radius:10rpx;background:#fbece6;color:#a04436;font-size:26rpx}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20rpx}.item{background:white;border-radius:16rpx;overflow:hidden;cursor:pointer}.item image{width:100%;height:280rpx;background:#eeeae0}.copy{padding:24rpx;display:flex;flex-direction:column;gap:12rpx}.name{font-size:28rpx;font-weight:600}.category,.score{font-size:21rpx;color:#7c8873;overflow-wrap:anywhere}.price{font-size:29rpx;color:#a17040}.empty{padding:40rpx;background:#fff;font-size:26rpx;line-height:1.8}.foot{padding:24rpx 0}@media(min-width:768px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}.title{font-size:32px}.intro{font-size:16px}.privacy,.foot{font-size:14px}.item image{height:220px}.name{font-size:17px}.category,.score{font-size:13px}.price{font-size:21px}.query{height:220px}.panel{padding:28px}.notice{font-size:15px}}
</style>
