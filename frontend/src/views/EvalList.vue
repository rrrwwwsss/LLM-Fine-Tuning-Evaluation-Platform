<template>
  <div>
    <div style="margin-bottom: 20px;">
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon> 创建评测任务
      </el-button>
    </div>

    <el-table :data="tasks" stripe style="width: 100%" v-loading="loading">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="任务名称" min-width="160" />
      <el-table-column prop="model_name_or_path" label="模型" min-width="180" show-overflow-tooltip />
      <el-table-column prop="dataset_path" label="数据集" min-width="140" show-overflow-tooltip />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度" width="200">
        <template #default="{ row }">
          <el-progress :percentage="Math.round(row.progress * 100)" :status="row.status === 'completed' ? 'success' : ''" />
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="160">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push('/eval/' + row.id)">详情</el-button>
          <el-button size="small" @click="handleEdit(row)" :disabled="row.status === 'running'">编辑配置</el-button>
          <el-button size="small" type="primary" @click="handleStart(row)" :disabled="row.status === 'running'">
            {{ row.status === 'running' ? '运行中' : '启动' }}
          </el-button>
          <el-popconfirm title="确定删除?" @confirm="handleDelete(row.id)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showCreate" title="创建评测任务" width="600px">
      <el-form :model="form" label-width="140px">
        <el-form-item label="任务名称" required>
          <el-input v-model="form.name" placeholder="输入任务名称" />
        </el-form-item>

        <el-form-item label="模型服务" required>
          <el-tooltip content="选择已在「模型服务」页面启动的推理服务" placement="top">
            <el-select v-model="form.model_service_id" placeholder="选择运行中的模型服务" style="width: 100%;">
              <el-option
                v-for="s in runningServices"
                :key="s.id"
                :label="s.name + ' (' + s.model_name_or_path.split('/').pop() + ')'"
                :value="s.id"
              />
              <el-option label="没有可用的模型服务" :value="0" disabled />
            </el-select>
          </el-tooltip>
          <div style="font-size: 12px; color: #e6a23c; margin-top: 4px;" v-if="runningServices.length === 0">
            尚无运行中的模型服务，请先在「模型服务」页面启动
          </div>
        </el-form-item>

        <el-form-item label="评测数据集" required>
          <el-select v-model="form.dataset_id" placeholder="选择已划分的数据集" style="width: 100%;" @change="onDatasetSelect">
            <el-option
              v-for="d in availableDatasets"
              :key="d.id"
              :label="d.name + ' (' + d.test_rows + '条测试)'"
              :value="d.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">创建并启动</el-button>
      </template>
    </el-dialog>
  <!-- 编辑配置对话框 -->
  <el-dialog v-model="showEdit" title="编辑评测任务配置" width="600px">
    <el-form :model="editForm" label-width="140px">
      <el-form-item label="任务名称" required>
        <el-input v-model="editForm.name" placeholder="输入任务名称" />
      </el-form-item>
      <el-form-item label="模型服务" required>
        <el-select v-model="editForm.model_service_id" placeholder="选择运行中的模型服务" style="width: 100%;">
          <el-option
            v-for="s in runningServices"
            :key="s.id"
            :label="s.name + ' (' + s.model_name_or_path.split('/').pop() + ')'"
            :value="s.id"
          />
          <el-option label="没有可用的模型服务" :value="0" disabled />
        </el-select>
        <div style="font-size: 12px; color: #e6a23c; margin-top: 4px;" v-if="runningServices.length === 0">
          尚无运行中的模型服务，请先在「模型服务」页面启动
        </div>
      </el-form-item>
      <el-form-item label="评测数据集" required>
        <el-select v-model="editForm.dataset_id" placeholder="选择已划分的数据集" style="width: 100%;">
          <el-option
            v-for="d in availableDatasets"
            :key="d.id"
            :label="d.name + ' (' + d.test_rows + '条测试)'"
            :value="d.id"
          />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showEdit = false">取消</el-button>
      <el-button type="primary" @click="confirmEdit" :loading="editing">保存</el-button>
    </template>
  </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { evalApi, datasetApi, modelApi } from '../api'
import { ElMessage } from 'element-plus'

const tasks = ref<any[]>([])
const loading = ref(false)
const showCreate = ref(false)
const creating = ref(false)
const availableDatasets = ref<any[]>([])
const runningServices = ref<any[]>([])

const form = ref({
  name: '',
  model_service_id: 0,
  dataset_id: 0,
  dataset_path: ''
})

