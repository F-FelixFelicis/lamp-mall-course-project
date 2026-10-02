<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { clearToken, currentUser, getToken, type User } from '../../api'
const user = ref<User | null>(null)
onShow(async () => { if (!getToken()) { uni.reLaunch({ url: '/pages/login/index' }); return }; try { user.value = await currentUser() } catch { clearToken(); uni.reLaunch({ url: '/pages/login/index' }) } })
function logout() { clearToken(); uni.reLaunch({ url: '/pages/login/index' }) }
</script>
<template><view class="screen"><view class="top"><text class="mark">◉ 灯具商城</text><text class="tag">CUSTOMER</text></view><view class="welcome"><text>你好，{{ user?.display_name || '朋友' }}</text><text class="small">今天也值得被好光照亮。</text></view><view class="card"><text class="label">账号状态</text><text class="value">{{ user?.status || '加载中' }}</text><text class="meta">{{ user?.phone_masked }}</text></view><view class="notice"><text>欢迎来到灯具商城。</text><text>精选灯具与图片搜索功能即将开放。</text></view><button @click="logout">退出登录</button></view></template>
<style scoped>.screen{min-height:100vh;padding:52rpx 42rpx;background:#f7f5f0}.top{display:flex;justify-content:space-between;align-items:center;color:#264b49}.mark{font-size:31rpx;font-weight:700}.tag{font-size:18rpx;letter-spacing:3rpx;color:#b38b5b}.welcome{display:flex;flex-direction:column;margin:115rpx 0 50rpx;font-size:50rpx;font-weight:600;color:#253d3d}.small{font-size:27rpx;font-weight:400;color:#7e8983;margin-top:24rpx}.card{background:#fff;padding:48rpx;border-radius:25rpx;display:flex;flex-direction:column;box-shadow:0 20rpx 55rpx #304b4310}.label{font-size:23rpx;color:#8e9992}.value{font-size:42rpx;color:#28594e;margin-top:20rpx}.meta{font-size:25rpx;color:#a2aca4;margin-top:18rpx}.notice{margin-top:45rpx;line-height:2;color:#7d8780;font-size:25rpx;display:flex;flex-direction:column}button{background:#e2ebe6;color:#2b514b;margin-top:60rpx;border-radius:14rpx;font-size:27rpx}</style>
