import { createRouter, createWebHistory } from 'vue-router'

import Overview from '@/views/Overview.vue'
import WorkbenchView from '@/views/WorkbenchView.vue'
import FieldGradingView from '@/views/FieldGradingView.vue'
import MaskRuleDetailView from '@/views/MaskRuleDetailView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: Overview },
    // 固定路径必须排在 /:moduleKey 之前，否则会被模块工作台抢先匹配。
    { path: '/field_grading', name: 'field-grading', component: FieldGradingView },
    { path: '/mask_rule/:ruleId', name: 'mask-rule-detail', component: MaskRuleDetailView, props: true },
    { path: '/:moduleKey', name: 'module', component: WorkbenchView, props: true },
  ],
})

export default router
