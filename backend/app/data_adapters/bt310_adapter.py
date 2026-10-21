"""BT310 系列数据适配器（蝶阀）

数据结构:
- rated_cv_and_flow.values: 对象列表，包含 inch/mm/cv_60_open/cv_90_open

BT310 是蝶阀，只有 60°/90° 开度两种 Cv 值。
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import SeriesAdapter, register_adapter, safe_float, mm_to_jis_a


@register_adapter
class Bt310Adapter(SeriesAdapter):
    """BT310 系列适配器"""

    SERIES_CODES = ["BT310"]

    def parse_rated_cv(self) -> List[Dict[str, Any]]:
        """解析 rated_cv_and_flow.values → valve_cv_stk 行格式"""
        rows: List[Dict[str, Any]] = []
        rated_cv = self.data.get("rated_cv_and_flow", {})
        values = rated_cv.get("values", [])

        for item in values:
            size_mm = safe_float(item.get("mm"))
            dn_label = mm_to_jis_a(size_mm) if size_mm else None

            # 60° 开度
            cv_60 = safe_float(item.get("cv_60_open"))
            if cv_60 is not None:
                rows.append({
                    "series_code": "BT310",
                    "dn_label": dn_label,
                    "trim_label": dn_label,
                    "flow_char": "60°",
                    "trim_type": "Standard",
                    "pressure_rating": None,
                    "seat_type": None,
                    "rated_cv": cv_60,
                    "stroke_unit": "°",
                    "stroke_value": 60.0,
                    "plug_mm": size_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

            # 90° 开度
            cv_90 = safe_float(item.get("cv_90_open"))
            if cv_90 is not None:
                rows.append({
                    "series_code": "BT310",
                    "dn_label": dn_label,
                    "trim_label": dn_label,
                    "flow_char": "90°",
                    "trim_type": "Standard",
                    "pressure_rating": None,
                    "seat_type": None,
                    "rated_cv": cv_90,
                    "stroke_unit": "°",
                    "stroke_value": 90.0,
                    "plug_mm": size_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

        return rows