onMounted(async () => {
  await loadTasks()
  await loadDatasets()
  await loadServices()
})

async function loadTasks() {
  loading.value = true
  try { const res = await evalApi.list(); tasks.value = res.data.data || [] }
  catch { ElMessage.error('加载失败') }
  finally { loading.value = false }
}

async function loadDatasets() {
  try { const res = await datasetApi.getForEval(); availableDatasets.value = res.data.data || [] } catch { }
}

async function loadServices() {
  try { const res = await modelApi.list(); runningServices.value = (res.data.data || []).filter((s: any) => s.status === 'running') } catch { }
}

function onDatasetSelect(datasetId: number) {
  const ds = availableDatasets.value.find((d: any) => d.id === datasetId)
  if (ds && ds.test_csv) form.value.dataset_path = ds.test_csv
}

async function handleCreate() {
  if (!form.value.name || !form.value.model_service_id || !form.value.dataset_path) {
    ElMessage.warning('请填写完整信息')
    return
  }
  creating.value = true
  try {
    const service = runningServices.value.find((s: any) => s.id === form.value.model_service_id)
    const res = await evalApi.create({
      name: form.value.name,
      dataset_path: form.value.dataset_path,
      model_name_or_path: service?.model_name_or_path || '',
      adapter_path: service?.adapter_path || '',
      template: service?.template || '',
      model_service_id: form.value.model_service_id
    })
    const taskId = res.data.data?.id
    if (taskId) await evalApi.start(taskId)
    ElMessage.success('评测任务已创建并启动')
    showCreate.value = false
    form.value = { name: '', model_service_id: 0, dataset_id: 0, dataset_path: '' }
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally { creating.value = false }
}

const showEdit = ref(false)
const editing = ref(false)
const editForm = reactive({
  id: 0,
  name: "",
  dataset_id: 0,
  dataset_path: "",
  model_name_or_path: "",
  adapter_path: "",
  template: "",
  model_service_id: 0
})

async function loadRunningServices() {
  try {
    const res = await modelApi.getRunning()
    return res.data.data
  } catch { return null }
}

function handleEdit(row: any) {
  editForm.id = row.id
  editForm.name = row.name
  editForm.model_service_id = row.model_service_id || 0
  // 根据 model_service_id 反查服务信息
  const svc = runningServices.value.find((s: any) => s.id === editForm.model_service_id)
  editForm.model_name_or_path = svc?.model_name_or_path || row.model_name_or_path || ""
  editForm.adapter_path = svc?.adapter_path || row.adapter_path || ""
  editForm.template = svc?.template || row.template || ""
  // 根据 dataset_path 反查数据集
  const ds = availableDatasets.value.find((d: any) => d.test_csv === row.dataset_path)
  editForm.dataset_id = ds?.id || 0
  editForm.dataset_path = row.dataset_path || ""
  showEdit.value = true
}

async function confirmEdit() {
  if (!editForm.name || !editForm.model_service_id || !editForm.dataset_id) {
    ElMessage.warning("请填写完整信息")
    return
  }
  editing.value = true
  try {
    // 从选中的服务中获取模型信息
    const svc = runningServices.value.find((s: any) => s.id === editForm.model_service_id)
    // 从选中的数据集中获取路径
    const ds = availableDatasets.value.find((d: any) => d.id === editForm.dataset_id)

    await evalApi.update(editForm.id, {
      name: editForm.name,
      dataset_path: ds?.test_csv || editForm.dataset_path,
      model_name_or_path: svc?.model_name_or_path || "",
      adapter_path: svc?.adapter_path || "",
      template: svc?.template || "",
      model_service_id: editForm.model_service_id
    })
    ElMessage.success("配置已更新")
    showEdit.value = false
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "更新失败")
  } finally {
    editing.value = false
  }
}

async function handleStart(row: any) {
  try { await evalApi.start(row.id); ElMessage.success('已启动'); await loadTasks() }
  catch { ElMessage.error('启动失败') }
}

async function handleDelete(id: number) {
  try { await evalApi.delete(id); ElMessage.success('已删除'); await loadTasks() }
  catch { ElMessage.error('删除失败') }
}

function statusType(s: string) { return ({ pending: 'info', running: 'warning', completed: 'success', failed: 'danger', stopped: 'info' })[s] || 'info' }
function statusLabel(s: string) { return ({ pending: '待启动', running: '运行中', completed: '已完成', failed: '失败', stopped: '已停止' })[s] || s }
function formatTime(t: string) { if (!t) return ''; return new Date(t).toLocaleString('zh-CN') }
</script>
