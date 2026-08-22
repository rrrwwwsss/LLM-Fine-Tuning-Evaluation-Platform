<template>
  <div>
    <el-button @click="$router.push('/dataset')" style="margin-bottom: 16px;">
      <el-icon><ArrowLeft /></el-icon> 返回数据集列表
    </el-button>

    <el-card shadow="never" style="margin-bottom: 16px;">
      <template #header>
        <div class="card-header">
          <strong>{{ datasetId ? `编辑数据集：${dataset?.name || ''}` : '制作新数据集' }}</strong>
          <el-tag v-if="datasetId" :type="dataset?.status === 'converted' ? 'success' : 'info'">
            {{ dataset?.status === 'converted' ? '可参与训练' : '待划分' }}
          </el-tag>
        </div>
      </template>

      <el-alert
        :title="form.training_stage === 'dpo'
          ? 'DPO 数据必须分别指定 Prompt、Chosen（优选回答）和 Rejected（较差回答），Image 列可选。'
          : 'SFT 数据必须分别指定 Prompt 和 Answer，Image 列可选。自定义列都会保留在 CSV 中。'"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      />

      <el-form label-position="top">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="数据集名称" required>
              <el-input v-model="form.name" :disabled="!!datasetId" placeholder="例如：道路目标识别数据" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="训练类型" required>
              <el-select v-model="form.training_stage" style="width: 100%;" @change="changeTrainingStage">
                <el-option label="SFT 监督微调" value="sft" />
                <el-option label="DPO 偏好优化" value="dpo" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="默认训练集比例">
              <el-slider v-model="form.train_ratio" :min="0.5" :max="0.95" :step="0.05" show-input />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="记录数据来源、标注规范等信息" @input="datasetId && (schemaDirty = true)" />
        </el-form-item>
        <el-form-item label="图片前置路径（可选）">
          <div class="path-input-row">
            <el-input
              v-model="form.image_prefix"
              placeholder="Linux 示例：/HTC/rws/data/pic；图片列为相对路径时自动拼接"
              @input="datasetId && (schemaDirty = true)"
            />
            <ServerPathPicker v-model="form.image_prefix" button-text="浏览 Linux 目录" title="选择图片前置目录" @update:model-value="datasetId && (schemaDirty = true)" />
          </div>
        </el-form-item>
      </el-form>

      <div class="section-title">
        <span>列结构</span>
        <el-button size="small" @click="addColumn"><el-icon><Plus /></el-icon> 添加列</el-button>
      </div>
      <el-table :data="columns" border size="small">
        <el-table-column label="顺序" width="100" align="center">
          <template #default="{ $index }">
            <el-button text size="small" :disabled="$index === 0" @click="moveColumn($index, -1)">↑</el-button>
            <el-button text size="small" :disabled="$index === columns.length - 1" @click="moveColumn($index, 1)">↓</el-button>
          </template>
        </el-table-column>
        <el-table-column label="列名" min-width="170">
          <template #default="{ row }"><el-input v-model="row.name" @input="schemaDirty = true" /></template>
        </el-table-column>
        <el-table-column label="类型" width="150">
          <template #default="{ row }">
            <el-select v-model="row.type" @change="schemaDirty = true">
              <el-option v-for="item in columnTypes" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="训练用途" width="150">
          <template #default="{ row }">
            <el-select v-model="row.role" @change="schemaDirty = true">
              <el-option v-for="item in columnRoles" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="必填" width="80" align="center">
          <template #default="{ row }"><el-switch v-model="row.required" @change="schemaDirty = true" /></template>
        </el-table-column>
        <el-table-column label="默认值" min-width="130">
          <template #default="{ row }"><el-input v-model="row.default" @input="schemaDirty = true" /></template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ $index }">
            <el-button text type="danger" :disabled="columns.length === 1" @click="removeColumn($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 16px; text-align: right;">
        <el-button v-if="datasetId" type="primary" :loading="savingSchema" @click="saveSchema">保存列结构</el-button>
        <el-button v-else type="primary" :loading="creating" @click="createDataset">创建并开始录入</el-button>
      </div>
    </el-card>

    <el-card v-if="datasetId" shadow="never">
      <template #header>
        <div class="card-header">
          <strong>数据内容（{{ datasetTotal }} 条）</strong>
          <div>
            <el-button :loading="folderImporting" @click="selectImageFolder" :disabled="schemaDirty">
              <el-icon><FolderOpened /></el-icon>
              {{ folderImporting ? `导入中 ${folderProgress}%` : '从本地导入图片' }}
            </el-button>
            <el-button :loading="serverBrowserLoading" @click="openServerBrowser" :disabled="schemaDirty">
              <el-icon><FolderOpened /></el-icon>
              从Linux目录导入
            </el-button>
            <el-button @click="showBulk = true" :disabled="schemaDirty">批量粘贴</el-button>
            <el-button type="primary" @click="openAdd" :disabled="schemaDirty"><el-icon><Plus /></el-icon> 新增数据</el-button>
            <el-button type="success" @click="splitAndFinish" :loading="splitting" :disabled="schemaDirty || datasetTotal < 2">
              保存、划分并用于训练
            </el-button>
          </div>
        </div>
      </template>

      <el-alert
        v-if="schemaDirty"
        title="列结构已有修改，请先保存列结构再继续录入数据。修改原始数据后，旧的训练/测试划分会自动失效。"
        type="warning"
        :closable="false"
        style="margin-bottom: 12px;"
      />
      <el-alert
        v-else-if="folderImporting"
        title="正在上传图片并自动创建数据行，请不要关闭页面。"
        type="info"
        :closable="false"
        style="margin-bottom: 12px;"
      />

      <div class="filter-bar">
        <el-select v-model="filterColumn" clearable placeholder="选择筛选列" style="width: 180px;">
          <el-option v-for="column in columns" :key="column.name" :label="column.name" :value="column.name" />
        </el-select>
        <el-select v-model="filterMode" style="width: 120px;">
          <el-option label="包含" value="contains" />
          <el-option label="等于" value="equals" />
          <el-option label="为空" value="empty" />
          <el-option label="不为空" value="not_empty" />
        </el-select>
        <el-input
          v-if="filterMode === 'contains' || filterMode === 'equals'"
          v-model="filterValue"
          clearable
          placeholder="输入筛选内容"
          style="width: 260px;"
          @keyup.enter="applyFilter"
        />
        <el-button type="primary" plain @click="applyFilter">筛选</el-button>
        <el-button v-if="activeFilter.column" @click="clearFilter">清除筛选</el-button>
        <span v-if="activeFilter.column" class="filter-result">筛选到 {{ total }} 条</span>
      </div>

      <div class="batch-bar">
        <span>已勾选 {{ selectedRows.length }} 条</span>
        <el-select v-model="batchScope" style="width: 170px;">
          <el-option label="操作勾选行" value="selected" />
          <el-option label="操作全部筛选结果" value="filtered" :disabled="!activeFilter.column" />
        </el-select>
        <el-select v-model="assignmentColumn" clearable placeholder="选择赋值列" style="width: 180px;">
          <el-option v-for="column in columns" :key="column.name" :label="column.name" :value="column.name" />
        </el-select>
        <el-input v-model="assignmentValue" clearable placeholder="统一赋值内容" style="width: 240px;" />
        <el-button type="primary" :loading="batchOperating" @click="runBatchOperation('assign')">统一赋值</el-button>
        <el-button type="danger" :loading="batchOperating" @click="runBatchOperation('delete')">批量删除</el-button>
      </div>

      <el-table
        ref="dataTableRef"
        :data="rows"
        row-key="_row_index"
        border
        stripe
        size="small"
        max-height="560"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="48" fixed="left" />
        <el-table-column type="index" label="#" width="55" />
        <el-table-column v-for="column in columns" :key="column.name" :label="column.name" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <el-image
              v-if="column.type === 'image' && row[column.name]"
              :src="fileUrl(row[column.name])"
              fit="cover"
              style="width: 54px; height: 40px; border-radius: 4px;"
              :preview-src-list="[fileUrl(row[column.name])]"
              preview-teleported
            />
            <span v-else>{{ row[column.name] }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确定删除这条数据？" @confirm="deleteSourceRow(row)">
              <template #reference><el-button text type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-wrap">
        <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total"
          layout="prev, pager, next, total, sizes" :page-sizes="[20, 50, 100]"
          @current-change="loadRows" @size-change="loadRows" />
      </div>
    </el-card>

    <el-dialog v-model="showRowDialog" :title="editingIndex >= 0 ? '编辑数据' : '新增数据'" width="760px" top="4vh">
      <el-form label-position="top">
        <el-form-item v-for="column in columns" :key="column.name" :label="`${column.name}${column.required ? ' *' : ''}`">
          <el-input v-if="column.type === 'long_text' || column.type === 'json'" v-model="rowDraft[column.name]" type="textarea" :rows="4" />
          <el-input-number v-else-if="column.type === 'number'" v-model="rowDraft[column.name]" style="width: 100%;" />
          <div v-else-if="column.type === 'image'" class="image-field">
            <el-input v-model="rowDraft[column.name]" placeholder="相对路径、绝对路径，或上传图片" />
            <el-upload :show-file-list="false" :http-request="imageUploadHandler(column.name)">
              <el-button>上传图片</el-button>
            </el-upload>
            <ServerPathPicker v-model="rowDraft[column.name]" mode="image" button-text="Linux 图片" title="选择服务器图片" />
          </div>
          <el-input v-else v-model="rowDraft[column.name]" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRowDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingRow" @click="saveRow">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showBulk" title="批量粘贴数据" width="760px">
      <el-alert :title="`按当前列顺序粘贴制表符分隔的数据：${columns.map(c => c.name).join(' → ')}`" type="info" :closable="false" />
      <el-input v-model="bulkText" type="textarea" :rows="14" placeholder="可直接从 Excel 复制多行；第一行若与列名一致会自动忽略" style="margin-top: 12px;" />
      <template #footer>
        <el-button @click="showBulk = false">取消</el-button>
        <el-button type="primary" :loading="savingRow" @click="saveBulk">导入</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showServerBrowser" title="选择 Linux 服务器图片目录" width="720px" :close-on-click-modal="false">
      <el-alert
        title="这里只显示管理员通过 SERVER_BROWSE_ROOTS 配置的服务器目录。双击文件夹进入，选中当前目录后会递归扫描图片。"
        type="info"
        :closable="false"
        style="margin-bottom: 12px;"
      />
      <div class="server-browser-path">
        <el-button :disabled="!serverParentPath" @click="loadServerDirectory(serverParentPath)">上一级</el-button>
        <el-input :model-value="serverCurrentPath || '请选择一个授权根目录'" readonly />
      </div>
      <el-table
        :data="serverDirectories"
        v-loading="serverBrowserLoading"
        height="360"
        border
        style="margin-top: 12px;"
        @row-dblclick="enterServerDirectory"
      >
        <el-table-column label="目录" min-width="420">
          <template #default="{ row }"><el-icon><FolderOpened /></el-icon> {{ row.name }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }"><el-button text type="primary" @click="enterServerDirectory(row)">进入</el-button></template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="showServerBrowser = false">取消</el-button>
        <el-button type="primary" :disabled="!serverCurrentPath" :loading="serverBrowserLoading" @click="chooseServerDirectory">
          选择当前目录
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showFolderDialog" :title="folderSource === 'server' ? '从 Linux 目录导入图片' : '从本地文件夹导入图片'" width="620px" :close-on-click-modal="false">
      <el-alert
        :title="folderSource === 'server'
          ? `服务器目录 ${serverFolderPath} 中检测到 ${selectedImageCount} 张图片；不会重复上传图片文件。`
          : `已选择 ${selectedImageCount} 张图片；图片会上传到当前数据集目录，每张图片自动创建一条数据，并保留文件夹内的相对路径。`"
        type="info"
        :closable="false"
        style="margin-bottom: 16px;"
      />
      <el-form label-position="top">
        <el-form-item v-if="folderSource === 'local'" label="图片路径保存到哪一层">
          <el-select v-model="pathStripLevels" style="width: 100%;">
            <el-option
              v-for="option in pathLevelOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <div style="font-size: 12px; color: #909399; margin-top: 6px;">
            下拉框展示的是图片列最终保存的路径示例；浏览器不会提供 F: 等本地盘符。
          </div>
        </el-form-item>
        <el-form-item v-else label="Linux 图片前置路径与保存效果">
          <el-select v-model="serverPathBase" style="width: 100%;">
            <el-option
              v-for="option in serverBaseOptions"
              :key="option.base"
              :label="option.label"
              :value="option.base"
            />
          </el-select>
          <div style="font-size: 12px; color: #909399; margin-top: 6px;">
            前置路径会保存到数据集配置中，用于网页预览、训练转换和 Linux 文件读取。
          </div>
        </el-form-item>
        <el-form-item label="统一赋值的列（可选）">
          <el-select v-model="batchColumn" clearable placeholder="不统一赋值" style="width: 100%;">
            <el-option
              v-for="column in columns.filter(item => item.role !== 'image')"
              :key="column.name"
              :label="`${column.name}${column.role !== 'other' ? ` · ${column.role}` : ''}`"
              :value="column.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="batchColumn" label="统一值">
          <el-input v-model="batchValue" type="textarea" :rows="4" placeholder="这个值会写入本批所有图片对应行的所选列" />
        </el-form-item>
      </el-form>
      <div style="font-size: 12px; color: #909399;">
        可把 Prompt 统一设置为“请描述图片内容”；已经存在于图片列的相对路径会自动跳过。
      </div>
      <template #footer>
        <el-button @click="showFolderDialog = false">取消</el-button>
        <el-button type="primary" @click="startFolderImport">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { datasetApi } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import ServerPathPicker from '../components/ServerPathPicker.vue'

interface DatasetColumn {
  name: string
  type: string
  role: string
  required: boolean
  default: any
  source_name?: string
}

const route = useRoute()
const router = useRouter()
const datasetId = ref(Number(route.query.id) || 0)
const dataset = ref<any>(null)
const form = ref({ name: '', description: '', train_ratio: 0.8, training_stage: 'sft', image_prefix: '' })
const columns = ref<DatasetColumn[]>([
  { name: 'prompt_text', type: 'long_text', role: 'prompt', required: true, default: '', source_name: 'prompt_text' },
  { name: 'model_result', type: 'long_text', role: 'answer', required: true, default: '', source_name: 'model_result' },
  { name: 'image_path', type: 'image', role: 'image', required: false, default: '', source_name: 'image_path' },
])
const columnTypes = [
  { label: '单行文本', value: 'text' }, { label: '长文本', value: 'long_text' },
  { label: '数字', value: 'number' }, { label: '标签', value: 'label' },
  { label: '图片', value: 'image' }, { label: 'JSON', value: 'json' },
]
const columnRoles = [
  { label: '普通字段', value: 'other' }, { label: 'Prompt', value: 'prompt' },
  { label: 'Answer', value: 'answer' }, { label: 'Image', value: 'image' },
  { label: 'Chosen（优选）', value: 'chosen' }, { label: 'Rejected（较差）', value: 'rejected' },
  { label: 'Label', value: 'label' },
]
const creating = ref(false)
const savingSchema = ref(false)
const schemaDirty = ref(false)
const rows = ref<any[]>([])
const total = ref(0)
const datasetTotal = ref(0)
const page = ref(1)
const pageSize = ref(50)
const showRowDialog = ref(false)
const rowDraft = ref<Record<string, any>>({})
const editingIndex = ref(-1)
const savingRow = ref(false)
const splitting = ref(false)
const showBulk = ref(false)
const bulkText = ref('')
const folderImporting = ref(false)
const folderProgress = ref(0)
const showFolderDialog = ref(false)
const pendingFolderFiles = ref<File[]>([])
const batchColumn = ref('')
const batchValue = ref('')
const pathStripLevels = ref(1)
const pathLevelOptions = ref<{ label: string; value: number }[]>([])
const folderSource = ref<'local' | 'server'>('local')
const selectedImageCount = ref(0)
const showServerBrowser = ref(false)
const serverBrowserLoading = ref(false)
const serverCurrentPath = ref('')
const serverParentPath = ref('')
const serverDirectories = ref<any[]>([])
const serverFolderPath = ref('')
const serverPathBase = ref('')
const serverBaseOptions = ref<any[]>([])
const filterColumn = ref('')
const filterMode = ref('contains')
const filterValue = ref('')
const activeFilter = ref({ column: '', mode: 'contains', value: '' })
const selectedRows = ref<any[]>([])
const batchScope = ref('selected')
const assignmentColumn = ref('')
const assignmentValue = ref('')
const batchOperating = ref(false)
const dataTableRef = ref<any>(null)
let syncingFilterSelection = false

onMounted(async () => {
  if (datasetId.value) await loadExisting()
})

function schemaError(requireMappings = false): string {
  const names = columns.value.map(c => c.name.trim())
  if (names.some(name => !name)) return '列名不能为空'
  if (new Set(names).size !== names.length) return '列名不能重复'
  for (const role of ['prompt', 'answer', 'chosen', 'rejected', 'image']) {
    if (columns.value.filter(c => c.role === role).length > 1) return `${role} 用途只能指定一列`
  }
  const requiredRoles = form.value.training_stage === 'dpo' ? ['prompt', 'chosen', 'rejected'] : ['prompt', 'answer']
  if (requireMappings) {
    const missing = requiredRoles.filter(role => !columns.value.some(c => c.role === role))
    if (missing.length) return `${form.value.training_stage.toUpperCase()} 数据缺少字段映射：${missing.join(', ')}`
  }
  return ''
}

function addColumn() {
  columns.value.push({ name: `column_${columns.value.length + 1}`, type: 'text', role: 'other', required: false, default: '', source_name: '' })
  schemaDirty.value = true
}
function removeColumn(index: number) { columns.value.splice(index, 1); schemaDirty.value = true }
function moveColumn(index: number, offset: number) {
  const target = index + offset
  const item = columns.value.splice(index, 1)[0]
  columns.value.splice(target, 0, item)
  schemaDirty.value = true
}

function changeTrainingStage(stage: string) {
  if (!datasetId.value) {
    columns.value = stage === 'dpo'
      ? [
          { name: 'prompt_text', type: 'long_text', role: 'prompt', required: true, default: '', source_name: 'prompt_text' },
          { name: 'chosen', type: 'long_text', role: 'chosen', required: true, default: '', source_name: 'chosen' },
          { name: 'rejected', type: 'long_text', role: 'rejected', required: true, default: '', source_name: 'rejected' },
          { name: 'image_path', type: 'image', role: 'image', required: false, default: '', source_name: 'image_path' },
        ]
      : [
          { name: 'prompt_text', type: 'long_text', role: 'prompt', required: true, default: '', source_name: 'prompt_text' },
          { name: 'model_result', type: 'long_text', role: 'answer', required: true, default: '', source_name: 'model_result' },
          { name: 'image_path', type: 'image', role: 'image', required: false, default: '', source_name: 'image_path' },
        ]
  }
  schemaDirty.value = !!datasetId.value
}

function schemaPayload() {
  return columns.value.map(c => ({ ...c, name: c.name.trim(), source_name: c.source_name || c.name.trim() }))
}

async function createDataset() {
  const error = schemaError()
  if (!form.value.name.trim()) return ElMessage.warning('请填写数据集名称')
  if (error) return ElMessage.warning(error)
  creating.value = true
  try {
    const res = await datasetApi.create({ ...form.value, columns: schemaPayload() })
    datasetId.value = res.data.data.id
    dataset.value = res.data.data
    columns.value.forEach(c => { c.source_name = c.name })
    schemaDirty.value = false
    await router.replace({ path: '/dataset/create', query: { id: datasetId.value } })
    ElMessage.success('数据集已创建，可以开始录入数据')
    await loadRows()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '创建失败') }
  finally { creating.value = false }
}

