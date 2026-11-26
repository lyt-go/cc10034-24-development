<template>
  <section v-if="detail" class="page rule-detail-page" data-testid="rule-detail-page">
    <header class="page-head">
      <div>
        <h2>脱敏规则详情 · {{ detail.规则.规则编号 }}</h2>
        <p class="page-desc">
          启用资格由服务端按字段分级表计算；已生效规则的历史回执保留当时所据的字段分级。
        </p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" :to="`/mask_rule`">返回脱敏规则</RouterLink>
        <RouterLink v-if="detail.资源" class="btn" :to="`/field_grading?resource=${detail.资源.编号}`">
          打开字段分级编辑器
        </RouterLink>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">规则状态</span>
        <strong class="stat-value" data-testid="rule-status">{{ detail.规则.status }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">父级资源等级</span>
        <strong class="stat-value" data-testid="resource-level">{{ detail.资源等级 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">目标字段有效分级</span>
        <strong class="stat-value" data-testid="field-effective">
          {{ detail.字段分级?.有效分级 ?? '未登记' }}
        </strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">规则保护能力</span>
        <strong class="stat-value" data-testid="rule-protection">{{ detail.保护等级 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">启用资格</span>
        <strong class="stat-value" :class="eligible ? 'ok-text' : 'error-text'" data-testid="rule-eligibility">
          {{ detail.资格 }}
        </strong>
      </article>
    </div>

    <article class="panel">
      <header class="panel-head">
        <h3>字段分级依据</h3>
        <span class="panel-note">
          {{ detail.资源?.数据资源 ?? '未绑定资源' }} · {{ detail.规则.目标字段 }} ·
          {{ detail.字段分级?.确认方式 ?? '未确认' }} / {{ detail.字段分级?.确认状态 ?? '—' }}
        </span>
      </header>
      <dl class="dag-detail">
        <div><dt>分级依据</dt><dd data-testid="grading-basis">{{ detail.字段分级?.分级依据 ?? '—' }}</dd></div>
        <div><dt>已批准例外</dt><dd data-testid="exception-info">
          {{ detail.字段分级?.例外?.例外编号 ?? '—' }} /
          {{ detail.字段分级?.例外?.例外等级 ?? '—' }} /
          实际保护 {{ detail.字段分级?.例外?.实际保护能力 ?? '—' }} /
          {{ detail.字段分级?.例外?.批准状态 ?? '未登记' }}
        </dd></div>
        <div><dt>冲突说明</dt><dd :class="{ 'conflict-text': detail.冲突说明 }" data-testid="conflict-note">
          {{ detail.冲突说明 || '—' }}
        </dd></div>
        <div><dt>确认时资源等级</dt><dd>{{ detail.字段分级?.确认时资源等级 ?? '—' }}</dd></div>
      </dl>
      <ul v-if="detail.原因.length" class="reason-list" data-testid="rejection-reasons">
        <li v-for="(reason, index) in detail.原因" :key="index" class="conflict-text">{{ reason }}</li>
      </ul>
      <ul v-if="!detail.原因.length && detail.提示.length" class="warning-list" data-testid="warning-notes">
        <li v-for="(note, index) in detail.提示" :key="index">{{ note }}</li>
      </ul>
      <div class="panel-actions">
        <button class="btn primary" data-testid="try-enable-rule" type="button" :disabled="busy" @click="tryEnable">
          实际尝试启用
        </button>
        <span v-if="enableResult" class="action-message" :class="enableResult.ok ? 'ok-text' : 'error-text'" data-testid="enable-result">
          {{ enableResult.message }}
        </span>
      </div>
    </article>

    <article class="panel">
      <header class="panel-head">
        <h3>规则分组：哪组规则仍可启用</h3>
        <span class="panel-note">
          可启用：{{ detail.规则分组.eligible_rules.join('、') || '无' }} ·
          不可启用：{{ detail.规则分组.rejected_rules.join('、') || '无' }}
        </span>
      </header>
      <div v-for="group in detail.规则分组.groups" :key="group.字段名" class="rule-group" :data-testid="`detail-group-${group.字段名}`">
        <h4>{{ group.字段名 }}（{{ group.有效分级 }}）</h4>
        <p v-if="group.冲突说明" class="conflict-text">{{ group.冲突说明 }}</p>
        <ul class="rule-list">
          <li v-for="rule in group.规则" :key="rule.规则编号" :class="rule.资格 === '可启用' ? 'eligible' : 'rejected'">
            <strong>{{ rule.规则编号 }}</strong> 保护至 {{ rule.保护等级 }} ·
            <span :data-testid="`group-eligibility-${rule.规则编号}`">{{ rule.资格 }}</span>
            <span v-if="rule.原因.length" class="reason-text">{{ rule.原因.join('；') }}</span>
          </li>
        </ul>
      </div>
    </article>

    <article class="panel">
      <header class="panel-head">
        <h3>生效回执（字段分级快照）</h3>
        <span class="panel-note">回执记录生效当时的字段分级，资源之后升等不会改写旧回执</span>
      </header>
      <p v-if="!detail.回执.length" class="empty-state" data-testid="no-receipt">该规则还没有生效回执</p>
      <div v-for="receipt in detail.回执" :key="receipt.回执编号" class="receipt-card" :data-testid="`receipt-${receipt.回执编号}`">
        <header class="draft-head">
          <strong>{{ receipt.回执编号 }}</strong>
          <span>{{ receipt.生效时间 }} · {{ receipt.操作人 }}</span>
          <span class="muted-block">当时资源等级 {{ receipt.资源等级 }} · 字段 {{ receipt.字段有效分级 }}</span>
        </header>
        <table class="data-table">
          <thead><tr><th>字段序号</th><th>字段</th><th>当时有效分级</th><th>当时依据</th></tr></thead>
          <tbody>
            <tr v-for="item in receipt.字段分级快照.字段分级" :key="item.字段名">
              <td>{{ item.字段序号 }}</td>
              <td>{{ item.字段名 }}</td>
              <td>{{ item.有效分级 }}</td>
              <td>{{ item.分级依据 }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="detail.当前快照" class="current-snapshot" data-testid="current-snapshot">
        当前字段分级：{{ detail.当前快照.资源等级 }} ·
        <span v-for="item in detail.当前快照.字段分级" :key="item.字段名" class="snapshot-item">
          {{ item.字段名 }}={{ item.有效分级 }}
        </span>
      </div>
    </article>

    <p v-if="errorMessage" class="error-text" data-testid="rule-error">{{ errorMessage }}</p>
  </section>
  <section v-else class="page">
    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
    <p v-else class="empty-state">脱敏规则详情加载中…</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { enableRule, loadRuleDetail } from '@/api/backend-service'
import type { EnableResult, RuleDetail } from '@/data/field-grading'

const props = defineProps<{ moduleKey: string; ruleId: string }>()
const detail = ref<RuleDetail | null>(null)
const enableResult = ref<EnableResult | null>(null)
const errorMessage = ref('')
const busy = ref(false)
const eligible = computed(() => detail.value?.资格 === '可启用')

async function reload() {
  errorMessage.value = ''
  try {
    detail.value = await loadRuleDetail(Number(props.ruleId))
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '详情读取失败'
  }
}

async function tryEnable() {
  busy.value = true
  errorMessage.value = ''
  try {
    enableResult.value = await enableRule(Number(props.ruleId))
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '启用操作失败'
  } finally {
    busy.value = false
  }
}

onMounted(reload)
</script>
