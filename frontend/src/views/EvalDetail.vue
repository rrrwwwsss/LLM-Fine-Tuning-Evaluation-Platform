<template>
  <div v-loading="loading">
    <el-button @click="$router.push('/eval')" style="margin-bottom: 16px;">
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

      <!-- 进度 -->
      <el-progress
        :percentage="Math.round(task.progress * 100)"
        :status="task.status === 'completed' ? 'success' : ''"
        :stroke-width="24"
        :text-inside="true"
        style="margin-bottom: 20px;"
      />
      <p style="font-size: 13px; color: #666; text-align: center;">
        已处理 {{ task.processed_samples }} / {{ task.total_samples }} 条样本
      </p>

      <!-- 指标卡片 -->
      <el-row :gutter="16" style="margin-bottom: 20px;" v-if="metrics">
        <el-col :span="6">
          <el-card shadow="hover" style="text-align: center;">
            <div style="font-size: 28px; color: #409eff; font-weight: bold;">{{ (metrics.accuracy * 100).toFixed(2) }}%</div>
            <div style="font-size: 13px; color: #999;">Accuracy</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" style="text-align: center;">
            <div style="font-size: 28px; color: #67c23a; font-weight: bold;">{{ (metrics.precision * 100).toFixed(2) }}%</div>
            <div style="font-size: 13px; color: #999;">Precision</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" style="text-align: center;">
            <div style="font-size: 28px; color: #e6a23c; font-weight: bold;">{{ (metrics.recall * 100).toFixed(2) }}%</div>
            <div style="font-size: 13px; color: #999;">Recall</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" style="text-align: center;">
            <div style="font-size: 28px; color: #f56c6c; font-weight: bold;">{{ (metrics.f1_score * 100).toFixed(2) }}%</div>
            <div style="font-size: 13px; color: #999;">F1 Score</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 混淆矩阵 -->
      <el-row :gutter="16" style="margin-bottom: 20px;" v-if="metrics && cmData.length">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header><span>混淆矩阵</span></template>
            <div ref="cmChartRef" style="height: 300px;"></div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never" v-if="crData">
            <template #header><span>分类报告</span></template>
            <el-table :data="crData" size="small" stripe>
              <el-table-column prop="class" label="类别" />
              <el-table-column prop="precision" label="Precision" width="100">
                <template #default="{ row }">{{ (row.precision * 100).toFixed(2) }}%</template>
              </el-table-column>
              <el-table-column prop="recall" label="Recall" width="100">
                <template #default="{ row }">{{ (row.recall * 100).toFixed(2) }}%</template>
              </el-table-column>
              <el-table-column prop="f1_score" label="F1" width="100">
                <template #default="{ row }">{{ (row.f1_score * 100).toFixed(2) }}%</template>
              </el-table-column>
              <el-table-column prop="support" label="Support" width="80" />
            </el-table>
          </el-card>
        </el-col>
      </el-row>

      <!-- 详细结果表格 -->
      <el-card shadow="never">
        <template #header>
          <span>逐条评测结果 (共 {{ total }} 条)</span>
        </template>
        <el-table :data="results" stripe size="small" max-height="500" style="width: 100%; cursor: pointer;" @row-click="showDetail">
          <el-table-column prop="sample_index" label="#" width="60" />
          <el-table-column prop="true_label" label="真实标签" width="120" />
          <el-table-column prop="predicted_label" label="预测标签" width="120">
            <template #default="{ row }">
              <el-tag :type="row.true_label === row.predicted_label ? 'success' : 'danger'" size="small">
                {{ row.predicted_label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="model_output" label="模型输出" min-width="200">
            <template #default="{ row }">
              <span style="color: #409eff;">{{ (row.model_output || "").substring(0, 60) }}{{ (row.model_output || "").length > 60 ? "..." : "" }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="prompt_text" label="Prompt" min-width="200">
            <template #default="{ row }">
              <span>{{ (row.prompt_text || "").substring(0, 60) }}{{ (row.prompt_text || "").length > 60 ? "..." : "" }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="image_path" label="图片" min-width="120" v-if="hasImage">
            <template #default="{ row }">
              <el-image
                v-if="row.image_path && isImagePath(row.image_path)"
                :src="'/api/file?path=' + encodeURIComponent(String(row.image_path).replace(/\\/g, '/'))"
                style="width: 48px; height: 48px; border-radius: 4px;"
                fit="cover"
                @click.stop="showDetail(row)"
              />
              <span v-else style="font-size: 12px; color: #999;">{{ String(row.image_path || "").substring(0, 30) }}</span>
            </template>
          </el-table-column>
        </el-table>
        <div style="margin-top: 16px; text-align: center;">
          <el-pagination
            v-model:current-page="page"
            :page-size="pageSize"
            :total="total"
            layout="prev, pager, next, total"
            @current-change="loadResults"
          />
        </div>
      </el-card>
    </el-card>
  </div>

  <!-- ???? -->
  <  <el-dialog v-model="detailVisible" title="评测详情" width="1000px" top="3vh" destroy-on-close>
    <div v-if="detailRow" style="max-height: 75vh; overflow-y: auto;">
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="样本序号">{{ detailRow.sample_index }}</el-descriptions-item>
        <el-descriptions-item label="真实标签">
          <el-tag :type="detailRow.true_label === detailRow.predicted_label ? 'success' : 'danger'" size="small">{{ detailRow.true_label }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="预测标签">
          <el-tag :type="detailRow.true_label === detailRow.predicted_label ? 'success' : 'danger'" size="small">{{ detailRow.predicted_label }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="提示词">
          <div style="white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto; font-size: 13px;">{{ detailRow.prompt_text }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="图片路径">
          <span style="word-break: break-all; font-size: 12px;">{{ detailRow.image_path || '无' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="图片" v-if="detailRow.image_path && isImagePath(detailRow.image_path)">
          <el-image
            :src="'/api/file?path=' + encodeURIComponent(String(detailRow.image_path).replace(/\\/g, '/'))"
            style="max-width: 100%; max-height: 400px; border-radius: 4px;"
            fit="contain"
            :preview-src-list="['/api/file?path=' + encodeURIComponent(String(detailRow.image_path).replace(/\\/g, '/'))]"
            preview-teleported
          />
        </el-descriptions-item>
        <el-descriptions-item v-else-if="detailRow.image_path" label="图片">
          <span style="color: #999;">非图片格式或无法加载</span>
        </el-descriptions-item>
        <el-descriptions-item label="模型输出">
          <div style="white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto; font-size: 13px; background: #f5f7fa; padding: 12px; border-radius: 4px;">{{ detailRow.model_output }}</div>
        </el-descriptions-item>
      </el-descriptions>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { evalApi } from '../api'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

const route = useRoute()
const taskId = Number(route.params.id)
const task = ref<any>(null)
const loading = ref(true)
const metrics = ref<any>(null)
const results = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const hasImage = ref(false)
const cmData = ref<string[]>([])
const crData = ref<any[]>([])
const cmChartRef = ref<HTMLElement | null>(null)
const detailVisible = ref(false)
const detailRow = ref<any>(null)

function isImagePath(path: string): boolean {
  const ext = path.split('.').pop()?.toLowerCase() || ''
  return ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'tiff', 'tif'].includes(ext)
}

function showDetail(row: any) {
  detailRow.value = row
  detailVisible.value = true
}

let ws: WebSocket | null = null
let pollTimer: any = null

onMounted(async () => {
  await loadTask()
  connectWs()
  startPolling()
})

onUnmounted(() => { ws?.close(); clearInterval(pollTimer) })

async function loadTask() {
  try {
    const res = await evalApi.get(taskId)
    task.value = res.data.data
    await loadMetrics()
    await loadResults()
  } catch { ElMessage.error('加载失败') }
  finally { loading.value = false }
}

async function loadMetrics() {
  try {
    const res = await evalApi.getMetrics(taskId)
    const m = res.data.data
    if (m) {
      metrics.value = m
      // 解析混淆矩阵
      try { const cm = JSON.parse(m.confusion_matrix); drawCM(cm) } catch { /* ignore */ }
      // 解析分类报告
      try {
        const cr = JSON.parse(m.classification_report)
        const rows: any[] = []
        for (const [key, val] of Object.entries(cr)) {
          if (key !== 'accuracy' && key !== 'macro avg' && key !== 'weighted avg' && typeof val === 'object') {
            rows.push({ class: key, ...(val as any) })
          }
        }
        crData.value = rows
      } catch { /* ignore */ }
    }
  } catch { /* ignore */ }
}

async function loadResults() {
  try {
    const res = await evalApi.getResults(taskId, page.value, pageSize)
    results.value = res.data.data?.items || []
    total.value = res.data.data?.total || 0
    hasImage.value = results.value.some((r: any) => r.image_path)
  } catch { /* ignore */ }
}

function drawCM(matrix: number[][]) {
  if (!cmChartRef.value || !matrix.length) return
  nextTick(() => {
    const chart = echarts.init(cmChartRef.value)
    const labels = matrix.map((_, i) => `类别${i}`)
    const data: any[] = []
    matrix.forEach((row, i) => {
      row.forEach((val, j) => {
        data.push([j, i, val])
      })
    })
    chart.setOption({
      grid: { left: 60, right: 60, bottom: 40, top: 10 },
      xAxis: { type: 'category', data: labels, splitArea: { show: true } },
      yAxis: { type: 'category', data: labels, splitArea: { show: true } },
      visualMap: { min: 0, max: Math.max(...matrix.flat()), calculable: true, orient: 'horizontal', left: 'center', bottom: 0 },
      series: [{
        type: 'heatmap', data,
        label: { show: true, color: '#333' },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' } }
      }]
    })
  })
}

function connectWs() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  ws = new WebSocket(`${protocol}//${location.host}/api/v1/ws/eval/${taskId}`)
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data)
    if (data.type === 'state' || data.type === 'progress') {
      task.value = { ...task.value, ...data }
      loadResults()
      loadMetrics()
    }
  }
}

function startPolling() {
  pollTimer = setInterval(() => { loadTask() }, 3000)
}

async function handleStop() {
  try { await evalApi.stop(taskId); ElMessage.success('已停止'); await loadTask() }
  catch { ElMessage.error('停止失败') }
}

function statusType(s: string) { const map: Record<string, string> = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger', stopped: 'info' }; return map[s] || 'info' }
function statusLabel(s: string) { const map: Record<string, string> = { pending: '待启动', running: '运行中', completed: '已完成', failed: '失败', stopped: '已停止' }; return map[s] || s }
</script>
