<template>
  <el-container style="height: 100vh;">
    <el-aside width="220px" style="background: #1a1a2e; color: #fff;">
      <div style="padding: 20px; font-size: 18px; font-weight: bold; border-bottom: 1px solid #333;">
        🧠 微调评测平台
      </div>
      <el-menu
        :default-active="route.path"
        router
        background-color="#1a1a2e"
        text-color="#ccc"
        active-text-color="#409eff"
        style="border-right: none;"
      >
                <el-menu-item index="/dataset">
          <el-icon><FolderOpened /></el-icon>
          <span>数据集管理</span>
        </el-menu-item><el-menu-item index="/finetune">
          <el-icon><TrendCharts /></el-icon>
          <span>微调任务</span>
        </el-menu-item>
        <el-menu-item index="/model">
          <el-icon><Cpu /></el-icon>
          <span>模型服务</span>
        </el-menu-item>
        <el-menu-item index="/eval">
          <el-icon><DataAnalysis /></el-icon>
          <span>评测任务</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header style="background: #fff; border-bottom: 1px solid #eee; display: flex; align-items: center; padding: 0 20px;">
        <h2 style="margin: 0; font-size: 18px;">{{ pageTitle }}</h2>
        <div style="flex: 1;"></div>
        <el-tag type="success" size="small" v-if="backendStatus === 'ok'">后端在线</el-tag>
        <el-tag type="danger" size="small" v-else>后端离线</el-tag>
      </el-header>

      <el-main style="background: #f5f7fa;">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const backendStatus = ref('checking')

const pageTitle = computed(() => {
  const map: Record<string, string> = {
        '/dataset': '数据集管理',
    '/dataset/create': '数据集制作',
    '/finetune': '微调任务管理',
    '/eval': '评测任务管理',
    '/model': '模型服务管理',
    '/model/chat': '模型对话测试'
  }
  return map[route.path] || 'LLM 微调与自动评测平台'
})

onMounted(async () => {
  try {
    const res = await axios.get('/api/health')
    backendStatus.value = res.data.status
  } catch {
    backendStatus.value = 'offline'
  }
})
</script>
