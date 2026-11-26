"""字段分级与规则启用 API。

这些路径比通用 /{module}/{entry_id} 更具体，所以必须先注册。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import field_grading
from app.services import service_for

router = APIRouter(prefix="/api", tags=["字段分级"])


class FieldDraftItem(BaseModel):
    field: str = Field(alias="字段名")
    mode: str = Field(default="继承", alias="确认方式")
    exception_level: str | None = Field(default=None, alias="例外等级")
    protection: str | None = Field(default=None, alias="实际保护能力")
    approved: bool = Field(default=True, alias="批准")
    note: str | None = Field(default=None, alias="说明")

    model_config = {"populate_by_name": True}


class DraftPayload(BaseModel):
    resource_id: int = Field(alias="资源编号")
    operator: str = Field(default="数据安全审核员", alias="提交人")
    remark: str | None = Field(default=None, alias="备注")
    fields: list[FieldDraftItem] = Field(default_factory=list, alias="字段")

    model_config = {"populate_by_name": True}


class ConfirmPayload(BaseModel):
    draft_id: int = Field(alias="草稿编号")
    field: str | None = Field(default=None, alias="字段名")
    operator: str = Field(default="数据安全审核员", alias="确认人")

    model_config = {"populate_by_name": True}


class LevelPayload(BaseModel):
    level: str = Field(alias="安全等级")
    operator: str = Field(default="数据安全审核员", alias="操作人")
    remark: str | None = Field(default=None, alias="备注")

    model_config = {"populate_by_name": True}


def _resource_or_404(resource_id: int) -> dict[str, Any]:
    overview = field_grading.resource_overview(resource_id)
    if overview is None:
        raise HTTPException(status_code=404, detail=f"数据资源 {resource_id} 不存在或已归档")
    return overview


@router.get("/field-grading")
def list_resources() -> dict[str, Any]:
    """字段分级编辑器入口：列出可编辑资源及其当前等级。"""
    items = []
    for tag in field_grading.store.rows("classify_tag"):
        resource_id = int(tag.get("id", 0))
        overview = field_grading.resource_overview(resource_id) or {}
        items.append({
            "资源编号": resource_id,
            "标签编号": tag.get("标签编号"),
            "数据资源": tag.get("数据资源"),
            "安全等级": overview.get("资源等级", "未分级"),
            "状态": tag.get("status"),
            "字段数": len(overview.get("字段目录", [])),
            "字段分级": [
                {
                    "字段名": row["字段名"],
                    "有效分级": row["有效分级"],
                    "确认方式": row["确认方式"],
                    "冲突说明": row["冲突说明"],
                }
                for row in overview.get("字段分级表", [])
            ],
            "可启用规则": overview.get("可启用规则", []),
            "不可启用规则": overview.get("不可启用规则", []),
            "待确认草稿": sum(
                1 for draft in overview.get("草稿", [])
                if str(draft.get("状态")) in ("待确认", "部分确认", "旧草稿待复核")
            ),
        })
    return {"items": items, "total": len(items)}


@router.get("/field-grading/{resource_id}")
def get_resource(resource_id: int) -> dict[str, Any]:
    """服务端计算出的字段分级表、草稿、冲突和规则分组。"""
    return _resource_or_404(resource_id)


@router.post("/field-grading/drafts")
def submit_draft(payload: DraftPayload) -> dict[str, Any]:
    """审核员提交父级资源与逐字段继承/例外选择，服务端生成草稿。"""
    draft, errors = field_grading.submit_draft(
        payload.resource_id,
        [item.model_dump(by_alias=True) for item in payload.fields],
        operator=payload.operator,
        remark=payload.remark or "",
    )
    if draft is None:
        return {"ok": False, "message": "；".join(errors), "draft": None}
    overview = _resource_or_404(payload.resource_id)
    return {
        "ok": True,
        "message": f"草稿 {draft.get('草稿编号')} 已提交，待逐字段确认",
        "draft": draft,
        "field_table": overview["字段分级表"],
        "rule_groups": overview["规则分组"],
    }


@router.post("/field-grading/drafts/confirm")
def confirm_draft(payload: ConfirmPayload) -> dict[str, Any]:
    """逐字段确认草稿；确认时记录当前资源等级，用于识别交错确认的旧草稿。"""
    draft = field_grading._draft_row(payload.draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"字段分级草稿 {payload.draft_id} 不存在")
    resource_id = int(draft.get("资源编号", 0))
    confirmed, message, errors = field_grading.confirm_draft_field(
        resource_id, payload.draft_id, payload.field, operator=payload.operator,
    )
    if confirmed is None:
        return {"ok": False, "message": message or "；".join(errors), "draft": None}
    overview = _resource_or_404(resource_id)
    return {
        "ok": True,
        "message": message,
        "draft": confirmed,
        "field_table": overview["字段分级表"],
        "rule_groups": overview["规则分组"],
    }


@router.post("/field-grading/{resource_id}/level")
def raise_level(resource_id: int, payload: LevelPayload) -> dict[str, Any]:
    """资源升等/降等；未确认草稿会标记为旧草稿待复核。"""
    level = str(payload.level or "").strip().upper()
    if level not in field_grading.LEVELS:
        return {"ok": False, "message": "安全等级必须是 L1~L4", "resource": None}
    previous = field_grading.resource_level(resource_id)
    resource, touched = field_grading.raise_resource_level(
        resource_id, level, operator=payload.operator, remark=payload.remark or "",
    )
    if resource is None:
        raise HTTPException(status_code=404, detail=f"数据资源 {resource_id} 不存在或已归档")
    overview = _resource_or_404(resource_id)
    return {
        "ok": True,
        "message": (
            f"资源 {resource.get('数据资源')} 等级由 {previous} 调整为 {level}；"
            f"{len(touched)} 份未确认草稿标记为旧草稿待复核"
        ),
        "resource": field_grading.resource_brief(resource_id),
        "field_table": overview["字段分级表"],
        "rule_groups": overview["规则分组"],
        "invalidated_drafts": touched,
    }


@router.get("/mask-rule/{rule_id}/detail")
def mask_rule_detail(rule_id: int) -> dict[str, Any]:
    """脱敏规则详情：字段分级依据、资格、冲突提示和历史回执。"""
    detail = field_grading.rule_detail(rule_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"脱敏规则 {rule_id} 不存在或已归档")
    return detail


@router.post("/mask-rule/{rule_id}/enable")
def mask_rule_enable(rule_id: int) -> dict[str, Any]:
    """实际尝试启用；不合格返回拒绝原因，合格才流转并写字段分级快照回执。"""
    if service_for("mask_rule") is None:
        raise HTTPException(status_code=404, detail="脱敏规则服务未注册")
    if field_grading.store.find("mask_rule", rule_id) is None:
        raise HTTPException(status_code=404, detail=f"脱敏规则 {rule_id} 不存在或已归档")
    return field_grading.try_enable(rule_id)
