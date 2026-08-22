<template>
  <div>
    <div style="margin-bottom: 20px; display: flex; gap: 12px;">
      <el-button type="success" @click="$router.push('/dataset/create')">
        <el-icon><Plus /></el-icon> 制作数据集
      </el-button>
      <el-button type="primary" @click="showUpload = true">
        <el-icon><Upload /></el-icon> 上传数据集
      </el-button>
      <el-button @click="loadDatasets">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <el-table :data="datasets" stripe style="width: 100%" v-loading="loading">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="数据集名称" min-width="180" />
      <el-table-column label="训练类型" width="100">
        <template #default="{ row }">
          <el-tag :type="row.training_stage === 'dpo' ? 'warning' : 'primary'" size="small">{{ (row.training_stage || 'sft').toUpperCase() }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="总行数" width="75">
        <template #default="{ row }">{{ row.total_rows }}</template>
      </el-table-column>
      <el-table-column label="划分" width="160">
        <template #default="{ row }">
          <span v-if="row.train_rows">训练 {{ row.train_rows }} / 测试 {{ row.test_rows }}</span>
          <span v-else style="color: #999;">未划分</span>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="360" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="success" plain @click="$router.push('/dataset/create?id=' + row.id)">编辑数据</el-button>
          <el-button size="small" @click="handlePreview(row)">预览</el-button>
          <el-button size="small" type="warning" @click="handleSplit(row)">
            {{ row.status === "uploaded" ? "划分" : "重新划分" }}
          </el-button>
          <el-popconfirm title="确定删除?" @confirm="handleDelete(row.id)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 上传对话框 -->
    <el-dialog v-model="showUpload" title="上传数据集" width="500px">
      <el-form label-width="100px">
        <el-form-item label="数据集名称" required>
          <el-input v-model="uploadForm.name" placeholder="如: 摆摊检测训练数据" />
        </el-form-item>
        <el-form-item label="图片前置路径">
          <div style="display: flex; align-items: center; width: 100%;">
            <el-input v-model="uploadPrefix" placeholder="如: /HTC/rws/model_tun/data/pic_pack" />
            <ServerPathPicker v-model="uploadPrefix" button-text="浏览 Linux 目录" title="选择图片前置目录" />
          </div>
          <div style="font-size: 12px; color: #999; margin-top: 4px;">
            CSV 中图片路径为相对路径时，输入前缀自动拼接；留空表示已是完整路径
          </div>
        </el-form-item>

        <el-form-item label="CSV 文件" required>
          <el-upload ref="uploadRef" :auto-upload="false" :show-file-list="true" :limit="1" accept=".csv" @change="onFileChange">
            <el-button type="primary">选择本地 CSV</el-button>
            <template #tip>
              <div style="font-size: 12px; color: #999; margin-top: 4px;">
                支持任意列；上传后可通过“编辑数据”设置 Prompt / Answer / Image 字段
              </div>
            </template>
          </el-upload>
          <el-button style="margin-top: 8px;" @click="openServerCsvBrowser">选择 Linux 服务器 CSV</el-button>
          <div v-if="serverCsvPath" style="font-size: 12px; color: #409eff; margin-top: 6px; word-break: break-all;">
            已选择服务器文件：{{ serverCsvPath }}
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUpload = false">取消</el-button>
        <el-button type="primary" @click="handleUpload" :loading="uploading">上传并导入</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showServerCsvBrowser" title="选择 Linux 服务器 CSV" width="720px">
      <el-alert title="只显示 SERVER_BROWSE_ROOTS 白名单目录及其中的 CSV 文件。" type="info" :closable="false" />
      <div style="display: flex; gap: 8px; margin-top: 12px;">
        <el-button :disabled="!serverCsvParent" @click="loadServerCsvDirectory(serverCsvParent)">上一级</el-button>
        <el-input :model-value="serverCsvCurrent || '请选择授权根目录'" readonly />
      </div>
      <el-table :data="serverCsvEntries" v-loading="serverCsvLoading" height="360" border style="margin-top: 12px;" @row-dblclick="openServerCsvEntry">
        <el-table-column label="名称" min-width="430">
          <template #default="{ row }">{{ row.kind === 'directory' ? '📁' : 'CSV' }} {{ row.name }}</template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ row.kind === 'directory' ? '目录' : 'CSV 文件' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button text type="primary" @click="openServerCsvEntry(row)">{{ row.kind === 'directory' ? '进入' : '选择' }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 划分对话框 -->
    <el-dialog v-model="showSplit" title="划分训练/测试集" width="400px">
      <el-form label-width="120px">
        <el-form-item label="训练集比例">
          <el-slider v-model="splitRatio" :min="0.5" :max="0.95" :step="0.05" show-input />
        </el-form-item>
        <p style="font-size: 13px; color: #666; text-align: center;">
          训练: {{ Math.round(splitRatio * 100) }}% | 测试: {{ Math.round((1 - splitRatio) * 100) }}%
        </p>
      </el-form>
      <template #footer>
        <el-button @click="showSplit = false">取消</el-button>
        <el-button type="primary" @click="confirmSplit" :loading="splitting">确认划分</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import { useRouter } from "vue-router"
import { datasetApi } from "../api"
import { ElMessage } from "element-plus"
import ServerPathPicker from "../components/ServerPathPicker.vue"

const router = useRouter()
const datasets = ref<any[]>([])
const loading = ref(false)

const showUpload = ref(false)
const uploading = ref(false)
const uploadForm = ref({ name: "" })
const uploadPrefix = ref("")
const uploadFile = ref<File | null>(null)
const serverCsvPath = ref("")
const showServerCsvBrowser = ref(false)
const serverCsvLoading = ref(false)
const serverCsvCurrent = ref("")
const serverCsvParent = ref("")
const serverCsvEntries = ref<any[]>([])

const showSplit = ref(false)
const splitting = ref(false)
const splitRatio = ref(0.8)
const splitTargetId = ref(0)

onMounted(loadDatasets)

async function loadDatasets() {
  loading.value = true
  try {
    const res = await datasetApi.list()
    datasets.value = res.data.data || []
  } catch { ElMessage.error("加载失败") }
  finally { loading.value = false }
}

function onFileChange(file: any) {
  uploadFile.value = file.raw
  serverCsvPath.value = ""
}

async function openServerCsvBrowser() {
  showServerCsvBrowser.value = true
  await loadServerCsvDirectory("")
}

async function loadServerCsvDirectory(path: string) {
  serverCsvLoading.value = true
  try {
    const res = await datasetApi.browseServerDirectories(path)
    const data = res.data.data
    serverCsvCurrent.value = data.current || ""
    serverCsvParent.value = data.parent || ""
    serverCsvEntries.value = data.entries || []
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "无法读取 Linux 服务器目录")
  } finally { serverCsvLoading.value = false }
}

