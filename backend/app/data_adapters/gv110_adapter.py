"""GV110 系列数据适配器（微小流量调节阀）

数据结构:
- rated_cv_stroke.table_3_1_needle_type: 针型阀芯
- rated_cv_stroke.table_3_2_v_type: V型阀芯

GV110 是微小流量调节阀，Cv 值非常小，有针型和 V 型两种阀芯。
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import SeriesAdapter, register_adapter, safe_float, mm_to_jis_a


@register_adapter
class Gv110Adapter(SeriesAdapter):
    """GV110 系列适配器"""

    SERIES_CODES = ["GV110"]

    def parse_rated_cv(self) -> List[Dict[str, Any]]:
        """解析 rated_cv_stroke → valve_cv_stk 行格式"""
        rows: List[Dict[str, Any]] = []
        rcv = self.data.get("rated_cv_stroke", {})

        # 表3-1 针型阀芯
        needle_table = rcv.get("table_3_1_needle_type", {})
        for row in needle_table.get("rows", []):
            if len(row) < 4:
                continue
            plug_inch, plug_mm, cv, stroke = row[0], safe_float(row[1]), safe_float(row[2]), safe_float(row[3])
            if cv is None:
                continue
            rows.append({
                "series_code": "GV110",
                "dn_label": None,  # GV110 只有 plug size，无独立 dn
                "trim_label": mm_to_jis_a(plug_mm) if plug_mm else None,
                "flow_char": "EQ%",
                "trim_type": "Needle",
                "pressure_rating": None,
                "seat_type": None,
                "rated_cv": cv,
                "stroke_unit": "mm" if stroke else None,
                "stroke_value": stroke,
                "plug_mm": plug_mm,
                "cv_min": None,
                "stk_index": None,
                "kfd": None, "kfo": None, "kfb": None,
            })

        # 表3-2 V型阀芯
        v_table = rcv.get("table_3_2_v_type", {})
        for item in v_table.get("rows", []):
            plug_mm = safe_float(item.get("size_mm"))
            stroke = safe_float(item.get("stroke"))
            # V型阀芯的 rated_cv 是列表，表示多档可选
            cv_values = item.get("rated_cv", [])
            if not isinstance(cv_values, list):
                cv_values = [cv_values]
            # 取最大值作为 rated_cv
            cv_max = max((safe_float(v) for v in cv_values if safe_float(v) is not None), default=None)
            if cv_max is None:
                continue
            rows.append({
                "series_code": "GV110",
                "dn_label": None,
                "trim_label": mm_to_jis_a(plug_mm) if plug_mm else None,
                "flow_char": "EQ%",
                "trim_type": "V-type",
                "pressure_rating": None,
                "seat_type": None,
                "rated_cv": cv_max,
                "stroke_unit": "mm" if stroke else None,
                "stroke_value": stroke,
                "plug_mm": plug_mm,
                "cv_min": None,
                "stk_index": None,
                "kfd": None, "kfo": None, "kfb": None,
            })

        return rows
