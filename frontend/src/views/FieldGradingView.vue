<template>
  <section class="page field-grading-page" data-testid="field-grading-page">
    <header class="page-head">
      <div>
        <h2>字段分级编辑器</h2>
        <p class="page-desc">
          审核员在这里提交父级资源与逐字段的继承/例外选择；字段分级表由服务端计算，页面不做业务换算。
        </p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/classify_tag">返回分级分类</RouterLink>
      </div>
    </header>

    <div class="filter-bar">
      <label class="filter-item">
        <span>数据资源</span>
        <select v-model.number="selectedId" data-testid="resource-select" @change="reload">
          <option v-for="item in resources" :key="item.资源编号" :value="item.资源编号">
            {{ item.数据资源 }}（{{ item.安全等级 }}）
          </option>
        </select>
      </label>
      <label v-if="overview" class="filter-item">
        <span>父级资源等级</span>
        <select v-model="targetLevel" data-testid="level-select">
          <option v-for="level in overview.等级选项" :key="level" :value="level">{{ level }}</option>
        </select>
      </label>
      <button v-if="overview" class="btn primary" data-testid="save-level" type="button" @click="saveLevel">
        提交父级等级
      </button>
      <span v-if="overview" class="level-current" data-testid="current-level">
        当前资源等级：{{ overview.资源等级 }}
      </span>
    </div>

    <p v-if="message" class="action-message" data-testid="grading-message">{{ message }}</p>
    <p v-if="errorMessage" class="error-text" data-testid="grading-error">{{ errorMessage }}</p>

    <div v-if="overview" class="grading-layout">
      <article class="panel">
        <header class="panel-head">
          <h3>逐字段确认继承 / 例外</h3>
          <span class="panel-note">字段目录来自服务端登记结果</span>
        </header>
        <p v-if="!overview.字段目录.length" class="empty-state" data-testid="no-catalog">
          该资源还没有登记字段目录，无法逐字段确认。
        </p>
        <table v-else class="data-table" data-testid="field-catalog">
          <thead>
            <tr>
              <th>序号</th><th>字段</th><th>说明</th><th>确认方式</th><th>例外等级</th><th>实际保护能力</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="field in overview.字段目录" :key="field.字段名" :data-testid="`field-row-${field.字段名}`">
              <td>{{ field.字段序号 }}</td>
              <td>
                {{ field.字段名 }}
                <small class="muted-block">{{ field.敏感标签 }}</small>
              </td>
              <td>{{ field.字段说明 }}</td>
              <td>
                <label class="mode-option">
                  <input
                    type="radio"
                    :name="`mode-${field.字段名}`"
                    value="继承"
                    :data-testid="`mode-inherit-${field.字段名}`"
                    v-model="choices[field.字段名].mode"
                  />
                  继承
                </label>
                <label class="mode-option">
                  <input
                    type="radio"
                    :name="`mode-${field.字段名}`"
                    value="例外"
                    :data-testid="`mode-exception-${field.字段名}`"
                    v-model="choices[field.字段名].mode"
                  />
                  例外
                </label>
              </td>
              <td>
                <select
                  v-model="choices[field.字段名].exceptionLevel"
                  :disabled="choices[field.字段名].mode !== '例外'"
                  :data-testid="`exception-level-${field.字段名}`"
                >
                  <option value="">—</option>
                  <option v-for="level in overview.等级选项" :key="level" :value="level">{{ level }}</option>
                </select>
              </td>
              <td>
                <select
                  v-model="choices[field.字段名].protection"
                  :disabled="choices[field.字段名].mode !== '例外'"
                  :data-testid="`exception-protection-${field.字段名}`"
                >
                  <option value="">—</option>
                  <option v-for="level in overview.等级选项" :key="level" :value="level">{{ level }}</option>
                </select>
                <label class="mode-option approve-option">
                  <input type="checkbox" v-model="choices[field.字段名].approved" />
                  已批准
                </label>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="overview.字段目录.length" class="panel-actions">
          <button class="btn primary" data-testid="submit-draft" type="button" :disabled="busy" @click="submitDraft">
            提交字段分级草稿
          </button>
        </div>
      </article>

      <article class="panel">
        <header class="panel-head">
          <h3>服务端计算的字段分级表</h3>
          <span class="panel-note">继承字段随父级资源等级变化，例外字段保留例外等级</span>
        </header>
        <table class="data-table" data-testid="grading-table">
          <thead>
            <tr>
              <th>序号</th><th>字段</th><th>确认方式</th><th>有效分级</th><th>分级依据</th><th>冲突说明</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in overview.字段分级表"
              :key="row.字段名"
              :data-testid="`grading-row-${row.字段名}`"
              :data-effective="row.有效分级"
              :data-conflict="row.冲突说明 ? 'yes' : 'no'"
            >
              <td>{{ row.字段序号 }}</td>
              <td>{{ row.字段名 }}</td>
              <td>{{ row.确认方式 }}/{{ row.确认状态 }}</td>
              <td>{{ row.有效分级 }}</td>
              <td>{{ row.分级依据 }}</td>
              <td :class="{ 'conflict-text': row.冲突说明 }">{{ row.冲突说明 || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </article>

      <article class="panel">
        <header class="panel-head">
          <h3>规则分组：哪组规则仍可启用</h3>
          <span class="panel-note">规则保护能力必须不低于字段有效分级</span>
        </header>
        <p class="rule-summary" data-testid="eligible-summary">
          可启用：{{ overview.可启用规则.join('、') || '无' }}；不可启用：{{ overview.不可启用规则.join('、') || '无' }}
        </p>
        <div v-for="group in overview.规则分组.groups" :key="group.字段名" class="rule-group" :data-testid="`rule-group-${group.字段名}`">
          <h4>{{ group.字段名 }}（有效分级 {{ group.有效分级 }}）</h4>
          <p v-if="group.冲突说明" class="conflict-text">{{ group.冲突说明 }}</p>
          <ul class="rule-list">
            <li v-for="rule in group.规则" :key="rule.规则编号" :class="rule.资格 === '可启用' ? 'eligible' : 'rejected'">
              <strong>{{ rule.规则编号 }}</strong> 保护至 {{ rule.保护等级 }} ·
              <span :data-testid="`rule-eligibility-${rule.规则编号}`">{{ rule.资格 }}</span>
              <span v-if="rule.原因.length" class="reason-text">（{{ rule.原因.join('；') }}）</span>
            </li>
            <li v-if="!group.规则.length" class="muted-block">暂无绑定该字段的规则</li>
          </ul>
        </div>
      </article>

      <article class="panel">
        <header class="panel-head">
          <h3>字段分级草稿与逐字段确认</h3>
          <span class="panel-note">资源升等后，旧草稿需按当前等级复核</span>
        </header>
        <p v-if="!overview.草稿.length" class="empty-state">暂无草稿</p>
        <div v-for="draft in overview.草稿" :key="draft.id" class="draft-card" :data-testid="`draft-${draft.id}`" :data-status="draft.状态">
          <header class="draft-head">
            <strong>{{ draft.草稿编号 }}</strong>
            <span class="draft-status">{{ draft.状态 }}</span>
            <span class="muted-block">提交时 {{ draft.提交时资源等级 }} · {{ draft.提交人 }}</span>
          </header>
          <p v-if="draft.失效原因" class="conflict-text">{{ draft.失效原因 }}</p>
          <ul class="draft-fields">
            <li v-for="item in draft.字段" :key="item.字段名">
              {{ item.字段名 }}：{{ item.确认方式 }}
              <span v-if="item.确认方式 === '例外'">
                （例外 {{ item.例外等级 }} / 实际 {{ item.实际保护能力 }} / {{ item.批准状态 }}）
              </span>
              <span class="draft-field-state">
                {{ item.确认状态 }}<span v-if="item.确认时资源等级 && item.确认时资源等级 !== '—'">（确认时 {{ item.确认时资源等级 }}）</span>
              </span>
              <button
                v-if="item.确认状态 !== '已确认'"
                class="link"
                type="button"
                :data-testid="`confirm-draft-${draft.id}-${item.字段名}`"
                @click="confirmField(draft.id, item.字段名)"
              >
                确认该字段
              </button>
            </li>
          </ul>
        </div>
      </article>
    </div>

    <p v-if="!overview && !errorMessage" class="empty-state">字段分级数据加载中…</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import {
  confirmFieldDraft,
  listGradingResources,
  loadResourceOverview,
  setResourceLevel,
  submitFieldDraft,
} from '@/api/backend-service'
import type { ResourceOverview, ResourceSummary, DraftSubmitItem } from '@/data/field-grading'

const resources = ref<ResourceSummary[]>([])
const route = useRoute()
const selectedId = ref<number>(0)
const overview = ref<ResourceOverview | null>(null)
const targetLevel = ref('L2')
const message = ref('')
const errorMessage = ref('')
const busy = ref(false)
type Choice = { mode: '继承' | '例外'; exceptionLevel: string; protection: string; approved: boolean }
const choices = reactive<Record<string, Choice>>({})

function seedChoices(data: ResourceOverview) {
  for (const field of data.字段目录) {
    const row = data.字段分级表.find((item) => item.字段名 === field.字段名)
    const mode = row?.确认方式 === '例外' ? '例外' : '继承'
    choices[field.字段名] = {
      mode,
      exceptionLevel: row?.例外?.例外等级 !== '—' ? String(row?.例外?.例外等级 ?? '') : '',
      protection: row?.例外?.实际保护能力 !== '—' ? String(row?.例外?.实际保护能力 ?? '') : '',
      approved: true,
    }
  }
}

async function reload() {
  if (!selectedId.value) return
  errorMessage.value = ''
  try {
    overview.value = await loadResourceOverview(selectedId.value)
    targetLevel.value = overview.value.资源等级
    seedChoices(overview.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '字段分级表读取失败'
  }
}

async function saveLevel() {
  if (!overview.value) return
  busy.value = true
  errorMessage.value = ''
  message.value = ''
  try {
    const result = await setResourceLevel(overview.value.资源.编号, targetLevel.value, '数据安全审核员', '字段分级编辑器提交')
    message.value = result.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '等级提交失败'
  } finally {
    busy.value = false
  }
}

async function submitDraft() {
  if (!overview.value) return
  busy.value = true
  errorMessage.value = ''
  message.value = ''
  try {
    const fields: DraftSubmitItem[] = overview.value.字段目录.map((field) => {
      const choice = choices[field.字段名]
      const item: DraftSubmitItem = { 字段名: field.字段名, 确认方式: choice.mode }
      if (choice.mode === '例外') {
        item.例外等级 = choice.exceptionLevel
        item.实际保护能力 = choice.protection
        item.批准 = choice.approved
      }
      return item
    })
    const result = await submitFieldDraft(overview.value.资源.编号, fields, '数据安全审核员', '逐字段确认')
    if (!result.ok) throw new Error(result.message)
    message.value = result.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '草稿提交失败'
  } finally {
    busy.value = false
  }
}

async function confirmField(draftId: number, field: string) {
  errorMessage.value = ''
  message.value = ''
  try {
    const result = await confirmFieldDraft(draftId, field, '数据安全审核员')
    if (!result.ok) throw new Error(result.message)
    message.value = result.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '字段确认失败'
  }
}

onMounted(async () => {
  try {
    resources.value = await listGradingResources()
    const requested = Number(route.query.resource ?? 0)
    const byQuery = resources.value.find((item) => item.资源编号 === requested)
    const withFields = resources.value
      .filter((item) => item.字段数 > 0)
      .sort((a, b) => b.资源编号 - a.资源编号)
    const preferred = byQuery ?? withFields[0] ?? resources.value[0]
    selectedId.value = preferred?.资源编号 ?? 0
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '资源列表读取失败'
  }
})
</script>
