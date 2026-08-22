import { createRouter, createWebHistory } from 'vue-router'
import DatasetList from '../views/DatasetList.vue'
import DatasetDetail from '../views/DatasetDetail.vue'
import DatasetCreate from '../views/DatasetCreate.vue'
import FinetuneList from '../views/FinetuneList.vue'
import FinetuneDetail from '../views/FinetuneDetail.vue'
import EvalList from '../views/EvalList.vue'
import EvalDetail from '../views/EvalDetail.vue'
import ModelList from '../views/ModelList.vue'
import ModelChat from '../views/ModelChat.vue'

const routes = [
  { path: '/dataset', name: 'DatasetList', component: DatasetList },
  { path: '/dataset/create', name: 'DatasetCreate', component: DatasetCreate },
  { path: '/dataset/:id', name: 'DatasetDetail', component: DatasetDetail },
  { path: '/', redirect: '/dataset' },
  { path: '/finetune', name: 'FinetuneList', component: FinetuneList },
  { path: '/finetune/:id', name: 'FinetuneDetail', component: FinetuneDetail },
  { path: '/eval', name: 'EvalList', component: EvalList },
  { path: '/eval/:id', name: 'EvalDetail', component: EvalDetail },
  { path: '/model', name: 'ModelList', component: ModelList },
  { path: '/model/chat/:id', name: 'ModelChat', component: ModelChat },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