async function loadExisting() {
  try {
    const [datasetRes, schemaRes] = await Promise.all([datasetApi.get(datasetId.value), datasetApi.getSchema(datasetId.value)])
    dataset.value = datasetRes.data.data
    form.value.name = dataset.value.name
    form.value.train_ratio = dataset.value.train_ratio || 0.8
    form.value.description = schemaRes.data.data.description || ''
    form.value.training_stage = schemaRes.data.data.training_stage || 'sft'
    form.value.image_prefix = schemaRes.data.data.image_prefix || ''
    columns.value = (schemaRes.data.data.columns || []).map((c: DatasetColumn) => ({ ...c, source_name: c.name }))
    schemaDirty.value = false
    await loadRows()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载数据集失败')
    router.push('/dataset')
  }
}

async function saveSchema() {
  const error = schemaError()
  if (error) return ElMessage.warning(error)
  if (datasetTotal.value > 0) {
    try {
      await ElMessageBox.confirm('列结构修改会使已有训练/测试划分失效，确定继续？', '修改列结构', { type: 'warning' })
    } catch { return }
  }
  savingSchema.value = true
  try {
    await datasetApi.updateSchema(datasetId.value, {
      description: form.value.description,
      training_stage: form.value.training_stage,
      image_prefix: form.value.image_prefix,
      columns: schemaPayload(),
    })
    columns.value.forEach(c => { c.source_name = c.name })
    schemaDirty.value = false
    ElMessage.success('列结构已保存')
    await loadRows()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '保存失败') }
  finally { savingSchema.value = false }
}

