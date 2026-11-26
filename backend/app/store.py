"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。

业务表（SEED_ROWS）参与运营概览统计；AUX_ROWS 是字段分级、例外、回执这类
支撑表，不属于可登记的独立业务模块，所以单独放在 aux 命名空间里。
"""
from __future__ import annotations

import copy
from typing import Any

from app.seed import AUX_ROWS, SEED_ROWS


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {}
        self._aux: dict[str, list[dict[str, Any]]] = {}
        self.reset()

    def reset(self) -> None:
        """恢复到种子数据，测试或演示需要重新开始时使用。"""
        self._tables = {
            name: copy.deepcopy(rows) for name, rows in SEED_ROWS.items()
        }
        self._aux = {
            name: copy.deepcopy(rows) for name, rows in AUX_ROWS.items()
        }

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    # ——————————— 支撑表（字段目录 / 例外 / 草稿 / 回执） ———————————

    def aux_rows(self, table: str) -> list[dict[str, Any]]:
        return self._aux.setdefault(table, [])

    def aux_find(self, table: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.aux_rows(table):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def aux_append(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        """按当前最大 id 自增后写入支撑表。"""
        rows = self.aux_rows(table)
        stored = {"id": max((int(item.get("id", 0)) for item in rows), default=0) + 1}
        stored.update(row)
        rows.append(stored)
        return stored

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
