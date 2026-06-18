<template>
  <div v-loading="loading">
    <el-button @click="$router.push('/finetune')" style="margin-bottom: 16px;">
      <el-icon><ArrowLeft /></el-icon> 返回列表
    </el-button>

    <el-card v-if="task" shadow="never">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span><strong>{{ task.name }}</strong> (ID: {{ task.id }})</span>
          <div>
            <el-tag :type="statusType(task.status)" size="small">{{ statusLabel(task.status) }}</el-tag>
            <el-button size="small" type="warning" @click="handleStop" v-if="task.status === 'running'" style="margin-left: 8px;">
              <el-icon><VideoPause /></el-icon> 停止
            </el-button>
          </div>
        </div>
      </template>

      <!-- 进度信息 -->
      <el-row :gutter="16" style="margin-bottom: 16px;">
        <el-col :span="12">
          <el-progress
            :percentage="Math.round(task.progress * 100)"
            :status="task.status === 'completed' ? 'success' : ''"
            :stroke-width="20"
            :text-inside="true"
          />
        </el-col>
        <el-col :span="12">
          <span style="font-size: 13px; color: #666;">
            Epoch: {{ task.current_epoch }} / {{ task.total_epochs || '?' }}
            | Step: {{ task.current_step }} / {{ task.total_steps || '?' }}
            | Loss: {{ task.current_loss?.toFixed(4) || '--' }}
          </span>
        </el-col>
      </el-row>

      <!-- Loss 曲线 -->
      <el-card shadow="never" style="margin-bottom: 16px;">
        <template #header><span>Loss 曲线</span></template>
        <div ref="lossChartRef" style="height: 300px;"></div>
      </el-card>

      <!-- 实时日志 -->
      <el-card shadow="never">
        <template #header>
          <div style="display: flex; justify-content: space-between;">
            <span>实时日志</span>
            <el-button size="small" @click="autoScroll = !autoScroll">
              {{ autoScroll ? '自动滚动: 开' : '自动滚动: 关' }}
            </el-button>
          </div>
        </template>
        <div ref="logRef" style="height: 400px; overflow-y: auto; background: #1e1e1e; color: #d4d4d4; padding: 12px; font-family: 'Courier New', monospace; font-size: 12px; white-space: pre-wrap; border-radius: 4px;">
          {{ logs || '(等待日志输出...)' }}
        </div>
      </el-card>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { finetuneApi } from '../api'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

const route = useRoute()
const taskId = Number(route.params.id)
const task = ref<any>(null)
const loading = ref(true)
const logs = ref('')
const autoScroll = ref(true)
const logRef = ref<HTMLElement | null>(null)
const lossChartRef = ref<HTMLElement | null>(null)

let ws: WebSocket | null = null
let chart: echarts.ECharts | null = null
let pollTimer: any = null

onMounted(async () => {
  await loadTask()
  await loadLogs()
  connectWs()
  startPolling()
})

onUnmounted(() => {
  ws?.close()
  chart?.dispose()
  clearInterval(pollTimer)
})

async function loadTask() {
  try {
    const res = await finetuneApi.get(taskId)
    task.value = res.data.data
    nextTick(() => initChart())
  } catch { ElMessage.error('加载任务失败') }
  finally { loading.value = false }
}

async function loadLogs() {
  try {
    const res = await finetuneApi.getLogs(taskId)
    logs.value = res.data.data || '(无日志)'
    scrollLog()
  } catch { /* ignore */ }
}

function connectWs() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws = new WebSocket(`${protocol}//${location.host}/api/v1/ws/finetune/${taskId}`)
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data)
    if (data.type === 'state' || data.type === 'progress') {
      task.value = { ...task.value, ...data }
      updateChart()
      loadLogs()
    }
  }
}

function startPolling() {
  pollTimer = setInterval(async () => {
    await loadTask()
    await loadLogs()
  }, 3000)
}

function initChart() {
  if (!lossChartRef.value) return
  chart = echarts.init(lossChartRef.value)
  chart.setOption({
    grid: { left: 50, right: 20, bottom: 30, top: 10 },
    xAxis: { type: 'value', name: 'Step' },
    yAxis: { type: 'value', name: 'Loss' },
    series: [{ type: 'line', data: [], smooth: true, lineStyle: { color: '#409eff' }, areaStyle: { color: 'rgba(64,158,255,0.1)' } }],
    tooltip: { trigger: 'axis' },
  })
  updateChart()
}

function updateChart() {
  if (!chart || !task.value?.loss_history) return
  try {
    const history = JSON.parse(task.value.loss_history)
    const data = history.map((h: any) => [h.step || h.step === 0 ? h.step : h.loss, h.loss])
    chart.setOption({ series: [{ data }] })
  } catch { /* ignore */ }
}

async function handleStop() {
  try {
    await finetuneApi.stop(taskId)
    ElMessage.success('已停止')
    await loadTask()
  } catch { ElMessage.error('停止失败') }
}

function scrollLog() {
  nextTick(() => {
    if (autoScroll.value && logRef.value) {
      logRef.value.scrollTop = logRef.value.scrollHeight
    }
  })
}

function statusType(s: string) { const map: Record<string, string> = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger', stopped: 'info' }; return map[s] || 'info' }
function statusLabel(s: string) { const map: Record<string, string> = { pending: '待启动', running: '运行中', completed: '已完成', failed: '失败', stopped: '已停止' }; return map[s] || s }

watch(logs, scrollLog)
</script>