async function loadRows() {
  const filter = activeFilter.value.column ? {
    filter_column: activeFilter.value.column,
    filter_mode: activeFilter.value.mode,
    filter_value: activeFilter.value.value,
  } : {}
  const res = await datasetApi.getSource(datasetId.value, page.value, pageSize.value, filter)
  rows.value = res.data.data.rows || []
  total.value = res.data.data.total || 0
  datasetTotal.value = res.data.data.dataset_total ?? total.value
  selectedRows.value = []
  await nextTick()
  syncingFilterSelection = true
  dataTableRef.value?.clearSelection()
  if (activeFilter.value.column && batchScope.value === 'filtered' && rows.value.length) {
    rows.value.forEach(row => dataTableRef.value?.toggleRowSelection(row, true))
  }
  syncingFilterSelection = false
}

function handleSelectionChange(selection: any[]) {
  selectedRows.value = selection
  if (!syncingFilterSelection && activeFilter.value.column && batchScope.value === 'filtered') {
    batchScope.value = 'selected'
  }
}

async function applyFilter() {
  if (!filterColumn.value) return ElMessage.warning('请选择筛选列')
  if ((filterMode.value === 'contains' || filterMode.value === 'equals') && !filterValue.value) {
    return ElMessage.warning('请输入筛选内容；筛选空值请使用“为空”')
  }
  activeFilter.value = { column: filterColumn.value, mode: filterMode.value, value: filterValue.value }
  batchScope.value = 'filtered'
  page.value = 1
  await loadRows()
}

