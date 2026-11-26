"""业务路由汇总：跨模块链接与字段分级路由必须先于通用资源路由注册。

通用资源路由含 /api/{module}/{entry_id}，如果放在前面会把
/api/field-grading/{id}、/api/mask-rule/{id}/detail 这类固定路径抢先匹配掉。
"""
from __future__ import annotations

from app.routers import cross_links, field_grading, resource

ROUTERS = [cross_links, field_grading, resource]
