<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { privateImage, request } from './api'
import { money, orderTime, orderStatus, type Order, type OrderPage } from '../../shared/orders'
const orders=ref<Order[]>([]), selected=ref<Order|null>(null), busy=ref(false), error=ref(''), page=ref(0), total=ref(0), preview=ref('')
async function run(action:()=>Promise<void>){if(busy.value)return;busy.value=true;error.value='';try{await action()}catch(e){error.value=e instanceof Error?e.message:'加载失败'}finally{busy.value=false}}
async function load(reset=true){const next=reset?1:page.value+1;const result=await request<OrderPage>('/admin/orders?page='+next);orders.value=reset?result.items:[...orders.value,...result.items];total.value=result.total;page.value=next;if(selected.value)selected.value=await request<Order>('/orders/'+selected.value.id)}
function detail(o:Order){return run(async()=>{selected.value=await request<Order>('/orders/'+o.id)})}
function close(){if(preview.value)URL.revokeObjectURL(preview.value);preview.value=''}
function show(id:number){return run(async()=>{close();preview.value=await privateImage('/api/v1/files/'+id+'/content')})}
onMounted(()=>run(()=>load()));onUnmounted(close)
</script>
<template><section class="orders"><div class="row"><h2>订单查询</h2><button :disabled="busy" @click="run(()=>load())">刷新订单</button></div><p>模拟履约订单。管理员可核查订单快照、状态轨迹与发货凭证。</p><p v-if="error" role="alert">{{ error }}</p><p v-if="busy">正在加载…</p>
<article v-if="selected"><button @click="selected=null">返回列表</button><h3>{{ selected.order_no }}</h3><p>{{ selected.shop_name }} · {{ orderStatus(selected.status) }} · ¥ {{ money(selected.total_amount) }}</p><p>{{ selected.address_snapshot.recipient }} · {{ selected.address_snapshot.phone }} · {{ selected.address_snapshot.address }}</p><div v-for="i in selected.items" :key="i.id"><p>{{ i.product_name }} · {{ i.sku_code }} · ¥ {{ money(i.unit_price) }} × {{ i.quantity }}</p><p>{{ Object.values(i.specification).filter(Boolean).join(' · ') }}</p><button v-if="i.cover_file_id" @click="show(i.cover_file_id)">查看商品快照图片</button><p v-if="i.review">评价 {{ i.review.rating }} 星 · {{ i.review.content }}</p></div><p v-if="selected.cancellation_reason">取消原因：{{ selected.cancellation_reason }}</p><div v-if="selected.shipment"><p>{{ selected.shipment.carrier }} · {{ selected.shipment.tracking_no }}</p><button @click="show(selected.shipment.proof_file_id)">查看发货凭证</button></div><h3>状态轨迹</h3><p v-for="(e,i) in selected.events" :key="i">{{ orderTime(e.created_at) }} · {{ orderStatus(e.to_status) }} {{ e.reason }}</p></article>
<div v-else><p v-if="!orders.length&&!busy">暂无订单。</p><article v-for="o in orders" :key="o.id"><div class="row"><h3>{{ o.shop_name }} · {{ orderStatus(o.status) }}</h3><button @click="detail(o)">查看详情</button></div><p>{{ o.order_no }} · ¥ {{ money(o.total_amount) }} · {{ orderTime(o.created_at) }}</p><p>{{ o.items.map(i=>i.product_name).join('、') }}</p></article><button v-if="orders.length<total" :disabled="busy" @click="run(()=>load(false))">加载更多</button></div>
<div v-if="preview" class="overlay" role="dialog" aria-label="订单图片预览" @click.self="close"><div><button @click="close">关闭</button><img :src="preview" alt="订单相关图片"/></div></div></section></template>
<style scoped>
.orders article{padding:24px;background:white;margin:18px 0;border-radius:14px;overflow-wrap:anywhere}.row{display:flex;justify-content:space-between;align-items:center;gap:18px}.orders button{width:auto;padding:10px 20px;margin:8px 0}.orders p{line-height:1.8;color:#60766c}.overlay{position:fixed;inset:0;background:#172923cc;display:grid;place-items:center;z-index:20}.overlay>div{background:white;padding:20px}.overlay img{display:block;max-width:85vw;max-height:75vh}
</style>
