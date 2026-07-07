import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1' })

export default api

// ====== 数据集 API ======
export const datasetApi = {
  list: () => api.get('/dataset/list'),
  get: (id: number) => api.get('/dataset/' + id),
  preview: (id: number, n = 5) => api.get('/dataset/' + id + '/preview?n=' + n),
  upload: (name: string, file: File, prefixPath = '') => {
    const fd = new FormData()
    fd.append('name', name)
    fd.append('prefix_path', prefixPath)
    fd.append('file', file)
    return api.post('/dataset/upload', fd)
  },
  split: (id: number, trainRatio = 0.8) => api.post('/dataset/' + id + '/split', { train_ratio: trainRatio }),
  delete: (id: number) => api.delete('/dataset/' + id),
  previewSplit: (id: number, split = "train", page = 1, pageSize = 50) => api.get("/dataset/" + id + "/preview-split", { params: { split, page, page_size: pageSize } }),
  updateRow: (id: number, split: string, rowIndex: number, updates: object) => api.put("/dataset/" + id + "/row", { split, row_index: rowIndex, updates }),
  deleteRow: (id: number, split: string, rowIndex: number) => api.delete("/dataset/" + id + "/row", { params: { split, row_index: rowIndex } }),
  getForFinetune: () => api.get('/dataset/for-finetune'),
  getForEval: () => api.get('/dataset/for-eval'),
}

// ====== 微调 API ======
export const finetuneApi = {
  list: () => api.get('/finetune/list'),
  get: (id: number) => api.get('/finetune/' + id),
  create: (data: { name: string; yaml_config: string; yaml_file?: string }) => api.post('/finetune/create', data),
  start: (id: number) => api.post('/finetune/' + id + '/start'),
  stop: (id: number) => api.post('/finetune/' + id + '/stop'),
  delete: (id: number) => api.delete('/finetune/' + id),
  getLogs: (id: number) => api.get('/finetune/' + id + '/logs'),
  getYamlTemplates: () => api.get('/finetune/yaml-templates'),
  update: (id: number, data: { name?: string; yaml_config?: string; yaml_file?: string }) => api.put('/finetune/' + id + '/yaml', data),
}

// ====== 评测 API ======
export const evalApi = {
  list: () => api.get('/eval/list'),
  get: (id: number) => api.get('/eval/' + id),
  create: (data: {
    name: string
    dataset_path: string
    model_name_or_path?: string
    adapter_path?: string
    template?: string
    api_port?: number
    model_service_id?: number
  }) => api.post('/eval/create', data),
  start: (id: number) => api.post('/eval/' + id + '/start'),
  stop: (id: number) => api.post('/eval/' + id + '/stop'),
  delete: (id: number) => api.delete('/eval/' + id),
  getResults: (id: number, page = 1, pageSize = 50) => api.get('/eval/' + id + '/results', { params: { page, page_size: pageSize } }),
  getMetrics: (id: number) => api.get('/eval/' + id + '/metrics'),
  update: (id: number, data: any) => api.put('/eval/' + id + '/update', data),
}


// ====== 模型服务 API ======
export const modelApi = {
  list: () => api.get('/model/list'),
  get: (id: number) => api.get('/model/' + id),
  create: (data: {
    name: string
    model_name_or_path: string
    adapter_path?: string
    template?: string
    port?: number
  }) => api.post('/model/create', data),
  start: (id: number, max_new_tokens = 2048) => api.post('/model/' + id + '/start', { max_new_tokens }),
  stop: (id: number) => api.post('/model/' + id + '/stop'),
  delete: (id: number) => api.delete('/model/' + id),
  getLogs: (id: number) => api.get('/model/' + id + '/logs'),
  chat: (modelServiceId: number, text: string, imagePath?: string) => api.post('/model/chat', {
    model_service_id: modelServiceId,
    text,
    image_path: imagePath || ''
  }),
  getRunning: () => api.get('/model/running'),
  update: (id: number, data: any) => api.put('/model/' + id + '/update', data),
}
