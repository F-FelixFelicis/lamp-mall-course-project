<script setup lang="ts">
import { ref } from 'vue'
import { login, register } from '../../api'
const isRegister = ref(false)
const account = ref('')
const displayName = ref('')
const code = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')
async function submit() {
  error.value = ''; busy.value = true
  try { if (isRegister.value) await register(account.value, code.value, password.value, displayName.value); await login(account.value, password.value); uni.reLaunch({ url: '/pages/home/index' }) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : '操作失败' }
  finally { busy.value = false }
}
</script>
<template>
  <view class="screen"><view class="halo"></view><view class="brand">◉ <text>灯具商城</text></view>
    <view class="hero"><text class="kicker">A BETTER LIGHT</text><text class="title">为生活，找一盏好灯。</text><text class="sub">从一张图片开始，发现喜欢的灯具。</text></view>
    <view class="card"><view class="tabs"><text :class="{active:!isRegister}" @click="isRegister=false">登录</text><text :class="{active:isRegister}" @click="isRegister=true">注册</text></view>
      <input v-model="account" :placeholder="isRegister?'手机号':'手机号或账号'" /><input v-if="isRegister" v-model="displayName" placeholder="称呼" /><input v-if="isRegister" v-model="code" placeholder="本地验证码见项目说明" /><input v-model="password" password placeholder="密码（至少 8 位）" />
      <text v-if="error" class="error">{{ error }}</text><button :disabled="busy" @click="submit">{{ busy?'请稍候…':isRegister?'注册并进入':'进入商城' }}</button></view>
    <text class="foot">LUMIÈRE · 让空间因光而生动</text></view>
</template>
<style scoped>
.screen{min-height:100vh;padding:48rpx 42rpx;background:#f7f5f0;position:relative;overflow:hidden}.halo{position:absolute;width:650rpx;height:650rpx;border-radius:50%;background:#f1dec0;filter:blur(80rpx);top:-210rpx;right:-280rpx;opacity:.8}.brand{position:relative;color:#284a49;font-size:39rpx;font-weight:700;letter-spacing:4rpx}.brand text{font-size:27rpx;letter-spacing:2rpx;margin-left:16rpx}.hero{position:relative;display:flex;flex-direction:column;margin:100rpx 0 70rpx}.kicker{font-size:20rpx;letter-spacing:6rpx;color:#b48b5e;font-weight:700}.title{font-size:56rpx;line-height:1.45;color:#253d3d;font-weight:600;margin-top:24rpx}.sub{color:#86908b;font-size:26rpx;margin-top:20rpx}.card{position:relative;background:#fff;border-radius:28rpx;padding:46rpx;box-shadow:0 25rpx 70rpx #304b4314}.tabs{display:flex;gap:45rpx;margin-bottom:38rpx;color:#a9afa9;font-size:31rpx}.tabs .active{color:#2a5450;font-weight:700;border-bottom:5rpx solid #c6955c;padding-bottom:15rpx}input{height:95rpx;border-bottom:1rpx solid #e4e9e5;font-size:27rpx;margin-bottom:20rpx}button{background:#2a5450;color:#fff;border-radius:14rpx;margin-top:36rpx;font-size:29rpx}.error{display:block;color:#b9453d;font-size:23rpx;margin-top:18rpx}.foot{display:block;position:relative;text-align:center;color:#a8aaa2;font-size:20rpx;margin-top:80rpx;letter-spacing:2rpx}
</style>
