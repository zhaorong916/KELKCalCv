"""GC320 系列数据适配器（多级降压式套筒导向型调节阀）

数据结构:
- rated_cv_stroke: 列表，每条包含 valve_inch/valve_mm/plug_inch/plug_mm/stroke_mm/min_cv/
  cv_1stg/cv_2stg/cv_4stg/cv_6stg/cv_8stg
- 特殊: 部分行有 cv_8stg_options 表示多档可选

GC320 是多级降压阀，流量特性只有 Linear，按级数(1/2/4/6/8)有不同 Cv 值。
入库时取最大级数的 Cv 作为 rated_cv，min_cv 作为 cv_min。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import SeriesAdapter, register_adapter, safe_float, inch_to_mm, mm_to_jis_a


@register_adapter
class Gc320Adapter(SeriesAdapter):
    """GC320 系列适配器"""

    SERIES_CODES = ["GC320"]

    def parse_rated_cv(self) -> List[Dict[str, Any]]:
        """解析 rated_cv_stroke → valve_cv_stk 行格式"""
        rows: List[Dict[str, Any]] = []
        rated_cv_list = self.data.get("rated_cv_stroke", [])

        for item in rated_cv_list:
            # 基础字段
            valve_mm = safe_float(item.get("valve_mm"))
            plug_mm = safe_float(item.get("plug_mm"))
            stroke_mm = safe_float(item.get("stroke_mm"))
            min_cv = safe_float(item.get("min_cv"))

            dn_label = mm_to_jis_a(valve_mm) if valve_mm else None
            trim_label = mm_to_jis_a(plug_mm) if plug_mm else None

            # 取最大级数的 Cv 作为 rated_cv
            # 优先级: 8stg > 6stg > 4stg > 2stg > 1stg
            rated_cv = None
            stages = None
            for stg in [8, 6, 4, 2, 1]:
                cv = safe_float(item.get(f"cv_{stg}stg"))
                if cv is not None:
                    rated_cv = cv
                    stages = stg
                    break

            # 如果有 cv_8stg_options，说明是多档可选，取最大值
            cv_options = item.get("cv_8stg_options")
            if cv_options and isinstance(cv_options, list):
                max_cv = max(safe_float(v) for v in cv_options if safe_float(v) is not None)
                if max_cv:
                    rated_cv = max_cv
                    stages = 8

            if rated_cv is None:
                continue  # 跳过无 Cv 的行

            rows.append({
                "series_code": "GC320",
                "dn_label": dn_label,
                "trim_label": trim_label,
                "flow_char": "Linear",  # GC320 只有线性特性
                "trim_type": f"{stages}Stage" if stages else "Multi-Stage",
                "pressure_rating": None,
                "seat_type": None,
                "rated_cv": rated_cv,
                "stroke_unit": "mm" if stroke_mm else None,
                "stroke_value": stroke_mm,
                "plug_mm": plug_mm,
                "cv_min": min_cv,
                "stk_index": None,
                "kfd": None, "kfo": None, "kfb": None,
            })

        return rows

    def parse_allowable_dp(self) -> List[Dict[str, Any]]:
        """解析允许压差数据"""
        rows: List[Dict[str, Any]] = []
        # GC320 的压差数据在 table_4_1 ~ table_4_4 中
        for i in range(1, 5):
            table_key = f"table_4_{i}"
            table = self.data.get(table_key)
            if not table:
                continue

            actuator = table.get("actuator", "")
            plug_sizes = table.get("plug_sizes_inch", [])
            table_rows = table.get("rows", [])

            for row in table_rows:
                actuator_size = row.get("actuator_size")
                air_supply = row.get("air_supply_kPaG")
                spring_range = row.get("spring_range_kPaG")
                seat_type = row.get("seat_type")
                dp_by_plug = row.get("dp_MPa_by_plug", {})

                for plug_inch, max_dp in dp_by_plug.items():
                    plug_mm = inch_to_mm(plug_inch)
                    trim_label = mm_to_jis_a(plug_mm) if plug_mm else None

                    rows.append({
                        "series_code": "GC320",
                        "dn_label": None,
                        "trim_label": trim_label,
                        "pressure_rating": None,
                        "seat_type": "Metal" if "金属" in str(seat_type) else "Soft" if "软" in str(seat_type) else None,
                        "max_dp_mpa": safe_float(max_dp),
                        "flow_direction": None,
                        "actuator_type": actuator,
                        "actuator_size": actuator_size,
                        "air_supply": air_supply,
                        "spring_range": spring_range,
                        "packing": None,
                        "remark": f"source: {table_key}",
                    })

        return rows