async function clearFilter() {
  filterColumn.value = ''
  filterMode.value = 'contains'
  filterValue.value = ''
  activeFilter.value = { column: '', mode: 'contains', value: '' }
  batchScope.value = 'selected'
  page.value = 1
  await loadRows()
}

async function runBatchOperation(action: 'assign' | 'delete') {
  if (batchScope.value === 'selected' && !selectedRows.value.length) {
    return ElMessage.warning('请先勾选要操作的数据行')
  }
  if (batchScope.value === 'filtered' && !activeFilter.value.column) {
    return ElMessage.warning('请先设置筛选条件')
  }
  if (action === 'assign' && !assignmentColumn.value) {
    return ElMessage.warning('请选择要统一赋值的列')
  }
  const count = batchScope.value === 'selected' ? selectedRows.value.length : total.value
  const scopeText = batchScope.value === 'selected' ? `${count} 条勾选数据` : `${count} 条筛选结果`
  if (action === 'delete') {
    try {
      await ElMessageBox.confirm(`确定永久删除${scopeText}？`, '批量删除', { type: 'warning' })
    } catch { return }
  } else {
    try {
      await ElMessageBox.confirm(`确定把${scopeText}的“${assignmentColumn.value}”统一修改为当前输入值？`, '统一赋值', { type: 'warning' })
    } catch { return }
  }
  batchOperating.value = true
  try {
    const res = await datasetApi.batchSourceRows(datasetId.value, {
      action,
      scope: batchScope.value,
      row_indices: selectedRows.value.map(row => row._row_index),
      filter_column: activeFilter.value.column,
      filter_mode: activeFilter.value.mode,
      filter_value: activeFilter.value.value,
      assignment_column: assignmentColumn.value,
      assignment_value: assignmentValue.value,
    })
    ElMessage.success(`${action === 'delete' ? '已删除' : '已更新'} ${res.data.data.affected} 条数据`)
    page.value = 1
    await loadRows()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '批量操作失败')
  } finally {
    batchOperating.value = false
  }
}