function openServerCsvEntry(row: any) {
  if (row.kind === "directory") return loadServerCsvDirectory(row.path)
  serverCsvPath.value = row.path
  uploadFile.value = null
  showServerCsvBrowser.value = false
}

async function handleUpload() {
  if (!uploadForm.value.name || (!uploadFile.value && !serverCsvPath.value)) {
    ElMessage.warning("请填写名称并选择文件")
    return
  }
  uploading.value = true
  try {
    if (serverCsvPath.value) {
      await datasetApi.uploadServerCsv(uploadForm.value.name, serverCsvPath.value, uploadPrefix.value)
    } else {
      await datasetApi.upload(uploadForm.value.name, uploadFile.value!, uploadPrefix.value)
    }
    ElMessage.success(serverCsvPath.value ? "服务器 CSV 导入成功" : "上传成功")
    showUpload.value = false
    uploadForm.value = { name: "" }
      uploadPrefix.value = ""
    uploadFile.value = null
    serverCsvPath.value = ""
    await loadDatasets()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "上传失败")
  } finally { uploading.value = false }
}

function handlePreview(row: any) {
  if (row.status === "uploaded") {
    ElMessage.warning("请先划分数据集")
    return
  }
  router.push("/dataset/" + row.id)
}

function handleSplit(row: any) {
  splitTargetId.value = row.id
  splitRatio.value = row.train_ratio || 0.8
  showSplit.value = true
}

async function confirmSplit() {
  splitting.value = true
  try {
    await datasetApi.split(splitTargetId.value, splitRatio.value)
    ElMessage.success("划分完成")
    showSplit.value = false
    await loadDatasets()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "划分失败")
  } finally { splitting.value = false }
}

async function handleDelete(id: number) {
  try {
    await datasetApi.delete(id)
    ElMessage.success("已删除")
    await loadDatasets()
  } catch { ElMessage.error("删除失败") }
}

function statusType(s: string) {
  const m: Record<string, string> = { uploaded: "info", split: "warning", converted: "success" }
  return m[s] || "info"
}
function statusLabel(s: string) {
  const m: Record<string, string> = { uploaded: "待划分", split: "已划分", converted: "可训练" }
  return m[s] || s
}
function formatTime(t: string) {
  if (!t) return ""
  return new Date(t).toLocaleString("zh-CN")
}
</script>
