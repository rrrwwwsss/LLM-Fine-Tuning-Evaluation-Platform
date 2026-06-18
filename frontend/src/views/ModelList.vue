<template>
  <div>
    <div style="margin-bottom: 20px; display: flex; gap: 12px;">
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon> 启动模型服务
      </el-button>
      <el-button @click="loadServices">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <el-table :data="services" stripe style="width: 100%" v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="服务名称" min-width="140" />
      <el-table-column prop="model_name_or_path" label="基础模型" min-width="200" show-overflow-tooltip />
      <el-table-column label="模板" width="100">
        <template #default="{ row }">{{ row.template || "-" }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="端口" width="80">
        <template #default="{ row }">{{ row.port || "-" }}</template>
      </el-table-column>
      <el-table-column label="API 地址" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ row.api_url || "-" }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="160">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="handleChat(row)" :disabled="row.status !== 'running'">对话测试</el-button>
          <el-button size="small" @click="handleLogs(row)">日志</el-button>
          <el-button size="small" type="primary" @click="handleStart(row)"
            :disabled="row.status === 'running' || row.status === 'starting'">
            {{ row.status === "starting" ? "启动中" : "启动" }}
          </el-button>
          <el-popconfirm title="确定停止?" @confirm="handleStop(row)">
            <template #reference>
              <el-button size="small" type="warning" :disabled="row.status !== 'running'">停止</el-button>
            </template>
          </el-popconfirm>
          <el-popconfirm title="确定删除?" @confirm="handleDelete(row.id)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showCreate" title="启动模型推理服务" width="650px">
      <el-form :model="form" label-width="140px">
        <el-form-item label="服务名称" required>
          <el-tooltip content="给这个推理服务起个名字" placement="top">
            <el-input v-model="form.name" placeholder="如: qwen3.5-vl-api" />
          </el-tooltip>
        </el-form-item>
        <el-form-item label="基础模型路径" required>
          <el-tooltip content="预训练模型的本地路径或 HuggingFace 模型名" placement="top">
            <el-input v-model="form.model_name_or_path" placeholder="如: /path/to/Qwen3.5-VL-27B" />
          </el-tooltip>
        </el-form-item>
        <el-form-item label="微调权重路径">
          <el-tooltip content="LoRA 微调后的权重目录（可选）" placement="top">
            <el-input v-model="form.adapter_path" placeholder="如: ./saves/qwen_lora_exp1" />
          </el-tooltip>
        </el-form-item>
        <el-form-item label="模型模板" required>
          <el-tooltip content="对话模板，必须与模型匹配" placement="top">
            <el-select v-model="form.template" placeholder="选择模板" style="width: 100%;" filterable allow-create>
              <el-option label="qwen2.5" value="qwen2.5" /><el-option label="qwen2_vl" value="qwen2_vl" /><el-option label="qwen3" value="qwen3" /><el-option label="qwen3_5" value="qwen3_5" /><el-option label="qwen3_6" value="qwen3_6" /><el-option label="qwen3_vl" value="qwen3_vl" /><el-option label="llama3" value="llama3" />
            </el-select>
          </el-tooltip>
        </el-form-item>
        <el-form-item label="端口">
          <el-tooltip content="留空自动分配，手动指定请确保端口未被占用" placement="top">
            <el-input-number v-model="form.port" :min="18081" :max="18100" placeholder="自动分配" />
          </el-tooltip>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">创建并启动</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showLogs" title="模型服务日志" width="800px" top="3vh">
      <pre style="max-height: 500px; overflow-y: auto; background: #1e1e1e; color: #d4d4d4; padding: 12px; font-size: 12px; border-radius: 4px;">{{ logsText || "(无日志)" }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRouter } from "vue-router"
import { modelApi } from "../api"
import { ElMessage } from "element-plus"

const router = useRouter()
const services = ref<any[]>([])
const loading = ref(false)
const showCreate = ref(false)
const creating = ref(false)
const showLogs = ref(false)
const logsText = ref("")

const form = ref({ name: "", model_name_or_path: "", adapter_path: "", template: "qwen2.5", port: 0 as number })

onMounted(loadServices)

async function loadServices() {
  loading.value = true
  try { const res = await modelApi.list(); services.value = res.data.data || [] }
  catch { ElMessage.error("加载失败") }
  finally { loading.value = false }
}

async function handleCreate() {
  if (!form.value.name || !form.value.model_name_or_path || !form.value.template) {
    ElMessage.warning("请填写必填项"); return
  }
  creating.value = true
  try {
    const res = await modelApi.create({ name: form.value.name, model_name_or_path: form.value.model_name_or_path, adapter_path: form.value.adapter_path, template: form.value.template, port: form.value.port || 0 })
    const sid = res.data.data?.id
    if (sid) await modelApi.start(sid)
    ElMessage.success("创建成功，服务正在启动")
    showCreate.value = false
    form.value = { name: "", model_name_or_path: "", adapter_path: "", template: "qwen2.5", port: 0 }
    await loadServices()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || "创建失败") }
  finally { creating.value = false }
}

async function handleStart(row: any) {
  try { await modelApi.start(row.id); ElMessage.success("正在启动"); await loadServices() }
  catch { ElMessage.error("启动失败") }
}
async function handleStop(row: any) {
  try { await modelApi.stop(row.id); ElMessage.success("已停止"); await loadServices() }
  catch { ElMessage.error("停止失败") }
}
async function handleDelete(id: number) {
  try { await modelApi.delete(id); ElMessage.success("已删除"); await loadServices() }
  catch { ElMessage.error("删除失败") }
}
function handleChat(row: any) { router.push("/model/chat/" + row.id) }

async function handleLogs(row: any) {
  try { const res = await modelApi.getLogs(row.id); logsText.value = res.data.data || "(无日志)"; showLogs.value = true }
  catch { ElMessage.error("获取日志失败") }
}

function statusType(s: string) {
  return ({ created: "info", starting: "warning", running: "success", stopped: "info", failed: "danger" })[s] || "info"
}
function statusLabel(s: string) {
  return ({ created: "已创建", starting: "启动中", running: "运行中", stopped: "已停止", failed: "失败" })[s] || s
}
function formatTime(t: string) { if (!t) return ""; return new Date(t).toLocaleString("zh-CN") }
</script>
