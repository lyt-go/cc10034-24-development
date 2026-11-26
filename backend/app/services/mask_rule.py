"""脱敏规则领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。

在通用骨架之上补充了「能否启用」的判定：规则必须绑定数据资源，并且
实际保护能力不低于目标字段的服务端计算结果。启用成功时写一份不可变
的字段分级快照回执。
"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.services import field_grading
from app.store import store


class MaskRuleService(BaseModuleService):
    MODULE = "mask_rule"
    ENTITY = "脱敏规则"
    OPERATION_TERM = "校验"
    LIST_FIELDS = [
        "规则编号", "目标字段", "脱敏算法", "保留位数", "掩码字符",
        "规则版本", "适用场景", "生效时间", "关联资源", "保护等级",
    ]
    REQUIRED_FIELDS = ["规则编号", "目标字段", "脱敏算法"]
    STATUS_ORDER = ["草稿", "待验证", "已生效", "已废弃"]
    ACTION_RULES = {"提交验证": "待验证", "标记生效": "已生效", "标记废弃": "已废弃"}
    NEGATIVE_ACTIONS = []

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        entry, missing = super().create_entry(values)
        if entry is None:
            return entry, missing
        resource_id = values.get("关联资源编号")
        if resource_id in (None, "") and str(values.get("关联资源") or "").strip():
            # 工作台按「关联资源」名称登记时，服务端解析成资源编号。
            named = next(
                (row for row in store.rows("classify_tag")
                 if str(row.get("数据资源", "")).strip() == str(values.get("关联资源")).strip()),
                None,
            )
            if named is None:
                return None, [f"未找到名为「{values.get('关联资源')}」的数据资源"]
            resource_id = named.get("id")
        if resource_id not in (None, ""):
            try:
                resource_id = int(resource_id)
            except (TypeError, ValueError):
                return None, ["关联资源编号必须是数字"]
            row = store.find("classify_tag", resource_id)
            if row is None:
                return None, [f"数据资源 {resource_id} 不存在或已归档"]
            entry["关联资源编号"] = resource_id
            entry.setdefault("关联资源", row.get("数据资源"))
        entry.setdefault("保护等级", values.get("保护等级") or "L2")
        return entry, []

    def detail(self, entry_id: int) -> dict[str, Any] | None:
        return field_grading.rule_detail(entry_id)

    def eligibility(self, entry_id: int) -> dict[str, Any] | None:
        rule = self.get_entry(entry_id)
        if rule is None:
            return None
        return field_grading.eligibility_for_rule(rule)

    def try_enable(self, entry_id: int) -> dict[str, Any]:
        return field_grading.try_enable(entry_id)

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        # 标记生效走字段分级判定；其余动作仍按状态流转表处理。
        if action == "标记生效":
            result = field_grading.try_enable(entry_id)
            return (result.get("规则"), result.get("message", "")) if result.get("ok") else (None, result.get("message", ""))
        return super().run_action(entry_id, action)

    def receipts(self, entry_id: int) -> list[dict[str, Any]]:
        return field_grading.receipts_for(entry_id)
