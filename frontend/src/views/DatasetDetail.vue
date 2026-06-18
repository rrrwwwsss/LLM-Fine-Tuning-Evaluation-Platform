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

        <el-form label-width="100px">
          <el-form-item :label="promptCol" v-if="promptCol">
            <el-input type="textarea" :rows="5" :model-value="detailRow[promptCol]" readonly style="font-size: 13px;" />
          </el-form-item>

          <el-form-item :label="answerCol || '模型输出'">
            <el-input
              v-model="editAnswer" style="font-size: 13px;"
              type="textarea"
              :rows="7"
              placeholder="修改模型输出内容..."
            />
          </el-form-item>

          <el-form-item label="其他字段" v-if="otherCols.length">
            <div style="width: 100%;">
              <div v-for="f in otherCols" :key="f" style="margin-bottom: 3px; font-size: 13px; word-break: break-all;">
                <strong>{{ f }}:</strong> {{ detailRow[f] }}
              </div>
            </div>
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="showDetail = false">取消</el-button>
        <el-button type="primary" @click="saveEdit" :loading="saving">保存修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue"
import { useRoute, useRouter } from "vue-router"
import { datasetApi } from "../api"
import { ElMessage } from "element-plus"

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
const editAnswer = ref("")
const saving = ref(false)

const imageCol = computed(() => findCol("image"))
const promptCol = computed(() => findCol("prompt"))
const answerCol = computed(() => findCol("answer"))
const otherCols = computed(() => columns.value.filter(c => c !== imageCol.value && c !== promptCol.value && c !== answerCol.value && c !== "_row_id"))

function findCol(type: string): string {
  for (const c of columns.value) {
    const cl = c.toLowerCase().replace(/ /g, "_")
    if (type === "image" && /image|img|picture|pic|photo/.test(cl)) return c
    if (type === "prompt" && /prompt|question|instruction|query/.test(cl)) return c
    if (type === "answer" && /answer|result|output|response|label|model_result/.test(cl)) return c
  }
  return ""
}

function isImageCol(col: string): boolean {
  return col === imageCol.value
}

function getFileUrl(path: string): string {
  return '/api/file?path=' + encodeURIComponent(String(path).split('\\').join('/'))
}

function isImagePath(val: any): boolean {
  return val && String(val).match(/\.(jpg|jpeg|png|gif|bmp|webp|svg)$/i)
}

onMounted(async () => {
  await loadDataset()
  if (ds.value && ds.value.status !== "uploaded") {
    await loadData()
  }
  loading.value = false
})

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
  editAnswer.value = answerCol.value && row[answerCol.value] ? String(row[answerCol.value]) : ""
  showDetail.value = true
}

async function saveEdit() {
  if (!answerCol.value) {
    ElMessage.warning("未检测到可编辑的列")
    return
  }
  saving.value = true
  try {
    await datasetApi.updateRow(dsId, activeSplit.value, detailIndex.value, { [answerCol.value]: editAnswer.value })
    ElMessage.success("已保存")
    showDetail.value = false
    await loadData()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "保存失败")
  } finally { saving.value = false }
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
