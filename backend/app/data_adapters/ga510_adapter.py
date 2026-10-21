"""GA510 系列数据适配器（角行程调节阀）

数据结构:
- cv_stroke.rows: 二维数组，列为:
  [size_inch, size_mm, plug_inch, plug_mm, cv_high_perf_Pport, cv_large, cv_Qport,
   stroke_Pport, stroke_Qport]

GA510 是角行程调节阀，有 P-port(高特性型/大Cv) 和 Q-port(ON-OFF) 两种阀芯形式。
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import SeriesAdapter, register_adapter, safe_float, mm_to_jis_a


@register_adapter
class Ga510Adapter(SeriesAdapter):
    """GA510 系列适配器"""

    SERIES_CODES = ["GA510"]

    def parse_rated_cv(self) -> List[Dict[str, Any]]:
        """解析 cv_stroke.rows → valve_cv_stk 行格式"""
        rows: List[Dict[str, Any]] = []
        cv_stroke = self.data.get("cv_stroke", {})
        raw_rows = cv_stroke.get("rows", [])

        for row in raw_rows:
            if len(row) < 9:
                continue

            size_inch, size_mm, plug_inch, plug_mm = row[0], safe_float(row[1]), row[2], safe_float(row[3])
            cv_high_perf = safe_float(row[4])
            cv_large = safe_float(row[5])
            cv_qport = safe_float(row[6])
            stroke_p = safe_float(row[7])
            stroke_q = safe_float(row[8])

            dn_label = mm_to_jis_a(size_mm) if size_mm else None
            trim_label = mm_to_jis_a(plug_mm) if plug_mm else None

            # P-port 高特性型
            if cv_high_perf is not None:
                rows.append({
                    "series_code": "GA510",
                    "dn_label": dn_label,
                    "trim_label": trim_label,
                    "flow_char": "EQ%",
                    "trim_type": "High Performance P-port",
                    "pressure_rating": None,
                    "seat_type": None,
                    "rated_cv": cv_high_perf,
                    "stroke_unit": "mm" if stroke_p else None,
                    "stroke_value": stroke_p,
                    "plug_mm": plug_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

            # P-port 大Cv
            if cv_large is not None:
                rows.append({
                    "series_code": "GA510",
                    "dn_label": dn_label,
                    "trim_label": trim_label,
                    "flow_char": "Linear",
                    "trim_type": "Large Cv",
                    "pressure_rating": None,
                    "seat_type": None,
                    "rated_cv": cv_large,
                    "stroke_unit": "mm" if stroke_p else None,
                    "stroke_value": stroke_p,
                    "plug_mm": plug_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

            # Q-port ON-OFF
            if cv_qport is not None:
                rows.append({
                    "series_code": "GA510",
                    "dn_label": dn_label,
                    "trim_label": trim_label,
                    "flow_char": "ON-OFF",
                    "trim_type": "Q-port",
                    "pressure_rating": None,
                    "seat_type": None,
                    "rated_cv": cv_qport,
                    "stroke_unit": "mm" if stroke_q else None,
                    "stroke_value": stroke_q,
                    "plug_mm": plug_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

        return rows
