"""字段分级服务：父级资源等级 + 逐字段继承/例外，由服务端计算字段分级表。

规则：
- 已批准的字段例外只有在实际保护能力不低于例外等级时才可用于规则判定；
- 没有可用例外的字段一律继承父级资源的安全等级；
- 资源升等后，此前批准的低等级例外仍然保留，但会标记为冲突待复审；
- 已生效规则的回执保存当时的字段分级快照，不随后续资源升等变化。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

LEVELS = ["L1", "L2", "L3", "L4"]
LEVEL_LABELS = {"L1": "L1", "L2": "L2", "L3": "L3", "L4": "L4"}


def level_rank(level: str | None) -> int:
    """把 L1~L4 转成可比较的序号；未分级或非法值返回 0。"""
    text = str(level or "").strip().upper()
    return LEVELS.index(text) + 1 if text in LEVELS else 0


def level_or_unknown(level: str | None) -> str:
    rank = level_rank(level)
    return LEVELS[rank - 1] if rank else "未分级"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


# ——————————— 基础读取 ———————————


def resource_row(resource_id: int) -> dict[str, Any] | None:
    return store.find("classify_tag", resource_id)


def resource_level(resource_id: int) -> str:
    row = resource_row(resource_id)
    return level_or_unknown(row.get("安全等级")) if row else "未分级"


def resource_brief(resource_id: int) -> dict[str, Any] | None:
    row = resource_row(resource_id)
    if row is None:
        return None
    return {
        "编号": row.get("id"),
        "标签编号": row.get("标签编号"),
        "数据资源": row.get("数据资源"),
        "安全等级": level_or_unknown(row.get("安全等级")),
        "状态": row.get("status"),
        "数据类型": row.get("数据类型"),
        "合规要求": row.get("合规要求"),
        "脱敏要求": row.get("脱敏要求"),
        "标签时间": row.get("标签时间"),
    }


def catalog_fields(resource_id: int) -> list[dict[str, Any]]:
    """资源字段目录：登记过的字段才允许逐字段确认。"""
    return [
        dict(row) for row in store.aux_rows("resource_fields")
        if _int(row.get("资源编号")) == resource_id
    ]


def field_names(resource_id: int) -> list[str]:
    return [str(row.get("字段名", "")) for row in catalog_fields(resource_id)]


def exceptions_for(resource_id: int) -> list[dict[str, Any]]:
    return [
        dict(row) for row in store.aux_rows("field_exceptions")
        if _int(row.get("资源编号")) == resource_id
    ]


def approved_exception(resource_id: int, field: str) -> dict[str, Any] | None:
    matches = [
        row for row in exceptions_for(resource_id)
        if str(row.get("字段名", "")) == field
        and str(row.get("批准状态", "")) == "已批准"
    ]
    return max(matches, key=lambda row: _int(row.get("id"))) if matches else None


def pending_exception(resource_id: int, field: str) -> dict[str, Any] | None:
    matches = [
        row for row in exceptions_for(resource_id)
        if str(row.get("字段名", "")) == field
        and str(row.get("批准状态", "")) == "待批准"
    ]
    return max(matches, key=lambda row: _int(row.get("id"))) if matches else None


def exception_usable(exception: dict[str, Any] | None) -> bool:
    """例外等级与实际保护能力都必须是有效等级，且实际保护能力不低于例外等级。"""
    if not exception:
        return False
    declared = level_rank(exception.get("例外等级"))
    actual = level_rank(exception.get("实际保护能力"))
    return declared > 0 and actual > 0 and actual >= declared


# ——————————— 草稿与逐字段确认 ———————————


def _draft_row(draft_id: int) -> dict[str, Any] | None:
    return store.aux_find("field_grading_submissions", draft_id)


def submissions_for(resource_id: int) -> list[dict[str, Any]]:
    rows = [
        row for row in store.aux_rows("field_grading_submissions")
        if _int(row.get("资源编号")) == resource_id
    ]
    return sorted(rows, key=lambda row: _int(row.get("id")))


def latest_confirmations(resource_id: int) -> dict[str, dict[str, Any]]:
    """汇总每个字段最近一次已确认的继承/例外选择。"""
    confirmed: dict[str, dict[str, Any]] = {}
    for submission in submissions_for(resource_id):
        for item in submission.get("字段", []):
            if str(item.get("确认状态", "")) != "已确认":
                continue
            confirmed[str(item.get("字段名", ""))] = {
                **item,
                "草稿编号": submission.get("草稿编号"),
                "确认时资源等级": item.get("确认时资源等级"),
                "确认时间": item.get("确认时间"),
            }
    return confirmed


def _exception_index(exception: dict[str, Any] | None) -> dict[str, Any]:
    if not exception:
        return {
            "例外编号": "—",
            "例外等级": "—",
            "实际保护能力": "—",
            "批准状态": "未登记",
            "批准人": "—",
        }
    return {
        "例外编号": exception.get("例外编号"),
        "例外等级": exception.get("例外等级"),
        "实际保护能力": exception.get("实际保护能力"),
        "批准状态": exception.get("批准状态"),
        "批准人": exception.get("批准人"),
        "批准时间": exception.get("批准时间"),
    }


def compute_grading_table(resource_id: int) -> list[dict[str, Any]]:
    """服务端计算每个字段的有效分级、依据和冲突说明。"""
    resource = resource_row(resource_id)
    if resource is None:
        return []
    parent_level = level_or_unknown(resource.get("安全等级"))
    parent_rank = level_rank(parent_level)
    confirmations = latest_confirmations(resource_id)
    table: list[dict[str, Any]] = []

    for index, field in enumerate(catalog_fields(resource_id), start=1):
        name = str(field.get("字段名", ""))
        approved = approved_exception(resource_id, name)
        pending = pending_exception(resource_id, name)
        confirmation = confirmations.get(name)
        mode = str(confirmation.get("确认方式")) if confirmation else ""

        usable = exception_usable(approved)
        notes: list[str] = []
        conflict = ""
        source = "inherit"
        effective = parent_level

        if mode == "例外" and approved:
            if usable:
                effective = level_or_unknown(approved.get("例外等级"))
                source = "exception"
                notes.append(f"采用已批准例外 {approved.get('例外编号')}，按 {effective} 保护")
            else:
                notes.append(
                    f"已批准例外 {approved.get('例外编号')} 的实际保护能力 "
                    f"{approved.get('实际保护能力')} 不足以支撑例外等级 "
                    f"{approved.get('例外等级')}，按继承资源等级处理"
                )
        elif mode == "例外" and not approved:
            if pending:
                notes.append(
                    f"选择了例外但例外 {pending.get('例外编号')} 仍待批准，批准前按继承资源等级处理"
                )
            else:
                notes.append("选择了例外但没有已批准例外，按继承资源等级处理")
        elif mode == "继承":
            effective = parent_level
            if approved:
                notes.append(
                    f"审核员逐字段确认按继承处理，已批准例外 "
                    f"{approved.get('例外编号')} 不参与判定"
                )
            else:
                notes.append(f"审核员逐字段确认按继承处理，继承资源等级 {parent_level}")
        elif approved and usable:
            effective = level_or_unknown(approved.get("例外等级"))
            source = "exception"
            notes.append(f"未逐字段确认时按已批准例外 {approved.get('例外编号')} 判定")
        elif approved and not usable:
            notes.append(
                f"已批准例外 {approved.get('例外编号')} 实际保护能力不足，按继承资源等级处理"
            )
        elif pending:
            notes.append("存在待批准例外，批准前按继承资源等级处理")
        else:
            notes.append(f"缺少已批准例外，继承资源等级 {parent_level}")

        if source == "exception" and parent_rank > level_rank(effective):
            conflict = (
                f"资源已升等至 {parent_level}，已批准例外仍为 {effective}；"
                f"例外复审前该字段按 {effective} 判定，规则保护能力不足 {parent_level} 时不能启用"
            )
        elif source == "exception" and parent_rank and level_rank(effective) > parent_rank:
            conflict = (
                f"例外等级 {effective} 高于父级资源等级 {parent_level}，需确认保持父级上限"
            )
        if approved and not usable and str(approved.get("例外等级")) in LEVELS and not conflict:
            conflict = (
                f"例外 {approved.get('例外编号')} 声明 {approved.get('例外等级')}，"
                f"实际保护能力 {approved.get('实际保护能力')} 不足"
            )

        if confirmation:
            basis = (
                f"{confirmation.get('确认方式')}（草稿 {confirmation.get('草稿编号')} "
                f"确认于 {confirmation.get('确认时资源等级') or '当前'} 资源等级）"
            )
        else:
            basis = "未确认，按服务端默认判定"

        table.append({
            "字段序号": field.get("字段序号") or f"字段{index}",
            "字段名": name,
            "字段说明": field.get("字段说明", ""),
            "资源等级": parent_level,
            "确认方式": confirmation.get("确认方式") if confirmation else ("例外" if source == "exception" else "继承"),
            "确认状态": confirmation.get("确认状态") if confirmation else "未确认",
            "确认草稿": confirmation.get("草稿编号") if confirmation else None,
            "确认时资源等级": confirmation.get("确认时资源等级") if confirmation else None,
            "例外": _exception_index(approved),
            "待批准例外": _exception_index(pending) if pending else None,
            "例外可用": usable,
            "有效分级": effective,
            "分级依据": "；".join(notes),
            "冲突说明": conflict,
            "来源": source,
            "更新时间": confirmation.get("确认时间") if confirmation else (resource.get("标签时间") or "—"),
        })
    return table


def grading_row(resource_id: int, field: str) -> dict[str, Any] | None:
    for row in compute_grading_table(resource_id):
        if row["字段名"] == field:
            return row
    return None


# ——————————— 规则资格 ———————————


def rules_for_resource(resource_id: int) -> list[dict[str, Any]]:
    return [
        row for row in store.rows("mask_rule")
        if _int(row.get("关联资源编号")) == resource_id
    ]


def eligibility_for_rule(rule: dict[str, Any], table: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    resource_id = _int(rule.get("关联资源编号"))
    protection = level_or_unknown(rule.get("保护等级"))
    protection_rank = level_rank(protection)
    field_name = str(rule.get("目标字段", ""))
    reasons: list[str] = []
    warnings: list[str] = []

    resource = resource_row(resource_id)
    if resource is None:
        return {
            "规则id": rule.get("id"),
            "规则编号": rule.get("规则编号"),
            "目标字段": field_name,
            "保护等级": protection,
            "关联资源": "—",
            "资源等级": "未分级",
            "字段有效分级": "未分级",
            "分级依据": "资源不存在或已归档",
            "冲突说明": "",
            "资格": "不可启用",
            "原因": ["未绑定有效的数据资源，无法确认字段分级"],
        }

    rows = table if table is not None else compute_grading_table(resource_id)
    matched = next((row for row in rows if row["字段名"] == field_name), None)
    if matched is None:
        return {
            "规则id": rule.get("id"),
            "规则编号": rule.get("规则编号"),
            "目标字段": field_name,
            "保护等级": protection,
            "关联资源": resource.get("数据资源"),
            "资源等级": level_or_unknown(resource.get("安全等级")),
            "字段有效分级": "未登记",
            "分级依据": "目标字段不在字段分级表中",
            "冲突说明": "",
            "资格": "不可启用",
            "原因": [f"目标字段「{field_name}」未在资源字段分级表中登记，无法确认继承或例外"],
        }

    effective = matched["有效分级"]
    basis = matched["分级依据"]
    conflict = str(matched.get("冲突说明") or "")
    approval = str((matched.get("例外") or {}).get("批准状态") or "")
    if conflict:
        warnings.append(conflict)
    elif approval == "待批准":
        warnings.append(f"字段「{field_name}」的例外仍在待批准状态，按继承资源等级判定")
    elif str(matched.get("确认状态")) == "待确认":
        warnings.append(f"字段「{field_name}」存在尚未确认的草稿，当前按服务端默认判定")

    if level_rank(effective) == 0:
        reasons.append("字段有效分级未确定，资源尚未完成分级")
    if protection_rank == 0:
        reasons.append(f"规则实际保护能力「{protection}」不是有效等级")
    if protection_rank and level_rank(effective) and protection_rank < level_rank(effective):
        reasons.append(
            f"规则实际保护能力 {protection} 低于字段「{field_name}」的有效分级 {effective}"
            f"（{basis}）；无法启用"
        )

    eligible = not reasons
    return {
        "规则id": rule.get("id"),
        "规则编号": rule.get("规则编号"),
        "目标字段": field_name,
        "保护等级": protection,
        "关联资源": resource.get("数据资源"),
        "资源等级": level_or_unknown(resource.get("安全等级")),
        "字段有效分级": effective,
        "分级依据": basis,
        "冲突说明": conflict,
        "资格": "可启用" if eligible else "不可启用",
        "原因": reasons,
        "提示": warnings,
    }


def rule_groups(resource_id: int) -> dict[str, Any]:
    """按字段分组说明哪组规则仍可启用。"""
    table = compute_grading_table(resource_id)
    groups: dict[str, dict[str, Any]] = {}
    for row in table:
        groups[row["字段名"]] = {
            "字段序号": row["字段序号"],
            "字段名": row["字段名"],
            "有效分级": row["有效分级"],
            "分级依据": row["分级依据"],
            "冲突说明": row["冲突说明"],
            "规则": [],
        }
    for rule in rules_for_resource(resource_id):
        info = eligibility_for_rule(rule, table)
        group = groups.setdefault(str(rule.get("目标字段", "")), {
            "字段序号": "未登记",
            "字段名": rule.get("目标字段", ""),
            "有效分级": "未登记",
            "分级依据": "目标字段不在字段分级表中",
            "冲突说明": "",
            "规则": [],
        })
        group["规则"].append(info)
    eligible = [info["规则编号"] for group in groups.values() for info in group["规则"] if info["资格"] == "可启用"]
    rejected = [info["规则编号"] for group in groups.values() for info in group["规则"] if info["资格"] != "可启用"]
    return {
        "groups": list(groups.values()),
        "eligible_rules": eligible,
        "rejected_rules": rejected,
    }


# ——————————— 编辑提交 ———————————


def _exception_label() -> str:
    count = len(store.aux_rows("field_exceptions"))
    return f"EXCP-{count + 1:04d}"


def _upsert_exception(
    resource_id: int,
    field: str,
    *,
    exception_level: str,
    protection: str,
    operator: str,
    approved: bool,
    remark: str = "",
) -> dict[str, Any]:
    rows = store.aux_rows("field_exceptions")
    existing = next(
        (row for row in rows
         if _int(row.get("资源编号")) == resource_id and str(row.get("字段名")) == field),
        None,
    )
    values = {
        "资源编号": resource_id,
        "字段名": field,
        "例外等级": exception_level,
        "实际保护能力": protection,
        "批准状态": "已批准" if approved else "待批准",
        "批准人": operator if approved else "—",
        "批准时间": _now() if approved else "—",
        "说明": remark or "审核员在字段分级编辑器中提交的字段例外",
    }
    if existing is None:
        existing = {"id": max((_int(row.get("id")) for row in rows), default=0) + 1, "例外编号": _exception_label()}
        existing.update(values)
        rows.append(existing)
    else:
        existing.update(values)
    return existing


def submit_draft(
    resource_id: int,
    fields: list[dict[str, Any]],
    *,
    operator: str,
    remark: str = "",
) -> tuple[dict[str, Any] | None, list[str]]:
    """审核员提交父级资源与字段例外：逐字段选择继承或例外，形成待确认草稿。"""
    resource = resource_row(resource_id)
    if resource is None:
        return None, [f"数据资源 {resource_id} 不存在"]
    names = field_names(resource_id)
    if not fields:
        return None, ["至少要确认一个字段"]
    if not names:
        return None, ["该资源还没有登记字段目录，无法逐字段确认"]

    normalized: list[dict[str, Any]] = []
    errors: list[str] = []
    for item in fields:
        name = str(item.get("字段名") or "").strip()
        if name not in names:
            errors.append(f"字段「{name or '（空）'}」不在资源字段目录中")
            continue
        mode = str(item.get("确认方式") or "继承").strip()
        if mode not in ("继承", "例外"):
            errors.append(f"字段「{name}」的确认方式只能是继承或例外")
            continue
        exception_level = str(item.get("例外等级") or "").strip()
        protection = str(item.get("实际保护能力") or "").strip()
        approved = bool(item.get("批准", True))
        if mode == "例外":
            if exception_level and exception_level not in LEVELS:
                errors.append(f"字段「{name}」的例外等级必须是 L1~L4")
                continue
            if protection and protection not in LEVELS:
                errors.append(f"字段「{name}」的实际保护能力必须是 L1~L4")
                continue
            if not exception_level or not protection:
                existing = approved_exception(resource_id, name) or pending_exception(resource_id, name)
                if existing is None:
                    errors.append(
                        f"字段「{name}」选择例外时必须填写例外等级和实际保护能力"
                    )
                    continue
                exception_level = exception_level or str(existing.get("例外等级", ""))
                protection = protection or str(existing.get("实际保护能力", ""))
        normalized.append({
            "字段名": name,
            "确认方式": mode,
            "例外等级": exception_level if mode == "例外" else "—",
            "实际保护能力": protection if mode == "例外" else level_or_unknown(resource.get("安全等级")),
            "批准": approved,
            "批准状态": ("已批准" if approved else "待批准") if mode == "例外" else "—",
            "说明": str(item.get("说明") or remark),
            "确认状态": "待确认",
            "确认时间": "—",
            "确认时资源等级": "—",
        })

    if errors:
        return None, errors
    if not normalized:
        return None, ["没有可提交的字段"]

    prior = submissions_for(resource_id)
    draft = store.aux_append("field_grading_submissions", {
        "资源编号": resource_id,
        "草稿编号": f"FGDR-{len(prior) + 1:04d}",
        "提交时资源等级": level_or_unknown(resource.get("安全等级")),
        "提交人": operator,
        "提交时间": _now(),
        "状态": "待确认",
        "备注": remark,
        "字段": normalized,
    })
    return draft, []


def confirm_draft_field(
    resource_id: int,
    draft_id: int,
    field: str | None,
    *,
    operator: str,
) -> tuple[dict[str, Any] | None, str, list[str]]:
    """逐字段确认旧草稿；确认时记录当前资源等级，便于核对交错确认顺序。"""
    draft = _draft_row(draft_id)
    if draft is None or _int(draft.get("资源编号")) != resource_id:
        return None, "草稿不存在或不属于该资源", []
    resource = resource_row(resource_id)
    if resource is None:
        return None, "数据资源不存在", []
    target = field or str(draft.get("字段", [{}])[0].get("字段名", "")) if draft.get("字段") else ""
    if target:
        items = [item for item in draft.get("字段", []) if str(item.get("字段名")) == target]
        if not items:
            return None, f"草稿中没有字段「{target}」", []
    else:
        items = list(draft.get("字段", []))

    current_level = level_or_unknown(resource.get("安全等级"))
    stale = str(draft.get("提交时资源等级")) != current_level
    for item in items:
        if str(item.get("确认方式")) == "例外":
            # 确认时才把例外落库（提交阶段只是草稿，不产生已批准的例外）。
            exception_level = str(item.get("例外等级") or "")
            protection = str(item.get("实际保护能力") or "")
            exception = _upsert_exception(
                resource_id, str(item.get("字段名")),
                exception_level=exception_level,
                protection=protection,
                operator=operator,
                approved=bool(item.get("批准", True)),
                remark=str(item.get("说明") or draft.get("备注") or ""),
            )
            item["例外编号"] = exception.get("例外编号")
            item["批准状态"] = exception.get("批准状态")
        item["确认状态"] = "已确认"
        item["确认时间"] = _now()
        item["确认时资源等级"] = current_level
        item["确认人"] = operator
    confirmed = [
        item for item in draft.get("字段", []) if str(item.get("确认状态")) == "已确认"
    ]
    if len(confirmed) == len(draft.get("字段", [])):
        draft["状态"] = "已确认"
        draft["确认时间"] = _now()
    else:
        draft["状态"] = "部分确认"
    draft["确认时资源等级"] = current_level
    if stale:
        draft["备注"] = (str(draft.get("备注", "")) + "；资源等级已变化，按确认时等级重新核对").strip("；")
    message = (
        f"字段「{target}」已在资源 {current_level} 下确认"
        if target else f"草稿 {draft.get('草稿编号')} 全部字段已在资源 {current_level} 下确认"
    )
    if stale:
        message += f"（草稿提交时为 {draft.get('提交时资源等级')}，属于旧草稿复核）"
    return draft, message, []


def raise_resource_level(resource_id: int, new_level: str, *, operator: str, remark: str = "") -> tuple[dict[str, Any] | None, list[str]]:
    """调整父级资源等级，并返回被标记为旧草稿待复核的草稿编号。"""
    resource = resource_row(resource_id)
    if resource is None:
        return None, []
    previous = level_or_unknown(resource.get("安全等级"))
    resource["安全等级"] = new_level
    resource["status"] = "已分级"
    resource["pending"] = True
    resource["标签时间"] = _now()
    resource["字段分级变更"] = (
        f"{operator} 将资源等级由 {previous} 调整为 {new_level}：{remark}" if remark
        else f"{operator} 将资源等级由 {previous} 调整为 {new_level}"
    )
    # 等级变化后，尚未确认的草稿必须重新按新等级复核。
    touched = invalidate_unconfirmed_drafts(
        resource_id, f"资源等级由 {previous} 调整为 {new_level}，请重新确认",
    )
    return resource, [str(draft.get("草稿编号")) for draft in touched]


def invalidate_unconfirmed_drafts(resource_id: int, reason: str) -> list[dict[str, Any]]:
    """资源等级变化后，把尚未确认的草稿标记为需要重新确认。"""
    touched: list[dict[str, Any]] = []
    for draft in submissions_for(resource_id):
        if str(draft.get("状态")) in ("待确认", "部分确认"):
            draft["状态"] = "旧草稿待复核"
            draft["失效原因"] = reason
            touched.append(draft)
    return touched


def snapshot_for_receipt(resource_id: int) -> dict[str, Any]:
    """生成不可变的字段分级快照，供规则生效回执保存。"""
    return {
        "资源编号": resource_id,
        "资源等级": resource_level(resource_id),
        "字段分级": [
            {
                "字段序号": row["字段序号"],
                "字段名": row["字段名"],
                "有效分级": row["有效分级"],
                "分级依据": row["分级依据"],
                "冲突说明": row["冲突说明"],
            }
            for row in compute_grading_table(resource_id)
        ],
    }


def receipts_for(rule_id: int) -> list[dict[str, Any]]:
    return [
        dict(row) for row in store.aux_rows("rule_receipts")
        if _int(row.get("规则id")) == rule_id
    ]


def record_receipt(rule: dict[str, Any], *, operator: str) -> dict[str, Any]:
    resource_id = _int(rule.get("关联资源编号"))
    snapshot = snapshot_for_receipt(resource_id)
    field = str(rule.get("目标字段", ""))
    matched = next(
        (item for item in snapshot["字段分级"] if item["字段名"] == field),
        None,
    )
    receipts = store.aux_rows("rule_receipts")
    receipt_id = max((_int(row.get("id")) for row in receipts), default=0) + 1
    receipt = {
        "id": receipt_id,
        "回执编号": f"RCPT-{receipt_id:04d}",
        "规则id": rule.get("id"),
        "规则编号": rule.get("规则编号"),
        "生效时间": _now(),
        "操作人": operator,
        "资源等级": snapshot["资源等级"],
        "字段名称": field,
        "字段有效分级": matched["有效分级"] if matched else "未登记",
        "分级依据": matched["分级依据"] if matched else "目标字段不在字段分级表中",
        "保护等级": level_or_unknown(rule.get("保护等级")),
        "判定": "通过",
        "字段分级快照": snapshot,
    }
    receipts.append(receipt)
    return receipt


def rule_detail(rule_id: int) -> dict[str, Any] | None:
    rule = store.find("mask_rule", rule_id)
    if rule is None:
        return None
    resource_id = _int(rule.get("关联资源编号"))
    resource = resource_brief(resource_id)
    table = compute_grading_table(resource_id)
    eligibility = eligibility_for_rule(rule, table)
    field_row = next((row for row in table if row["字段名"] == str(rule.get("目标字段", ""))), None)
    groups = rule_groups(resource_id) if resource else {"groups": [], "eligible_rules": [], "rejected_rules": []}
    return {
        "规则": dict(rule),
        "资源": resource,
        "资源等级": level_or_unknown(resource.get("安全等级")) if resource else "未分级",
        "字段分级": field_row,
        "字段分级表": table,
        "保护等级": level_or_unknown(rule.get("保护等级")),
        "资格": eligibility["资格"],
        "原因": eligibility["原因"],
        "提示": eligibility["提示"],
        "冲突说明": eligibility["冲突说明"],
        "资格明细": eligibility,
        "回执": receipts_for(rule_id),
        "当前快照": snapshot_for_receipt(resource_id) if resource else None,
        "规则分组": groups,
    }


def try_enable(rule_id: int, *, operator: str = "数据安全审核员") -> dict[str, Any]:
    """实际尝试启用规则：不合格就只回原因，合格才流转并写回执。"""
    rule = store.find("mask_rule", rule_id)
    if rule is None:
        return {"ok": False, "message": f"脱敏规则 {rule_id} 不存在或已归档", "规则": None}
    detail = rule_detail(rule_id)
    assert detail is not None
    if detail["资格"] != "可启用":
        reason = "；".join(detail["原因"]) or "字段分级不足以支撑规则启用"
        return {
            "ok": False,
            "message": f"无法启用 {rule.get('规则编号')}：{reason}",
            "规则": dict(rule),
            "资格明细": detail["资格明细"],
        }
    rule["status"] = "已生效"
    rule["pending"] = True
    rule["生效时间"] = _now()
    receipt = record_receipt(rule, operator=operator)
    warnings = "；".join(detail["提示"]) if detail["提示"] else ""
    message = f"{rule.get('规则编号')} 已启用，回执 {receipt['回执编号']}"
    if warnings:
        message += f"；冲突提示：{warnings}"
    return {
        "ok": True,
        "message": message,
        "规则": dict(rule),
        "回执": receipt,
        "资格明细": detail["资格明细"],
    }


def resource_overview(resource_id: int) -> dict[str, Any] | None:
    resource = resource_brief(resource_id)
    if resource is None:
        return None
    table = compute_grading_table(resource_id)
    groups = rule_groups(resource_id)
    drafts = submissions_for(resource_id)
    level_changed = any(str(draft.get("提交时资源等级")) != resource["安全等级"] for draft in drafts)
    conflicts = [
        {
            "字段名": row["字段名"],
            "有效分级": row["有效分级"],
            "冲突说明": row["冲突说明"],
        }
        for row in table if row["冲突说明"]
    ]
    return {
        "资源": resource,
        "资源等级": resource["安全等级"],
        "等级选项": LEVELS,
        "字段目录": catalog_fields(resource_id),
        "字段分级表": table,
        "例外": exceptions_for(resource_id),
        "草稿": drafts,
        "存在旧草稿": level_changed,
        "冲突": conflicts,
        "规则分组": groups,
        "可启用规则": groups["eligible_rules"],
        "不可启用规则": groups["rejected_rules"],
    }
