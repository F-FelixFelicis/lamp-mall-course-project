<script setup lang="ts">
import { ref } from 'vue'
import { login } from '../../api'
const account = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')
async function submit() { error.value=''; busy.value=true; try { await login(account.value,password.value); uni.reLaunch({url:'/pages/home/index'}) } catch(cause) { error.value=cause instanceof Error?cause.message:'登录失败' } finally { busy.value=false } }
</script>
<template><view class="screen"><view class="brand">◉ <text>灯具商城</text></view><view class="hero"><text class="kicker">MERCHANT STUDIO</text><text class="title">好灯，从好商家开始。</text><text class="sub">登录后管理你的灯具与订单。</text></view><view class="card"><text class="card-title">商家登录</text><input v-model="account" placeholder="商家账号"/><input v-model="password" password placeholder="密码"/><text v-if="error" class="error">{{ error }}</text><button :disabled="busy" @click="submit">{{busy?'请稍候…':'进入工作台'}}</button></view><text class="foot">LUMIÈRE · 商家工作台 v0.1</text></view></template>
<style scoped>.screen{min-height:100vh;padding:48rpx 42rpx;background:linear-gradient(160deg,#e9eee8 0,#f5f6f3 47%)}.brand{color:#1d4d4e;font-size:40rpx;font-weight:700}.brand text{font-size:28rpx;margin-left:15rpx}.hero{display:flex;flex-direction:column;margin:120rpx 0 75rpx}.kicker{font-size:20rpx;letter-spacing:6rpx;color:#ae8757}.title{font-size:53rpx;line-height:1.4;font-weight:600;margin:27rpx 0;color:#244444}.sub{font-size:26rpx;color:#8a9690}.card{background:#fff;border-radius:28rpx;padding:47rpx;box-shadow:0 24rpx 55rpx #20403412}.card-title{font-size:33rpx;font-weight:600;display:block;margin-bottom:27rpx}input{height:95rpx;border-bottom:1rpx solid #e0e8e4;margin-top:14rpx;font-size:27rpx}button{background:#245352;color:#fff;border-radius:14rpx;margin-top:45rpx;font-size:29rpx}.error{display:block;color:#bc4c43;font-size:23rpx;margin-top:20rpx}.foot{display:block;text-align:center;margin-top:80rpx;font-size:20rpx;color:#a0aba4}</style>
