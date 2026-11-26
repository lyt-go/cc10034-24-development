"""字段分级与规则启用判定测试。

覆盖：
- 字段例外只有在实际保护能力足够时才能用于启用规则；
- 资源升等到 L3 后，继承字段的规则被拒绝，例外字段的规则仍可启用；
- 交错确认旧草稿时记录确认时的资源等级；
- 已生效规则的回执保留生效当时的字段分级快照。
"""
from __future__ import annotations

import pytest

from app.services import field_grading
from app.store import store


RESOURCE = 4  # 员工档案库：初始 L2，甲字段有已批准的 L2 例外，乙字段继承


@pytest.fixture(autouse=True)
def _isolate_store():
    """每个用例前后都恢复种子数据，避免互相污染。"""
    store.reset()
    yield
    store.reset()


class TestGradingTable:
    def test_inherit_and_approved_exception(self):
        table = {row["字段名"]: row for row in field_grading.compute_grading_table(RESOURCE)}
        assert table["员工手机号"]["有效分级"] == "L2"
        assert table["员工手机号"]["来源"] == "exception"
        assert table["员工工号"]["有效分级"] == "L2"
        assert table["员工工号"]["来源"] == "inherit"
        assert table["员工工号"]["例外"]["批准状态"] == "未登记"

    def test_insufficient_exception_falls_back_to_inherit(self):
        """例外声明 L2 但实际保护能力只有 L1 时不能采用。"""
        table = {row["字段名"]: row for row in field_grading.compute_grading_table(2)}
        assert table["合同金额"]["例外可用"] is False
        assert table["合同金额"]["有效分级"] == "L3"  # 例外不可用，继承资源等级 L3
        assert "实际保护能力" in table["合同金额"]["冲突说明"]

    def test_parent_level_drives_inherited_fields(self):
        field_grading.raise_resource_level(RESOURCE, "L3", operator="审核员")
        table = {row["字段名"]: row for row in field_grading.compute_grading_table(RESOURCE)}
        assert table["员工工号"]["有效分级"] == "L3"
        assert table["员工手机号"]["有效分级"] == "L2"
        assert "资源已升等至 L3" in table["员工手机号"]["冲突说明"]


class TestRuleEligibility:
    def test_both_pending_rules_eligible_at_l2(self):
        groups = field_grading.rule_groups(RESOURCE)
        assert "MASK-0001" in groups["eligible_rules"]
        assert "MASK-0002" in groups["eligible_rules"]

    def test_after_escalation_only_exception_group_eligible(self):
        field_grading.raise_resource_level(RESOURCE, "L3", operator="审核员")
        groups = field_grading.rule_groups(RESOURCE)
        assert "MASK-0001" in groups["eligible_rules"]
        assert "MASK-0002" in groups["rejected_rules"]

    def test_rejection_reason_names_effective_grade(self):
        field_grading.raise_resource_level(RESOURCE, "L3", operator="审核员")
        result = field_grading.try_enable(2)
        assert result["ok"] is False
        assert "L3" in result["message"] and "L2" in result["message"]
        assert "员工工号" in result["message"]

    def test_enable_writes_receipt(self):
        result = field_grading.try_enable(1, operator="审核员")
        assert result["ok"] is True
        assert result["回执"]["回执编号"].startswith("RCPT-")
        assert result["回执"]["字段有效分级"] == "L2"
        detail = field_grading.rule_detail(1)
        assert len(detail["回执"]) == 1
        assert detail["规则"]["status"] == "已生效"

    def test_rejected_enable_does_not_change_status(self):
        field_grading.raise_resource_level(RESOURCE, "L3", operator="审核员")
        result = field_grading.try_enable(2)
        assert result["ok"] is False
        rule = store.find("mask_rule", 2)
        assert rule is not None and rule["status"] == "待验证"


class TestReceiptsAreHistoricalSnapshots:
    def test_historical_receipt_keeps_old_grading(self):
        detail = field_grading.rule_detail(3)
        receipt = detail["回执"][0]
        assert receipt["资源等级"] == "L2"
        assert receipt["字段有效分级"] == "L2"
        snapshot_levels = {
            item["字段名"]: item["有效分级"] for item in receipt["字段分级快照"]["字段分级"]
        }
        assert snapshot_levels == {"员工手机号": "L2", "员工工号": "L2"}

    def test_receipt_snapshot_survives_escalation(self):
        field_grading.raise_resource_level(RESOURCE, "L3", operator="审核员")
        receipt = field_grading.rule_detail(3)["回执"][0]
        assert receipt["资源等级"] == "L2"
        assert receipt["字段分级快照"]["资源等级"] == "L2"
        current = field_grading.rule_detail(3)["当前快照"]
        assert current["资源等级"] == "L3"


class TestEditorFlow:
    def test_submit_and_confirm_draft(self):
        draft, errors = field_grading.submit_draft(
            RESOURCE, [
                {"字段名": "员工手机号", "确认方式": "例外", "例外等级": "L2",
                 "实际保护能力": "L2", "批准": True},
                {"字段名": "员工工号", "确认方式": "继承"},
            ],
            operator="审核员",
        )
        assert draft is not None, errors
        assert draft["状态"] == "待确认"
        confirmed, message, _ = field_grading.confirm_draft_field(
            RESOURCE, draft["id"], "员工工号", operator="审核员",
        )
        assert confirmed is not None
        assert confirmed["状态"] == "部分确认"
        assert "L2" in message

    def test_unknown_field_rejected(self):
        draft, errors = field_grading.submit_draft(
            RESOURCE, [{"字段名": "身份证号", "确认方式": "继承"}], operator="审核员",
        )
        assert draft is None
        assert "不在资源字段目录" in errors[0]

    def test_interleaved_confirm_after_escalation_records_current_level(self):
        # 先提交一份旧草稿（提交时资源等级 L2）。
        draft, _ = field_grading.submit_draft(
            RESOURCE, [{"字段名": "员工手机号", "确认方式": "例外", "例外等级": "L2",
                        "实际保护能力": "L2", "批准": True}],
            operator="审核员",
        )
        assert draft is not None
        # 资源升等，未确认草稿被标记为旧草稿待复核。
        field_grading.raise_resource_level(RESOURCE, "L3", operator="审核员")
        touched = [item for item in field_grading.submissions_for(RESOURCE)
                   if item["id"] == draft["id"]][0]
        assert touched["状态"] == "旧草稿待复核"
        # 交错确认旧草稿：确认时记录 L3，而不是提交时的 L2。
        confirmed, message, _ = field_grading.confirm_draft_field(
            RESOURCE, draft["id"], "员工手机号", operator="审核员",
        )
        assert confirmed is not None
        item = confirmed["字段"][0]
        assert item["确认时资源等级"] == "L3"
        assert "旧草稿复核" in message
        # 已批准例外仍按 L2 判定，规则 MASK-0001 仍可启用。
        assert field_grading.rule_groups(RESOURCE)["eligible_rules"].count("MASK-0001") == 1

    def test_pending_exception_not_usable_until_approved(self):
        draft, _ = field_grading.submit_draft(
            RESOURCE, [{"字段名": "员工工号", "确认方式": "例外", "例外等级": "L3",
                        "实际保护能力": "L3", "批准": False}],
            operator="审核员",
        )
        assert draft is not None
        field_grading.confirm_draft_field(RESOURCE, draft["id"], "员工工号", operator="审核员")
        row = field_grading.grading_row(RESOURCE, "员工工号")
        assert row is not None
        assert row["例外可用"] is False
        assert row["有效分级"] == "L2"