function emptyRow() {
  return Object.fromEntries(columns.value.map(c => [c.name, c.default ?? '']))
}
function openAdd() { editingIndex.value = -1; rowDraft.value = emptyRow(); showRowDialog.value = true }
function openEdit(row: any) {
  editingIndex.value = row._row_index
  rowDraft.value = Object.fromEntries(columns.value.map(c => [c.name, row[c.name] ?? '']))
  showRowDialog.value = true
}

async function saveRow() {
  savingRow.value = true
  try {
    if (editingIndex.value >= 0) await datasetApi.updateSourceRow(datasetId.value, editingIndex.value, rowDraft.value)
    else await datasetApi.appendRows(datasetId.value, [rowDraft.value])
    showRowDialog.value = false
    ElMessage.success('数据已保存')
    await loadRows()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '保存失败') }
  finally { savingRow.value = false }
}

async function deleteSourceRow(row: any) {
  try {
    await datasetApi.deleteSourceRow(datasetId.value, row._row_index)
    ElMessage.success('已删除')
    await loadRows()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '删除失败') }
}

async function uploadImage(columnName: string, options: any) {
  try {
    const res = await datasetApi.uploadImage(datasetId.value, options.file)
    rowDraft.value[columnName] = res.data.data.path
    ElMessage.success('图片已上传')
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '图片上传失败') }
}

