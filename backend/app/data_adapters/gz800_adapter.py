"""GZ800 系列数据适配器（自力式调节阀）

数据结构:
- rated_cv_table5: 按子系列分组（GZ810/GZ820_GZ830/GZ840/GZ850/GZ860）

GZ800 是自力式调节阀，包含多个子系列：
- GZ810: 阀前/阀后压力控制，小流量
- GZ820/GZ830: 阀前/阀后压力控制，中大流量
- GZ840: 差压控制
- GZ850: 流量控制
- GZ860: 温度控制
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import SeriesAdapter, register_adapter, safe_float, mm_to_jis_a


@register_adapter
class Gz800Adapter(SeriesAdapter):
    """GZ800 系列适配器"""

    SERIES_CODES = ["GZ810", "GZ820", "GZ830", "GZ840", "GZ850", "GZ860"]
    JSON_FILENAME = "GZ800_structured_data.json"

    def __init__(self, series_code: str, json_path=None):
        from . import DOCS_DIR
        json_path = json_path or (DOCS_DIR / self.JSON_FILENAME)
        super().__init__(series_code, json_path)

    def parse_rated_cv(self) -> List[Dict[str, Any]]:
        """解析 rated_cv_table5 → valve_cv_stk 行格式"""
        rows: List[Dict[str, Any]] = []
        table5 = self.data.get("rated_cv_table5", {})

        # GZ810: 阀前/阀后压力控制，小流量
        gz810 = table5.get("GZ810", {})
        downstream = gz810.get("downstream_by_seat_dia", {})
        for seat_dia, cv in downstream.items():
            cv_val = safe_float(cv)
            if cv_val is None:
                continue
            rows.append({
                "series_code": "GZ810",
                "dn_label": None,
                "trim_label": f"{seat_dia}A",
                "flow_char": "EQ%",
                "trim_type": "Downstream",
                "pressure_rating": None,
                "seat_type": None,
                "rated_cv": cv_val,
                "stroke_unit": None,
                "stroke_value": None,
                "plug_mm": safe_float(seat_dia),
                "cv_min": None,
                "stk_index": None,
                "kfd": None, "kfo": None, "kfb": None,
            })

        upstream = gz810.get("upstream_cv_values", [])
        for i, cv in enumerate(upstream):
            cv_val = safe_float(cv)
            if cv_val is None:
                continue
            rows.append({
                "series_code": "GZ810",
                "dn_label": None,
                "trim_label": f"Upstream-{i+1}",
                "flow_char": "EQ%",
                "trim_type": "Upstream",
                "pressure_rating": None,
                "seat_type": None,
                "rated_cv": cv_val,
                "stroke_unit": None,
                "stroke_value": None,
                "plug_mm": None,
                "cv_min": None,
                "stk_index": None,
                "kfd": None, "kfo": None, "kfb": None,
            })

        # GZ820/GZ830: 中大流量
        gz820_830 = table5.get("GZ820_GZ830", {})
        by_seat = gz820_830.get("by_seat_dia", {})
        for seat_dia, cv_data in by_seat.items():
            downstream_cv = safe_float(cv_data.get("downstream"))
            upstream_cv = safe_float(cv_data.get("upstream"))

            if downstream_cv is not None:
                rows.append({
                    "series_code": "GZ820",
                    "dn_label": None,
                    "trim_label": f"{seat_dia}A",
                    "flow_char": "EQ%",
                    "trim_type": "Downstream",
                    "pressure_rating": None,
                    "seat_type": None,
                    "rated_cv": downstream_cv,
                    "stroke_unit": None,
                    "stroke_value": None,
                    "plug_mm": safe_float(seat_dia),
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })
            if upstream_cv is not None:
                rows.append({
                    "series_code": "GZ830",
                    "dn_label": None,
                    "trim_label": f"{seat_dia}A",
                    "flow_char": "EQ%",
                    "trim_type": "Upstream",
                    "pressure_rating": None,
                    "seat_type": None,
                    "rated_cv": upstream_cv,
                    "stroke_unit": None,
                    "stroke_value": None,
                    "plug_mm": safe_float(seat_dia),
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

        # GZ840: 差压控制
        gz840 = table5.get("GZ840", {})
        downstream_840 = gz840.get("downstream_by_seat_dia", {})
        for seat_dia, cv in downstream_840.items():
            cv_val = safe_float(cv)
            if cv_val is None:
                continue
            rows.append({
                "series_code": "GZ840",
                "dn_label": None,
                "trim_label": f"{seat_dia}A",
                "flow_char": "EQ%",
                "trim_type": "Downstream",
                "pressure_rating": None,
                "seat_type": None,
                "rated_cv": cv_val,
                "stroke_unit": None,
                "stroke_value": None,
                "plug_mm": safe_float(seat_dia),
                "cv_min": None,
                "stk_index": None,
                "kfd": None, "kfo": None, "kfb": None,
            })

        # GZ850: 流量控制
        gz850 = table5.get("GZ850", {})
        downstream_850 = gz850.get("downstream_by_seat_dia", {})
        for seat_dia, cv in downstream_850.items():
            cv_val = safe_float(cv)
            if cv_val is None:
                continue
            rows.append({
                "series_code": "GZ850",
                "dn_label": None,
                "trim_label": f"{seat_dia}A",
                "flow_char": "EQ%",
                "trim_type": "Downstream",
                "pressure_rating": None,
                "seat_type": None,
                "rated_cv": cv_val,
                "stroke_unit": None,
                "stroke_value": None,
                "plug_mm": safe_float(seat_dia),
                "cv_min": None,
                "stk_index": None,
                "kfd": None, "kfo": None, "kfb": None,
            })

        # GZ860: 温度控制
        gz860 = table5.get("GZ860", {})
        downstream_860 = gz860.get("downstream_by_seat_dia", {})
        for seat_dia, cv in downstream_860.items():
            cv_val = safe_float(cv)
            if cv_val is None:
                continue
            rows.append({
                "series_code": "GZ860",
                "dn_label": None,
                "trim_label": f"{seat_dia}A",
                "flow_char": "EQ%",
                "trim_type": "Downstream",
                "pressure_rating": None,
                "seat_type": None,
                "rated_cv": cv_val,
                "stroke_unit": None,
                "stroke_value": None,
                "plug_mm": safe_float(seat_dia),
                "cv_min": None,
                "stk_index": None,
                "kfd": None, "kfo": None, "kfb": None,
            })

        return rows
