"""BV210 系列数据适配器（球阀）

数据结构:
- rated_cv.table_3: 列表，每条包含 size_inch/size_mm/cv_ANSI150_300/cv_ANSI600

BV210 是球阀，Cv 值按 ANSI 150/300 和 ANSI 600 两个压力等级分列。
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import SeriesAdapter, register_adapter, safe_float, mm_to_jis_a


@register_adapter
class Bv210Adapter(SeriesAdapter):
    """BV210 系列适配器"""

    SERIES_CODES = ["BV210"]

    def parse_rated_cv(self) -> List[Dict[str, Any]]:
        """解析 rated_cv.table_3 → valve_cv_stk 行格式"""
        rows: List[Dict[str, Any]] = []
        table_3 = self.data.get("rated_cv", {}).get("table_3", [])

        for item in table_3:
            size_mm = safe_float(item.get("size_mm"))
            dn_label = mm_to_jis_a(size_mm) if size_mm else None

            # ANSI 150/300 (库中使用 300#)
            cv_150_300 = safe_float(item.get("cv_ANSI150_300"))
            if cv_150_300 is not None:
                rows.append({
                    "series_code": "BV210",
                    "dn_label": dn_label,
                    "trim_label": dn_label,  # 球阀无独立阀芯尺寸
                    "flow_char": "ON-OFF",
                    "trim_type": "Standard",
                    "pressure_rating": "300#",
                    "seat_type": None,
                    "rated_cv": cv_150_300,
                    "stroke_unit": "°",
                    "stroke_value": 90.0,
                    "plug_mm": size_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

            # ANSI 600
            cv_600 = safe_float(item.get("cv_ANSI600"))
            if cv_600 is not None:
                rows.append({
                    "series_code": "BV210",
                    "dn_label": dn_label,
                    "trim_label": dn_label,
                    "flow_char": "ON-OFF",
                    "trim_type": "Standard",
                    "pressure_rating": "600#",
                    "seat_type": None,
                    "rated_cv": cv_600,
                    "stroke_unit": "°",
                    "stroke_value": 90.0,
                    "plug_mm": size_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

        return rows