function imageUploadHandler(columnName: string) {
  return (options: any) => uploadImage(columnName, options)
}

function selectImageFolder() {
  if (!columns.value.some(column => column.role === 'image')) {
    ElMessage.warning('请先设置一个用途为 Image 的列')
    return
  }
  const input = document.createElement('input')
  input.type = 'file'
  input.multiple = true
  input.accept = 'image/*'
  input.setAttribute('webkitdirectory', '')
  input.onchange = async () => {
    const files = Array.from(input.files || []).filter(file => /\.(jpg|jpeg|png|gif|bmp|webp)$/i.test(file.name))
    if (!files.length) return ElMessage.warning('所选文件夹中没有支持的图片')
    pendingFolderFiles.value = files
    folderSource.value = 'local'
    selectedImageCount.value = files.length
    batchColumn.value = ''
    batchValue.value = ''
    const samplePath = String((files[0] as any).webkitRelativePath || files[0].name).replace(/\\/g, '/')
    const parts = samplePath.split('/').filter(Boolean)
    const maxSafeStrip = Math.min(...files.map(file => {
      const relativePath = String((file as any).webkitRelativePath || file.name).replace(/\\/g, '/')
      return Math.max(0, relativePath.split('/').filter(Boolean).length - 1)
    }))
    pathLevelOptions.value = parts.slice(0, maxSafeStrip + 1).map((_, index) => ({
      value: index,
      label: `保存为：${parts.slice(index).join('/')}`,
    }))
    pathStripLevels.value = maxSafeStrip >= 1 ? 1 : 0
    showFolderDialog.value = true
  }
  input.click()
}

