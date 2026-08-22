<template>
  <span class="server-path-picker">
    <el-button @click="openPicker">{{ buttonText }}</el-button>
    <el-dialog v-model="visible" :title="title" width="720px" append-to-body>
      <el-alert
        title="只显示 Linux 启动脚本配置的 /HTC/rws 白名单目录。若列表为空，请查看页面错误提示和 logs/backend.log。"
        type="info"
        :closable="false"
      />
      <div class="path-row">
        <el-button :disabled="!parentPath" @click="loadDirectory(parentPath)">上一级</el-button>
        <el-input :model-value="currentPath || '请选择 /HTC/rws 根目录'" readonly />
      </div>
      <el-table
        :data="visibleEntries"
        v-loading="loading"
        height="380"
        border
        style="margin-top: 12px;"
        @row-dblclick="openEntry"
      >
        <el-table-column label="名称" min-width="430">
          <template #default="{ row }">{{ row.kind === 'directory' ? '📁' : fileLabel }} {{ row.name }}</template>
        </el-table-column>
        <el-table-column label="类型" width="110">
          <template #default="{ row }">{{ row.kind === 'directory' ? '目录' : fileLabel }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button text type="primary" @click="openEntry(row)">{{ row.kind === 'directory' ? '进入' : '选择' }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button v-if="mode === 'directory'" type="primary" :disabled="!currentPath" @click="selectPath(currentPath)">
          选择当前目录
        </el-button>
      </template>
    </el-dialog>
  </span>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { datasetApi } from '../api'

const props = withDefaults(defineProps<{
  modelValue?: string
  mode?: 'directory' | 'image' | 'csv'
  buttonText?: string
  title?: string
}>(), {
  modelValue: '',
  mode: 'directory',
  buttonText: '浏览 Linux 目录',
  title: '选择 Linux 服务器路径',
})

const emit = defineEmits<{ (event: 'update:modelValue', value: string): void }>()
const visible = ref(false)
const loading = ref(false)
const currentPath = ref('')
const parentPath = ref('')
const entries = ref<any[]>([])

const visibleEntries = computed(() => entries.value.filter(entry => {
  if (entry.kind === 'directory') return true
  return entry.kind === props.mode
}))
const fileLabel = computed(() => props.mode === 'image' ? '图片' : 'CSV')

async function openPicker() {
  visible.value = true
  await loadDirectory('')
}

async function loadDirectory(path: string) {
  loading.value = true
  try {
    const res = await datasetApi.browseServerDirectories(path)
    const data = res.data.data
    currentPath.value = data.current || ''
    parentPath.value = data.parent || ''
    entries.value = data.entries || []
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '无法读取 Linux 服务器目录')
  } finally {
    loading.value = false
  }
}

function openEntry(entry: any) {
  if (entry.kind === 'directory') return loadDirectory(entry.path)
  selectPath(entry.path)
}

function selectPath(path: string) {
  emit('update:modelValue', path)
  visible.value = false
}
</script>

<style scoped>
.server-path-picker { display: inline-flex; margin-left: 8px; }
.path-row { display: flex; gap: 8px; margin-top: 12px; }
</style>
