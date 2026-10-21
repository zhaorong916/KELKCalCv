"""BT110 系列数据适配器（蝶阀）

数据结构:
- rated_cv_table_3.rows: 对象列表，包含 size_mm/cv_60deg_damper/cv_90deg_damper/
  cv_60deg_15sealed/cv_90deg_15sealed

BT110 是蝶阀，有 60°/90° 开度和 Damper/15 Deg Sealed 两种密封形式。
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import SeriesAdapter, register_adapter, safe_float, mm_to_jis_a


@register_adapter
class Bt110Adapter(SeriesAdapter):
    """BT110 系列适配器"""

    SERIES_CODES = ["BT110"]

    def parse_rated_cv(self) -> List[Dict[str, Any]]:
        """解析 rated_cv_table_3.rows → valve_cv_stk 行格式"""
        rows: List[Dict[str, Any]] = []
        table_3 = self.data.get("rated_cv_table_3", {})
        raw_rows = table_3.get("rows", [])

        for item in raw_rows:
            size_mm = safe_float(item.get("size_mm"))
            dn_label = mm_to_jis_a(size_mm) if size_mm else None

            # 60° Damper
            cv_60d = safe_float(item.get("cv_60deg_damper"))
            if cv_60d is not None:
                rows.append({
                    "series_code": "BT110",
                    "dn_label": dn_label,
                    "trim_label": dn_label,
                    "flow_char": "60°",
                    "trim_type": "Damper",
                    "pressure_rating": None,
                    "seat_type": "Damper",
                    "rated_cv": cv_60d,
                    "stroke_unit": "°",
                    "stroke_value": 60.0,
                    "plug_mm": size_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

            # 90° Damper
            cv_90d = safe_float(item.get("cv_90deg_damper"))
            if cv_90d is not None:
                rows.append({
                    "series_code": "BT110",
                    "dn_label": dn_label,
                    "trim_label": dn_label,
                    "flow_char": "90°",
                    "trim_type": "Damper",
                    "pressure_rating": None,
                    "seat_type": "Damper",
                    "rated_cv": cv_90d,
                    "stroke_unit": "°",
                    "stroke_value": 90.0,
                    "plug_mm": size_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

            # 60° 15 Deg Sealed
            cv_60s = safe_float(item.get("cv_60deg_15sealed"))
            if cv_60s is not None:
                rows.append({
                    "series_code": "BT110",
                    "dn_label": dn_label,
                    "trim_label": dn_label,
                    "flow_char": "60°",
                    "trim_type": "15 Deg Sealed",
                    "pressure_rating": None,
                    "seat_type": "15 Deg Sealed",
                    "rated_cv": cv_60s,
                    "stroke_unit": "°",
                    "stroke_value": 60.0,
                    "plug_mm": size_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

            # 90° 15 Deg Sealed
            cv_90s = safe_float(item.get("cv_90deg_15sealed"))
            if cv_90s is not None:
                rows.append({
                    "series_code": "BT110",
                    "dn_label": dn_label,
                    "trim_label": dn_label,
                    "flow_char": "90°",
                    "trim_type": "15 Deg Sealed",
                    "pressure_rating": None,
                    "seat_type": "15 Deg Sealed",
                    "rated_cv": cv_90s,
                    "stroke_unit": "°",
                    "stroke_value": 90.0,
                    "plug_mm": size_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

        return rows