async function openServerBrowser() {
  if (!columns.value.some(column => column.role === 'image')) {
    return ElMessage.warning('请先设置一个用途为 Image 的列')
  }
  showServerBrowser.value = true
  await loadServerDirectory('')
}

async function loadServerDirectory(path: string) {
  serverBrowserLoading.value = true
  try {
    const res = await datasetApi.browseServerDirectories(path)
    const data = res.data.data
    serverCurrentPath.value = data.current || ''
    serverParentPath.value = data.parent || ''
    serverDirectories.value = (data.entries || []).filter((entry: any) => entry.kind === 'directory')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '无法读取 Linux 服务器目录')
  } finally {
    serverBrowserLoading.value = false
  }
}

function enterServerDirectory(row: any) {
  loadServerDirectory(row.path)
}

async function chooseServerDirectory() {
  if (!serverCurrentPath.value) return
  serverBrowserLoading.value = true
  try {
    const res = await datasetApi.inspectServerImageFolder(serverCurrentPath.value)
    const data = res.data.data
    folderSource.value = 'server'
    serverFolderPath.value = data.folder
    selectedImageCount.value = Number(data.count || 0)
    serverBaseOptions.value = data.base_options || []
    serverPathBase.value = serverBaseOptions.value[serverBaseOptions.value.length - 1]?.base || ''
    batchColumn.value = ''
    batchValue.value = ''
    showServerBrowser.value = false
    showFolderDialog.value = true
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '所选 Linux 目录中没有可导入图片')
  } finally {
    serverBrowserLoading.value = false
  }
}

