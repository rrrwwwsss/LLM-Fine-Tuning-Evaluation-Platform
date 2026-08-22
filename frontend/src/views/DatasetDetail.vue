<template>
  <div v-loading="loading">
    <el-button @click="$router.push('/dataset')" style="margin-bottom: 12px;">
      <el-icon><ArrowLeft /></el-icon> 返回数据集列表
    </el-button>

    <el-card v-if="ds" shadow="never">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div>
            <strong>{{ ds.name }}</strong> (ID: {{ ds.id }})
            <el-tag :type="statusType(ds.status)" size="small" style="margin-left: 8px;">
              {{ statusLabel(ds.status) }}
            </el-tag>
            <el-tag :type="trainingStage === 'dpo' ? 'warning' : 'primary'" size="small" style="margin-left: 8px;">
              {{ trainingStage.toUpperCase() }}
            </el-tag>
            <span style="color: #666; font-size: 13px; margin-left: 12px;">共 {{ ds.total_rows }} 条</span>
            <span v-if="ds.train_rows" style="color: #666; font-size: 13px; margin-left: 8px;">
              训练 {{ ds.train_rows }} / 测试 {{ ds.test_rows }}
            </span>
          </div>
          <div>
            <el-button size="small" type="warning" @click="showSplit = true" v-if="ds.status !== 'uploaded'">
              重新划分 ({{ Math.round(ds.train_ratio * 100) }}%)
            </el-button>
          </div>
        </div>
      </template>

      <el-alert
        v-if="ds.status === 'uploaded'"
        title="该数据集尚未划分，请先在数据集列表页进行划分操作"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      />

      <el-tabs v-model="activeSplit" @tab-change="loadData">
        <el-tab-pane label="训练集" name="train" />
        <el-tab-pane label="测试集" name="test" />
      </el-tabs>

      <el-table
        :data="rows"
        stripe
        size="small"
        max-height="580"
        border
        highlight-current-row
        @row-click="onRowClick"
        style="cursor: pointer;"
      >
                <el-table-column type="index" label="#" width="50" />
        <el-table-column
          v-for="col in columns"
          :key="col"
          :prop="col"
          :label="col"
          min-width="130"
        >
          <template #default="{ row }">
            <span style="font-size: 12px;">{{ row[col] }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 16px; display: flex; justify-content: center;">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next, total, sizes"
          :page-sizes="[20, 50, 100]"
          @current-change="loadData"
          @size-change="loadData"
        />
      </div>
    </el-card>

    <!-- 划分对话框 -->
    <el-dialog v-model="showSplit" title="重新划分训练/测试集" width="400px">
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

    <!-- 行详情对话框 -->
    <el-dialog v-model="showDetail" title="数据详情" width="920px" top="2vh">
      <template v-if="detailRow">
        <div v-if="imageCol && detailRow[imageCol]" style="text-align: center; margin-bottom: 16px;">
          <el-image
            v-if="isImagePath(detailRow[imageCol])"
            :src="getFileUrl(detailRow[imageCol])"
            style="max-width: 100%; max-height: 360px; border-radius: 6px;"
            fit="contain"
            :preview-src-list="[getFileUrl(detailRow[imageCol])]"
          />
          <div style="font-size: 12px; color: #999; margin-top: 6px;">
            路径: {{ detailRow[imageCol] }}
            <el-button size="small" text @click="copyText(detailRow[imageCol])">复制</el-button>
          </div>
        </div>

        <el-form label-position="top">
          <el-form-item v-for="field in editableCols" :key="field" :label="fieldLabel(field)">
            <el-input-number v-if="columnType(field) === 'number'" v-model="editValues[field]" style="width: 100%;" />
            <div v-else-if="columnType(field) === 'image'" style="width: 100%; display: flex; gap: 8px;">
              <el-input v-model="editValues[field]" placeholder="图片相对路径或绝对路径" />
              <el-upload :show-file-list="false" :http-request="imageUploadHandler(field)">
                <el-button>上传图片</el-button>
              </el-upload>
              <ServerPathPicker v-model="editValues[field]" mode="image" button-text="Linux 图片" title="选择服务器图片" />
            </div>
            <el-input
              v-else
              v-model="editValues[field]"
              :type="['long_text', 'json'].includes(columnType(field)) ? 'textarea' : 'text'"
              :rows="['long_text', 'json'].includes(columnType(field)) ? 5 : undefined"
              style="font-size: 13px;"
            />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="showDetail = false">取消</el-button>
        <el-button type="primary" @click="saveEdit" :loading="saving">保存修改</el-button>
        <el-popconfirm title="确定删除该条数据?" @confirm="deleteRow">
          <template #reference>
            <el-button type="danger" :loading="deleting">删除该条</el-button>
          </template>
        </el-popconfirm>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue"
import { useRoute, useRouter } from "vue-router"
import { datasetApi } from "../api"
import { ElMessage } from "element-plus"
import ServerPathPicker from "../components/ServerPathPicker.vue"

const route = useRoute()
const router = useRouter()
const dsId = Number(route.params.id)

const loading = ref(true)
const ds = ref<any>(null)
const activeSplit = ref("train")
const rows = ref<any[]>([])
const columns = ref<string[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)

const showSplit = ref(false)
const splitting = ref(false)
const splitRatio = ref(0.8)

const showDetail = ref(false)
const detailRow = ref<any>(null)
const detailIndex = ref(-1)
const saving = ref(false)
const deleting = ref(false)
const schemaColumns = ref<any[]>([])
const trainingStage = ref('sft')
const editValues = ref<Record<string, any>>({})

const imageCol = computed(() => schemaColumns.value.find(c => c.role === 'image')?.name || findCol("image"))
const editableCols = computed(() => columns.value.filter(c => c !== "_row_id"))

function findCol(type: string): string {
  for (const c of columns.value) {
    const cl = c.toLowerCase().replace(/ /g, "_")
    if (type === "image" && /image|img|picture|pic|photo/.test(cl)) return c
    if (type === "prompt" && /prompt|question|instruction|query/.test(cl)) return c
    if (type === "answer" && /answer|result|output|response|label|model_result/.test(cl)) return c
  }
  return ""
}

function getFileUrl(path: string): string {
  let normalized = String(path).replace(/\\/g, '/')
  if (!normalized.startsWith('/') && !/^[A-Za-z]:\//.test(normalized)) {
    return `/api/v1/dataset/${dsId}/asset?path=${encodeURIComponent(normalized)}`
  }
  return '/api/file?path=' + encodeURIComponent(normalized)
}

function isImagePath(val: any): boolean {
  return val && String(val).match(/\.(jpg|jpeg|png|gif|bmp|webp|svg)$/i)
}

onMounted(async () => {
  await loadDataset()
  await loadSchema()
  if (ds.value && ds.value.status !== "uploaded") {
    await loadData()
  }
  loading.value = false
})

async function loadSchema() {
  try {
    const res = await datasetApi.getSchema(dsId)
    schemaColumns.value = res.data.data.columns || []
    trainingStage.value = res.data.data.training_stage || 'sft'
  } catch { schemaColumns.value = [] }
}

async function loadDataset() {
  try {
    const res = await datasetApi.get(dsId)
    ds.value = res.data.data
    if (!ds.value) {
      ElMessage.error("数据集不存在")
      router.push("/dataset")
    }
  } catch {
    ElMessage.error("加载数据集失败")
    router.push("/dataset")
  }
}

async function loadData() {
  try {
    const res = await datasetApi.previewSplit(dsId, activeSplit.value, page.value, pageSize.value)
    const d = res.data.data
    rows.value = d.rows || []
    columns.value = d.columns || []
    total.value = d.total || 0
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "加载数据失败")
  }
}

