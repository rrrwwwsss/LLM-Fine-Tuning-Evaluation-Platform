<template>
  <div>
    <div style="margin-bottom: 20px; display: flex; gap: 12px;">
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon> 创建微调任务
      </el-button>
      <el-button @click="loadTasks">
        <el-icon><Refresh /></el-icon> 刷新
      </el-button>
    </div>

    <el-table :data="tasks" stripe style="width: 100%" v-loading="loading">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="任务名称" min-width="160" />
      <el-table-column label="训练类型" width="100">
        <template #default="{ row }">
          <el-tag :type="row.training_stage === 'dpo' ? 'warning' : 'primary'" size="small">{{ (row.training_stage || 'sft').toUpperCase() }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="base_model" label="基础模型" min-width="200" show-overflow-tooltip />
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度" width="200">
        <template #default="{ row }">
          <el-progress :percentage="Math.round(row.progress * 100)" :status="row.status === 'completed' ? 'success' : ''" />
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="310" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push('/finetune/' + row.id)">详情</el-button>
          <el-button size="small" @click="handleEdit(row)" :disabled="row.status === 'running'">编辑配置</el-button>
          <el-button size="small" type="primary" @click="handleStart(row)" :disabled="row.status === 'running'">
            {{ row.status === "running" ? "运行中" : "启动" }}
          </el-button>
          <el-popconfirm title="确定删除?" @confirm="handleDelete(row.id)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建对话框 -->
    <el-dialog v-model="showCreate" title="创建微调任务" width="820px">
      <el-form :model="form" label-width="150px" label-position="top">
        <el-form-item label="任务名称" required>
          <el-tooltip content="给本次微调任务起个名字，方便识别" placement="top">
            <el-input v-model="form.name" placeholder="如: qwen_lora_exp1" />
          </el-tooltip>
        </el-form-item>

        <el-form-item label="训练类型" required>
          <el-radio-group v-model="form.stage" @change="handleStageChange">
            <el-radio-button value="sft">SFT 监督微调</el-radio-button>
            <el-radio-button value="dpo">DPO 偏好优化</el-radio-button>
          </el-radio-group>
          <div style="font-size: 12px; color: #999; margin-top: 4px;">
            DPO 数据集必须包含 Prompt、Chosen 和 Rejected，并已转换为偏好数据格式
          </div>
        </el-form-item>

        <el-form-item label="训练数据集" required>
          <el-tooltip content="选择已在数据集管理中上传并转换好的数据集，YAML 会自动引用该数据集的 dataset_info.json" placement="top">
            <el-select v-model="form.dataset_id" placeholder="选择已转换的数据集" style="width: 100%;">
              <el-option
                v-for="d in availableDatasets"
                :key="d.id"
                :label="`${d.name} [${(d.training_stage || 'sft').toUpperCase()}] (${d.train_rows}条训练)`"
                :value="d.id"
                :disabled="(d.training_stage || 'sft') !== form.stage"
              />
              <el-option label="手动填写 YAML" :value="0" />
            </el-select>
          </el-tooltip>
        </el-form-item>

        <el-form-item label="基础模型路径" required>
          <el-tooltip content="指定预训练模型的本地路径或 HuggingFace 模型名，如 /path/to/Qwen2.5-7B-Instruct 或 Qwen/Qwen2.5-7B-Instruct" placement="top">
            <div class="path-input-row">
              <el-input v-model="form.model_name_or_path" placeholder="如: /HTC/rws/Qwen/Qwen3.5-VL-27B" />
              <ServerPathPicker v-model="form.model_name_or_path" button-text="浏览 Linux 模型目录" title="选择基础模型目录" />
            </div>
          </el-tooltip>
        </el-form-item>

        <el-form-item label="模型模板" required>
          <el-tooltip content="LLaMA-Factory 使用的对话模板，必须与模型类型匹配。Qwen 系列用 qwen2.5/qwen3_5，Llama 系列用 llama3。支持手动输入自定义模板名" placement="top">
            <el-select v-model="form.template" placeholder="选择或输入模板" style="width: 100%;" filterable allow-create>
              <el-option label="qwen2.5" value="qwen2.5" />
              <el-option label="qwen2_vl" value="qwen2_vl" />
              <el-option label="qwen3" value="qwen3" />
              <el-option label="qwen3_5" value="qwen3_5" />
              <el-option label="qwen3_6" value="qwen3_6" />
              <el-option label="qwen3_vl" value="qwen3_vl" />
              <el-option label="llama3" value="llama3" />
              <el-option label="baichuan2" value="baichuan2" />
              <el-option label="chatglm3" value="chatglm3" />
              <el-option label="deepseek" value="deepseek" />
              <el-option label="mistral" value="mistral" />
            </el-select>
          </el-tooltip>
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="LoRA 目标" required>
              <el-tooltip content="选择要应用 LoRA 的线性层。q_proj/v_proj/k_proj/o_proj 是注意力层，gate_proj/up_proj/down_proj 是前馈层。选择越多效果越好，显存占用也越大" placement="top">
                <el-checkbox-group v-model="form.lora_target">
                  <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                    <el-checkbox label="q_proj" />
                    <el-checkbox label="v_proj" />
                    <el-checkbox label="k_proj" />
                    <el-checkbox label="o_proj" />
                    <el-checkbox label="gate_proj" />
                    <el-checkbox label="up_proj" />
                    <el-checkbox label="down_proj" />
                  </div>
                </el-checkbox-group>
              </el-tooltip>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="输出目录">
              <el-tooltip content="微调权重保存路径。默认 ./saves/任务名称，可自定义" placement="top">
                <div class="path-input-row">
                  <el-input v-model="form.output_dir" placeholder="自动填充: ./saves/任务名称" />
                  <ServerPathPicker v-model="form.output_dir" button-text="选择 Linux 目录" title="选择训练输出目录" />
                </div>
              </el-tooltip>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row v-if="form.stage === 'dpo'" :gutter="16">
          <el-col :span="12">
            <el-form-item label="DPO Beta">
              <el-tooltip content="偏好损失强度，LLaMA-Factory 默认值为 0.1" placement="top">
                <el-input-number v-model="form.pref_beta" :min="0.001" :max="2" :step="0.05" style="width: 100%;" />
              </el-tooltip>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="偏好损失">
              <el-select v-model="form.pref_loss" style="width: 100%;">
                <el-option label="Sigmoid（标准 DPO）" value="sigmoid" />
                <el-option label="Hinge" value="hinge" />
                <el-option label="IPO" value="ipo" />
                <el-option label="KTO Pair" value="kto_pair" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <el-button type="primary" @click="generateYaml" :disabled="!canGenerate">
            <el-icon><Document /></el-icon> 生成 YAML 配置
          </el-button>
          <span style="font-size: 12px; color: #999; margin-left: 8px;">
            填写完上面选项后点击生成
          </span>
        </el-form-item>

        <el-form-item label="YAML 预览" v-if="form.yaml_config">
          <el-input
            v-model="form.yaml_config"
            type="textarea"
            :rows="16"
            style="font-family: Courier New, monospace; font-size: 13px;"
          />
          <div style="font-size: 12px; color: #999; margin-top: 4px;">可在此手动微调生成的配置</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">创建并启动</el-button>
      </template>
    </el-dialog>

    <!-- 编辑对话框 -->
    <el-dialog v-model="showEdit" title="编辑 YAML 配置" width="800px">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="任务名称" required>
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="YAML 配置" required>
          <el-input
            v-model="editForm.yaml_config"
            type="textarea"
            :rows="20"
            style="font-family: Courier New, monospace; font-size: 13px;"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" @click="handleUpdate" :loading="updating">保存修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue"
import { finetuneApi, datasetApi } from "../api"
import { ElMessage } from "element-plus"
import ServerPathPicker from "../components/ServerPathPicker.vue"

const tasks = ref<any[]>([])
const loading = ref(false)
const showCreate = ref(false)
const creating = ref(false)
const showEdit = ref(false)
const updating = ref(false)
const editingTaskId = ref(0)
const availableDatasets = ref<any[]>([])

const form = ref({
  name: "",
  stage: "sft",
  dataset_id: 0,
  model_name_or_path: "",
  template: "qwen2.5",
  lora_target: ["q_proj", "v_proj"] as string[],
  output_dir: "",
  pref_beta: 0.1,
  pref_loss: "sigmoid",
  yaml_config: "",
})

const editForm = ref({ name: "", yaml_config: "", yaml_file: "" })

const canGenerate = computed(() => {
  const f = form.value
  return f.model_name_or_path && f.template && f.lora_target.length > 0
})

onMounted(async () => {
  await loadTasks()
  await loadDatasets()
})

async function loadTasks() {
  loading.value = true
  try {
    const res = await finetuneApi.list()
    tasks.value = res.data.data || []
  } catch { ElMessage.error("加载失败") }
  finally { loading.value = false }
}

async function loadDatasets() {
  try {
    const res = await datasetApi.getForFinetune()
    availableDatasets.value = res.data.data || []
  } catch { /* ignore */ }
}

function generateYaml() {
  const f = form.value
  const datasetName = f.dataset_id ? "dataset_" + f.dataset_id : "your_dataset"
  const ds = f.dataset_id ? availableDatasets.value.find((d: any) => d.id === f.dataset_id) : null
  // use dataset_dir instead of dataset_info
  const datasetInfoPath = ds ? ds.dataset_info_json : "./data/dataset_info.json"
  const datasetDir = datasetInfoPath ? datasetInfoPath.replace(/[\\/]dataset_info\.json$/i, "") : "./data"
  const outputDir = f.output_dir || "saves/finetune_models/" + (f.name || "ft_output")

  const yaml = [
    "### 模型与模板",
    "model_name_or_path: " + f.model_name_or_path,
    "template: " + f.template,
    "finetuning_type: lora",
    "lora_target: " + f.lora_target.join(","),
    "lora_rank: 32",
    "lora_alpha: 32",
    "",
    "### 数据",
    "dataset: " + datasetName,
    "dataset_dir: " + datasetDir,
    "cutoff_len: 2048",
    "overwrite_cache: true",
    "",
    "### 训练",
    "stage: " + f.stage,
    "do_train: true",
    ...(f.stage === "dpo" ? ["pref_beta: " + f.pref_beta, "pref_loss: " + f.pref_loss] : []),
    "output_dir: " + outputDir,
    "logging_steps: 10",
    "save_steps: 500",
    "plot_loss: true",
    "overwrite_output_dir: true",
    "gradient_checkpointing: true",
    "",
    "per_device_train_batch_size: 1",
    "gradient_accumulation_steps: 8",
    "learning_rate: " + (f.stage === "dpo" ? "0.000005" : "0.00002"),
    "num_train_epochs: 3.0",
    "lr_scheduler_type: cosine",
    "warmup_ratio: 0.1",
    "",
    "bf16: true",
    ...(f.stage === "sft" ? ["", "val_size: 0.1", "per_device_eval_batch_size: 1", "eval_strategy: steps", "eval_steps: 500"] : []),
  ].join("\n")

  form.value.yaml_config = yaml
}

async function handleEdit(row: any) {
  editingTaskId.value = row.id
  try {
    const res = await finetuneApi.get(row.id)
    const task = res.data.data
    editForm.value = {
      name: task.name,
      yaml_config: task.yaml_config,
      yaml_file: task.yaml_file || ""
    }
    showEdit.value = true
  } catch {
    ElMessage.error("加载任务详情失败")
  }
}

async function handleUpdate() {
  if (!editForm.value.yaml_config) {
    ElMessage.warning("YAML 配置不能为空")
    return
  }
  updating.value = true
  try {
    await finetuneApi.update(editingTaskId.value, { ...editForm.value })
    ElMessage.success("配置已更新")
    showEdit.value = false
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "更新失败")
  } finally { updating.value = false }
}

