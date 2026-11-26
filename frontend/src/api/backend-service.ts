import { request } from './client'
import { moduleMeta } from '@/data/modules'
import type { ActionResult, EntryRow, OverviewResult, PageResult } from '@/data/types'
import type {
  DraftResult,
  EnableResult,
  ResourceOverview,
  ResourceSummary,
  RuleDetail,
} from '@/data/field-grading'

export { moduleMeta }

export async function listEntries(
  key: string,
  filters: Record<string, string> = {},
): Promise<PageResult> {
  const query = new URLSearchParams(filters).toString()
  const response = await request(`/api/${key}?${query}`)
  if (!response.ok) throw new Error('业务数据读取失败')
  return await response.json()
}

export async function createEntry(
  key: string,
  values: Record<string, string>,
): Promise<ActionResult> {
  const response = await request(`/api/${key}`, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  return await response.json()
}

export async function runAction(
  key: string,
  id: number,
  action: string,
): Promise<ActionResult> {
  const response = await request(`/api/${key}/${id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  })
  return await response.json()
}

export async function downloadEntries(
  key: string,
  filters: Record<string, string> = {},
): Promise<void> {
  const query = new URLSearchParams(filters).toString()
  const response = await request(`/api/${key}/export?${query}`)
  if (!response.ok) throw new Error('业务数据导出失败')
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${key}.csv`
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export async function loadOverview(): Promise<OverviewResult> {
  const response = await request('/api/overview')
  if (!response.ok) throw new Error('运营概览读取失败')
  return await response.json()
}

// ——————————— 字段分级编辑器 ———————————

export async function listGradingResources(): Promise<ResourceSummary[]> {
  const response = await request('/api/field-grading')
  if (!response.ok) throw new Error('字段分级资源读取失败')
  const payload = (await response.json()) as { items: ResourceSummary[] }
  return payload.items
}

export async function loadResourceOverview(resourceId: number): Promise<ResourceOverview> {
  const response = await request(`/api/field-grading/${resourceId}`)
  if (!response.ok) throw new Error('字段分级表读取失败')
  return (await response.json()) as ResourceOverview
}

export async function submitFieldDraft(
  resourceId: number,
  fields: import('@/data/field-grading').DraftSubmitItem[],
  operator = '数据安全审核员',
  remark = '',
): Promise<DraftResult> {
  const response = await request('/api/field-grading/drafts', {
    method: 'POST',
    body: JSON.stringify({ 资源编号: resourceId, 提交人: operator, 备注: remark, 字段: fields }),
  })
  return (await response.json()) as DraftResult
}

export async function confirmFieldDraft(
  draftId: number,
  field: string,
  operator = '数据安全审核员',
): Promise<DraftResult> {
  const response = await request('/api/field-grading/drafts/confirm', {
    method: 'POST',
    body: JSON.stringify({ 草稿编号: draftId, 字段名: field, 确认人: operator }),
  })
  return (await response.json()) as DraftResult
}

export async function setResourceLevel(
  resourceId: number,
  level: string,
  operator = '数据安全审核员',
  remark = '',
): Promise<DraftResult & { resource?: ResourceOverview['资源'] }> {
  const response = await request(`/api/field-grading/${resourceId}/level`, {
    method: 'POST',
    body: JSON.stringify({ 安全等级: level, 操作人: operator, 备注: remark }),
  })
  return (await response.json()) as DraftResult & { resource?: ResourceOverview['资源'] }
}

export async function loadRuleDetail(ruleId: number): Promise<RuleDetail> {
  const response = await request(`/api/mask-rule/${ruleId}/detail`)
  if (!response.ok) throw new Error('脱敏规则详情读取失败')
  return (await response.json()) as RuleDetail
}

export async function enableRule(ruleId: number): Promise<EnableResult> {
  const response = await request(`/api/mask-rule/${ruleId}/enable`, { method: 'POST' })
  if (!response.ok) throw new Error(`启用接口返回 ${response.status}`)
  return (await response.json()) as EnableResult
}