function onRowClick(row: any) {
  detailRow.value = row
  detailIndex.value = rows.value.indexOf(row)
  editValues.value = Object.fromEntries(editableCols.value.map(field => [field, row[field] ?? ""]))
  showDetail.value = true
}

async function saveEdit() {
  saving.value = true
  try {
    const rowIdx = detailRow.value?._row_index ?? (detailIndex.value + (page.value - 1) * pageSize.value)
    await datasetApi.updateRow(dsId, activeSplit.value, rowIdx, editValues.value)
    ElMessage.success("已保存")
    showDetail.value = false
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "保存失败")
  } finally { saving.value = false }
}

function columnType(field: string): string {
  return schemaColumns.value.find(c => c.name === field)?.type || (field === imageCol.value ? 'image' : 'text')
}

function fieldLabel(field: string): string {
  const definition = schemaColumns.value.find(c => c.name === field)
  const role = definition?.role && definition.role !== 'other' ? ` · ${definition.role}` : ''
  return field + role
}

async function uploadImage(field: string, options: any) {
  try {
    const res = await datasetApi.uploadImage(dsId, options.file)
    editValues.value[field] = res.data.data.path
    ElMessage.success('图片已上传')
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '图片上传失败') }
}

function imageUploadHandler(field: string) {
  return (options: any) => uploadImage(field, options)
}

async function deleteRow() {
  if (!detailRow.value) return
  deleting.value = true
  try {
    const rowIdx = detailRow.value?._row_index ?? (detailIndex.value + (page.value - 1) * pageSize.value)
    await datasetApi.deleteRow(dsId, activeSplit.value, rowIdx)
    ElMessage.success("删除成功")
    showDetail.value = false
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "删除失败")
  } finally { deleting.value = false }
}

async function confirmSplit() {
  splitting.value = true
  try {
    await datasetApi.split(dsId, splitRatio.value)
    ElMessage.success("划分完成")
    showSplit.value = false
    await loadDataset()
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "划分失败")
  } finally { splitting.value = false }
}

function copyText(text: string) {
  navigator.clipboard.writeText(text).then(() => ElMessage.success("已复制"))
}

function statusType(s: string) {
  return ({ uploaded: "info", split: "warning", converted: "success" })[s] || "info"
}
function statusLabel(s: string) {
  return ({ uploaded: "未划分", split: "已划分", converted: "已转换" })[s] || s
}
</script>