async function startFolderImport() {
  const commonValues = batchColumn.value ? { [batchColumn.value]: batchValue.value } : {}
  showFolderDialog.value = false
  folderImporting.value = true
  folderProgress.value = 0
  let imported = 0
  let skipped = 0
  try {
    if (folderSource.value === 'server') {
      const res = await datasetApi.importServerImageFolder(datasetId.value, {
        folder_path: serverFolderPath.value,
        path_base: serverPathBase.value,
        common_values: commonValues,
      })
      imported = Number(res.data.data.imported || 0)
      skipped = Number(res.data.data.skipped || 0)
      form.value.image_prefix = res.data.data.image_prefix || serverPathBase.value
      ElMessage.success(`服务器目录导入完成：新增 ${imported} 张，跳过重复路径 ${skipped} 张`)
      page.value = 1
      await loadRows()
      return
    }
    const files = pendingFolderFiles.value
    if (!files.length) return
    const batchSize = 50
    for (let index = 0; index < files.length; index += batchSize) {
      const batch = files.slice(index, index + batchSize)
      const res = await datasetApi.importImageFolder(datasetId.value, batch, commonValues, pathStripLevels.value)
      imported += Number(res.data.data.imported ?? batch.length)
      skipped += Number(res.data.data.skipped || 0)
      folderProgress.value = Math.round(Math.min(index + batch.length, files.length) / files.length * 100)
    }
    ElMessage.success(`导入完成：新增 ${imported} 张，跳过重复路径 ${skipped} 张`)
    page.value = 1
    await loadRows()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || `导入中断，已新增 ${imported} 张、跳过 ${skipped} 张`)
    await loadRows()
  } finally {
    folderImporting.value = false
    folderProgress.value = 0
    pendingFolderFiles.value = []
    selectedImageCount.value = 0
  }
}

async function saveBulk() {
  const lines = bulkText.value.split(/\r?\n/).filter(line => line.trim())
  if (!lines.length) return ElMessage.warning('请粘贴数据')
  const names = columns.value.map(c => c.name)
  const values = lines.map(line => line.split('\t'))
  if (values[0].every((value, index) => value.trim() === names[index])) values.shift()
  const data = values.map(items => Object.fromEntries(names.map((name, index) => [name, items[index] ?? ''])))
  savingRow.value = true
  try {
    await datasetApi.appendRows(datasetId.value, data)
    showBulk.value = false
    bulkText.value = ''
    ElMessage.success(`已导入 ${data.length} 条数据`)
    await loadRows()
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '批量导入失败') }
  finally { savingRow.value = false }
}

async function splitAndFinish() {
  const error = schemaError(true)
  if (error) return ElMessage.warning(error)
  splitting.value = true
  try {
    await datasetApi.split(datasetId.value, form.value.train_ratio)
    ElMessage.success('数据集已划分并转换，可以直接用于微调')
    router.push(`/dataset/${datasetId.value}`)
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || '划分或转换失败') }
  finally { splitting.value = false }
}

function fileUrl(value: string) {
  let path = String(value || '').replace(/\\/g, '/')
  if (!path.startsWith('/') && !/^[A-Za-z]:\//.test(path)) {
    return `/api/v1/dataset/${datasetId.value}/asset?path=${encodeURIComponent(path)}`
  }
  return '/api/file?path=' + encodeURIComponent(path)
}
</script>

<style scoped>
.card-header, .section-title { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.section-title { margin: 4px 0 12px; font-weight: 600; }
.pagination-wrap { margin-top: 16px; display: flex; justify-content: center; }
.filter-bar, .batch-bar { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; }
.batch-bar { padding: 10px 12px; background: #f5f7fa; border-radius: 6px; }
.filter-result { color: #606266; font-size: 13px; }
.image-field { width: 100%; display: flex; gap: 8px; }
.image-field .el-input { flex: 1; }
.path-input-row { display: flex; align-items: center; width: 100%; }
.path-input-row .el-input { flex: 1; }
</style>