async function handleCreate() {
  if (!form.value.name || !form.value.yaml_config) {
    ElMessage.warning("请先填写选项并点击「生成 YAML 配置」")
    return
  }
  creating.value = true
  try {
    const selectedDataset = form.value.dataset_id ? availableDatasets.value.find((d: any) => d.id === form.value.dataset_id) : null
    if (selectedDataset && (selectedDataset.training_stage || 'sft') !== form.value.stage) {
      ElMessage.warning(`请选择 ${form.value.stage.toUpperCase()} 类型的数据集`)
      return
    }
    const res = await finetuneApi.create({ name: form.value.name, yaml_config: form.value.yaml_config })
    const taskId = res.data.data?.id
    if (taskId) await finetuneApi.start(taskId)
    ElMessage.success("创建成功")
    showCreate.value = false
    form.value = { name: "", stage: "sft", dataset_id: 0, model_name_or_path: "", template: "qwen2.5", lora_target: ["q_proj", "v_proj"], output_dir: "", pref_beta: 0.1, pref_loss: "sigmoid", yaml_config: "" }
    await loadTasks()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "创建失败")
  } finally { creating.value = false }
}

function handleStageChange() {
  form.value.dataset_id = 0
  form.value.yaml_config = ""
}

async function handleStart(row: any) {
  try {
    await finetuneApi.start(row.id)
    ElMessage.success("已启动")
    await loadTasks()
  } catch { ElMessage.error("启动失败") }
}

async function handleDelete(id: number) {
  try {
    await finetuneApi.delete(id)
    ElMessage.success("已删除")
    await loadTasks()
  } catch { ElMessage.error("删除失败") }
}

function statusType(s: string) {
  const map: Record<string, string> = { pending: "info", running: "warning", completed: "success", failed: "danger", stopped: "info" }
  return map[s] || "info"
}

function statusLabel(s: string) {
  const map: Record<string, string> = { pending: "待启动", running: "运行中", completed: "已完成", failed: "失败", stopped: "已停止" }
  return map[s] || s
}

function formatTime(t: string) {
  if (!t) return ""
  return new Date(t).toLocaleString("zh-CN")
}
</script>

<style scoped>
.path-input-row { display: flex; align-items: center; width: 100%; }
.path-input-row .el-input { flex: 1; }
</style>
