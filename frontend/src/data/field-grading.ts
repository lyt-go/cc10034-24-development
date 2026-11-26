/** 字段分级编辑器与脱敏规则详情的公共类型。 */

import type { EntryRow } from './types'

export type Level = 'L1' | 'L2' | 'L3' | 'L4'

export type ExceptionIndex = {
  例外编号: string
  例外等级: string
  实际保护能力: string
  批准状态: string
  批准人: string
  批准时间?: string
}

export type GradingRow = {
  字段序号: string
  字段名: string
  字段说明: string
  资源等级: string
  确认方式: string
  确认状态: string
  确认草稿: string | null
  确认时资源等级: string | null
  例外: ExceptionIndex
  待批准例外: ExceptionIndex | null
  例外可用: boolean
  有效分级: string
  分级依据: string
  冲突说明: string
  来源: string
  更新时间: string
}

export type FieldCatalogRow = {
  id: number
  资源编号: number
  字段序号: string
  字段名: string
  字段说明: string
  敏感标签: string
}

export type DraftItem = {
  字段名: string
  确认方式: string
  例外等级: string
  实际保护能力: string
  批准?: boolean
  批准状态: string
  确认状态: string
  确认时间: string
  确认时资源等级: string
}

export type Draft = {
  id: number
  草稿编号: string
  资源编号: number
  提交时资源等级: string
  提交人: string
  提交时间: string
  状态: string
  确认时间: string
  确认时资源等级: string
  备注: string
  字段: DraftItem[]
  失效原因?: string
}

export type RuleEligibility = {
  规则id: number
  规则编号: string
  目标字段: string
  保护等级: string
  关联资源: string
  资源等级: string
  字段有效分级: string
  分级依据: string
  冲突说明: string
  资格: string
  原因: string[]
  提示?: string[]
}

export type RuleGroup = {
  字段序号: string
  字段名: string
  有效分级: string
  分级依据: string
  冲突说明: string
  规则: RuleEligibility[]
}

export type RuleGroups = {
  groups: RuleGroup[]
  eligible_rules: string[]
  rejected_rules: string[]
}

export type ResourceOverview = {
  资源: {
    编号: number
    标签编号: string
    数据资源: string
    安全等级: string
    状态: string
    数据类型: string
    合规要求: string
    脱敏要求: string
    标签时间: string
  }
  资源等级: string
  等级选项: string[]
  字段目录: FieldCatalogRow[]
  字段分级表: GradingRow[]
  例外: Array<Record<string, string>>
  草稿: Draft[]
  存在旧草稿: boolean
  冲突: { 字段名: string; 有效分级: string; 冲突说明: string }[]
  规则分组: RuleGroups
  可启用规则: string[]
  不可启用规则: string[]
}

export type ResourceSummary = {
  资源编号: number
  标签编号: string
  数据资源: string
  安全等级: string
  状态: string
  字段数: number
  字段分级: { 字段名: string; 有效分级: string; 确认方式: string; 冲突说明: string }[]
  可启用规则: string[]
  不可启用规则: string[]
  待确认草稿: number
}

export type RuleReceipt = {
  回执编号: string
  规则编号: string
  生效时间: string
  操作人: string
  资源等级: string
  字段名称: string
  字段有效分级: string
  分级依据: string
  保护等级: string
  判定: string
  字段分级快照: {
    资源编号: number
    资源等级: string
    字段分级: { 字段序号: string; 字段名: string; 有效分级: string; 分级依据: string; 冲突说明: string }[]
  }
}

export type RuleDetail = {
  规则: EntryRow
  资源: ResourceOverview['资源'] | null
  资源等级: string
  字段分级: GradingRow | null
  字段分级表: GradingRow[]
  保护等级: string
  资格: string
  原因: string[]
  提示: string[]
  冲突说明: string
  资格明细: RuleEligibility
  回执: RuleReceipt[]
  当前快照: { 资源编号: number; 资源等级: string; 字段分级: RuleReceipt['字段分级快照']['字段分级'] } | null
  规则分组: RuleGroups
}

export type DraftSubmitItem = {
  字段名: string
  确认方式: '继承' | '例外'
  例外等级?: string
  实际保护能力?: string
  批准?: boolean
  说明?: string
}

export type DraftResult = {
  ok: boolean
  message: string
  draft?: Draft
  field_table?: GradingRow[]
  rule_groups?: RuleGroups
}

export type EnableResult = {
  ok: boolean
  message: string
  回执?: RuleReceipt
  资格明细?: RuleEligibility
}
