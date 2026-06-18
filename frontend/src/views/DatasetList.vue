<template>
  <div>
    <div style="margin-bottom: 20px; display: flex; gap: 12px;">
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
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
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
          <el-input v-model="uploadPrefix" placeholder="如: /HTC/rws/model_tun/data/pic_pack" />
          <div style="font-size: 12px; color: #999; margin-top: 4px;">
            CSV 中图片路径为相对路径时，输入前缀自动拼接；留空表示已是完整路径
          </div>
        </el-form-item>

        <el-form-item label="CSV 文件" required>
          <el-upload ref="uploadRef" :auto-upload="false" :show-file-list="true" :limit="1" accept=".csv" @change="onFileChange">
            <el-button type="primary">选择文件</el-button>
            <template #tip>
              <div style="font-size: 12px; color: #999; margin-top: 4px;">
                CSV 需包含 prompt_text / model_result / image_path 等列
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUpload = false">取消</el-button>
        <el-button type="primary" @click="handleUpload" :loading="uploading">上传并导入</el-button>
      </template>
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

const router = useRouter()
const datasets = ref<any[]>([])
const loading = ref(false)

const showUpload = ref(false)
const uploading = ref(false)
const uploadForm = ref({ name: "" })
const uploadPrefix = ref("")
const uploadFile = ref<File | null>(null)

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

function onFileChange(file: any) { uploadFile.value = file.raw }

async function handleUpload() {
  if (!uploadForm.value.name || !uploadFile.value) {
    ElMessage.warning("请填写名称并选择文件")
    return
  }
  uploading.value = true
  try {
    await datasetApi.upload(uploadForm.value.name, uploadFile.value, uploadPrefix.value)
    ElMessage.success("上传成功")
    showUpload.value = false
    uploadForm.value = { name: "" }
      uploadPrefix.value = ""
    uploadFile.value = null
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
  const m: Record<string, string> = { uploaded: "已上传", split: "已划分", converted: "已转换" }
  return m[s] || s
}
function formatTime(t: string) {
  if (!t) return ""
  return new Date(t).toLocaleString("zh-CN")
}
</script>
