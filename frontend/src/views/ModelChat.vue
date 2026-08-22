<template>
  <div v-loading="sending">
    <el-button @click="$router.push('/model')" style="margin-bottom: 16px;">
      <el-icon><ArrowLeft /></el-icon> 返回模型服务列表
    </el-button>

    <el-card v-if="service" shadow="never">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span><strong>{{ service.name }}</strong> - 对话测试</span>
          <el-tag :type="service.status === 'running' ? 'success' : 'danger'" size="small">
            {{ service.status === 'running' ? '运行中' : '已停止' }}
          </el-tag>
        </div>
      </template>

      <div v-if="service.status !== 'running'" style="text-align: center; padding: 40px; color: #999;">
        模型服务未运行，请先启动服务
      </div>

      <template v-else>
        <div style="display: flex; flex-direction: column; gap: 12px; margin-bottom: 16px;">
          <el-input v-model="inputText" type="textarea" :rows="3" placeholder="输入文本（留空则只传图片）" />
          <div style="display: flex; gap: 12px; align-items: center;">
            <el-input v-model="imagePath" placeholder="图片路径（可选）" style="flex: 1;" />
            <ServerPathPicker v-model="imagePath" mode="image" button-text="选择 Linux 图片" title="选择服务器图片" />
            <el-button type="primary" @click="sendMessage" :loading="sending">发送</el-button>
            <el-button @click="clearChat">清空</el-button>
          </div>
          <div v-if="imagePath" style="text-align: center;">
            <el-image :src="getFileUrl(imagePath)" style="max-width: 320px; max-height: 240px; border-radius: 6px;" fit="contain" :preview-src-list="[getFileUrl(imagePath)]" />
            <div style="font-size: 12px; color: #999; margin-top: 4px;">{{ imagePath }}</div>
          </div>
        </div>

        <div ref="chatRef" style="max-height: 500px; overflow-y: auto; border: 1px solid #eee; border-radius: 6px; padding: 16px; background: #fafafa;">
          <div v-for="(msg, idx) in messages" :key="idx" style="margin-bottom: 16px;">
            <div v-if="msg.role === 'user'" style="text-align: right; margin-bottom: 4px;">
              <div style="display: inline-block; background: #409eff; color: #fff; padding: 8px 14px; border-radius: 12px 12px 4px 12px; max-width: 80%; text-align: left; font-size: 13px; white-space: pre-wrap;">
                <div v-if="msg.image" style="margin-bottom: 4px;"><el-image :src="getFileUrl(msg.image)" style="max-width: 200px; border-radius: 4px;" fit="contain" /></div>
                {{ msg.text || "(仅图片)" }}
              </div>
            </div>
            <div v-else style="text-align: left;">
              <div style="display: inline-block; background: #fff; border: 1px solid #e0e0e0; padding: 8px 14px; border-radius: 12px 12px 12px 4px; max-width: 80%; text-align: left; font-size: 13px; white-space: pre-wrap;">{{ msg.text || "(无响应)" }}</div>
            </div>
          </div>
          <div v-if="messages.length === 0" style="text-align: center; color: #ccc; padding: 40px;">输入文本和图片后点击发送</div>
        </div>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from "vue"
import { useRoute } from "vue-router"
import { modelApi } from "../api"
import { ElMessage } from "element-plus"
import ServerPathPicker from "../components/ServerPathPicker.vue"

const route = useRoute()
const serviceId = Number(route.params.id)
const service = ref<any>(null)
const inputText = ref("")
const imagePath = ref("")
const sending = ref(false)
const messages = ref<Array<{ role: string; text: string; image?: string }>>([])
const chatRef = ref<HTMLElement | null>(null)

onMounted(async () => {
  try { const res = await modelApi.get(serviceId); service.value = res.data.data }
  catch { ElMessage.error("加载服务信息失败") }
})

async function sendMessage() {
  if (!inputText.value && !imagePath.value) { ElMessage.warning("请输入文本或选择图片"); return }
  messages.value.push({ role: "user", text: inputText.value, image: imagePath.value })
  scrollChat()
  sending.value = true
  try {
    const res = await modelApi.chat(serviceId, inputText.value, imagePath.value)
    const data = res.data.data
    messages.value.push({ role: "assistant", text: data.output || "错误: " + (data.error || "无响应") })
  } catch (e: any) {
    messages.value.push({ role: "assistant", text: "请求失败: " + (e.response?.data?.detail || e.message) })
  } finally {
    sending.value = false; inputText.value = ""; imagePath.value = ""; scrollChat()
  }
}

function clearChat() { messages.value = []; inputText.value = ""; imagePath.value = "" }
function scrollChat() { nextTick(() => { if (chatRef.value) chatRef.value.scrollTop = chatRef.value.scrollHeight }) }

function getFileUrl(path: string): string { if (!path) return ""; return "/api/file?path=" + encodeURIComponent(String(path)) }
</script>
