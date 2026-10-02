<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { clearToken, currentUser, getToken, type User } from '../../api'
const user=ref<User|null>(null)
onShow(async()=>{if(!getToken()){uni.reLaunch({url:'/pages/login/index'});return}try{user.value=await currentUser()}catch{clearToken();uni.reLaunch({url:'/pages/login/index'})}})
function logout(){clearToken();uni.reLaunch({url:'/pages/login/index'})}
</script>
<template><view class="screen"><view class="top"><text>◉ 灯具商城</text><text class="tag">MERCHANT</text></view><view class="welcome">你好，{{user?.display_name||'商家'}}<text>今天也让好灯被更多人看到。</text></view><view class="card"><text class="label">商家账号</text><text class="value">{{user?.roles?.includes('MERCHANT')?'已登录':'验证中'}}</text><text class="meta">账号状态 {{user?.status||'加载中'}}</text></view><view class="notice">商品发布、报价与订单管理功能即将开放。</view><button @click="logout">退出登录</button></view></template>
<style scoped>.screen{min-height:100vh;background:#f5f6f3;padding:52rpx 42rpx}.top{display:flex;justify-content:space-between;align-items:center;color:#235152;font-size:30rpx;font-weight:700}.tag{font-size:18rpx;letter-spacing:3rpx;color:#b0885f}.welcome{display:flex;flex-direction:column;margin:120rpx 0 55rpx;font-size:48rpx;color:#264545;font-weight:600}.welcome text{font-size:26rpx;font-weight:400;color:#89948e;margin-top:22rpx}.card{background:#fff;border-radius:26rpx;padding:46rpx;display:flex;flex-direction:column;box-shadow:0 20rpx 55rpx #20403410}.label{font-size:23rpx;color:#939d96}.value{font-size:41rpx;color:#285c53;margin-top:19rpx}.meta{font-size:24rpx;color:#98a49b;margin-top:18rpx}.notice{font-size:25rpx;line-height:1.8;color:#7d8982;margin-top:45rpx}button{background:#e2ebe6;color:#2b514b;margin-top:70rpx;border-radius:14rpx;font-size:27rpx}</style>
