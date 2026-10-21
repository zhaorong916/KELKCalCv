"""BT210 系列数据适配器（高性能双偏心蝶阀）

数据结构:
- rated_cv.values: 列表，每条包含 size_inch/size_mm/ansi150_60_open/ansi150_90_open/
  ansi300_60_open/ansi300_90_open

BT210 是蝶阀，Cv 值按 ANSI 150#/300# 和 60°/90° 开度分列。
入库时按压力等级和开度组合生成多行记录。
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import SeriesAdapter, register_adapter, safe_float, mm_to_jis_a


@register_adapter
class Bt210Adapter(SeriesAdapter):
    """BT210 系列适配器"""

    SERIES_CODES = ["BT210"]

    def parse_rated_cv(self) -> List[Dict[str, Any]]:
        """解析 rated_cv.values → valve_cv_stk 行格式"""
        rows: List[Dict[str, Any]] = []
        rated_cv_data = self.data.get("rated_cv", {})
        values = rated_cv_data.get("values", [])

        for item in values:
            size_mm = safe_float(item.get("size_mm"))
            dn_label = mm_to_jis_a(size_mm) if size_mm else None

            # ANSI 150# 60° 开度
            cv_150_60 = safe_float(item.get("ansi150_60_open"))
            if cv_150_60 is not None:
                rows.append({
                    "series_code": "BT210",
                    "dn_label": dn_label,
                    "trim_label": dn_label,  # 蝶阀无独立阀芯尺寸，与口径一致
                    "flow_char": "Inherent Character",
                    "trim_type": "60° Open",
                    "pressure_rating": "150#",
                    "seat_type": None,
                    "rated_cv": cv_150_60,
                    "stroke_unit": "°",
                    "stroke_value": 60.0,
                    "plug_mm": size_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

            # ANSI 150# 90° 开度
            cv_150_90 = safe_float(item.get("ansi150_90_open"))
            if cv_150_90 is not None:
                rows.append({
                    "series_code": "BT210",
                    "dn_label": dn_label,
                    "trim_label": dn_label,
                    "flow_char": "Inherent Character",
                    "trim_type": "90° Open",
                    "pressure_rating": "150#",
                    "seat_type": None,
                    "rated_cv": cv_150_90,
                    "stroke_unit": "°",
                    "stroke_value": 90.0,
                    "plug_mm": size_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

            # ANSI 300# 60° 开度
            cv_300_60 = safe_float(item.get("ansi300_60_open"))
            if cv_300_60 is not None:
                rows.append({
                    "series_code": "BT210",
                    "dn_label": dn_label,
                    "trim_label": dn_label,
                    "flow_char": "Inherent Character",
                    "trim_type": "60° Open",
                    "pressure_rating": "300#",
                    "seat_type": None,
                    "rated_cv": cv_300_60,
                    "stroke_unit": "°",
                    "stroke_value": 60.0,
                    "plug_mm": size_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

            # ANSI 300# 90° 开度
            cv_300_90 = safe_float(item.get("ansi300_90_open"))
            if cv_300_90 is not None:
                rows.append({
                    "series_code": "BT210",
                    "dn_label": dn_label,
                    "trim_label": dn_label,
                    "flow_char": "Inherent Character",
                    "trim_type": "90° Open",
                    "pressure_rating": "300#",
                    "seat_type": None,
                    "rated_cv": cv_300_90,
                    "stroke_unit": "°",
                    "stroke_value": 90.0,
                    "plug_mm": size_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

        return rows

    def parse_body_pt(self) -> List[Dict[str, Any]]:
        """解析阀体温压数据"""
        rows: List[Dict[str, Any]] = []
        # BT210 的温压数据在 appendix_table_1 中
        appendix = self.data.get("appendix_table_1", {})
        if not appendix:
            return rows

        # appendix_table_1 是 ANSI B16.34 标准温压表
        materials = appendix.get("materials", [])
        for mat in materials:
            material = mat.get("material")
            for class_data in mat.get("classes", []):
                pressure_class = class_data.get("class")
                for temp_data in class_data.get("temps", []):
                    rows.append({
                        "series_code": "BT210",
                        "body_material": material,
                        "standard": "ASME B16.34",
                        "pressure_class": pressure_class,
                        "temp_c": safe_float(temp_data.get("temp_c")),
                        "max_pressure_mpa": safe_float(temp_data.get("pressure_mpa")),
                        "remark": None,
                    })

        return rows
