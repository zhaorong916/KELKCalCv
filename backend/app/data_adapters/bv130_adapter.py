"""BV130 系列数据适配器（球阀）

数据结构:
- rated_cv.values: 对象列表，包含 inch/mm/Cv

BV130 是球阀，只有一个 Cv 值。
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import SeriesAdapter, register_adapter, safe_float, mm_to_jis_a


@register_adapter
class Bv130Adapter(SeriesAdapter):
    """BV130 系列适配器"""

    SERIES_CODES = ["BV130"]

    def parse_rated_cv(self) -> List[Dict[str, Any]]:
        """解析 rated_cv.values → valve_cv_stk 行格式"""
        rows: List[Dict[str, Any]] = []
        rated_cv = self.data.get("rated_cv", {})
        values = rated_cv.get("values", [])

        for item in values:
            size_mm = safe_float(item.get("mm"))
            cv = safe_float(item.get("Cv"))
            dn_label = mm_to_jis_a(size_mm) if size_mm else None

            if cv is None:
                continue

            rows.append({
                "series_code": "BV130",
                "dn_label": dn_label,
                "trim_label": dn_label,
                "flow_char": "Inherent Character",
                "trim_type": "Full Bore",
                "pressure_rating": None,
                "seat_type": None,
                "rated_cv": cv,
                "stroke_unit": "°",
                "stroke_value": 90.0,
                "plug_mm": size_mm,
                "cv_min": None,
                "stk_index": None,
                "kfd": None, "kfo": None, "kfb": None,
            })

        return rows
