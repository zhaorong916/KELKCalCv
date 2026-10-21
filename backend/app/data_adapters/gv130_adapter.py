"""GV130 系列数据适配器（与 GV120 类似的顶部导向型单座调节阀）

数据结构:
- rated_cv_stroke.rows: 对象列表，包含 valve_inch/valve_mm/plug_inch/plug_mm/
  cv_p_port_higheq_①/cv_p_port_largecv_②/cv_q_port_onoff/stroke_p_port/stroke_q_port

GV130 有 P-port High EQ / P-port Large Cv / Q-port ON-OFF 三种阀芯形式。
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import SeriesAdapter, register_adapter, safe_float, mm_to_jis_a


@register_adapter
class Gv130Adapter(SeriesAdapter):
    """GV130 系列适配器"""

    SERIES_CODES = ["GV130"]

    def parse_rated_cv(self) -> List[Dict[str, Any]]:
        """解析 rated_cv_stroke.rows → valve_cv_stk 行格式"""
        rows: List[Dict[str, Any]] = []
        rcv = self.data.get("rated_cv_stroke", {})
        raw_rows = rcv.get("rows", [])

        for item in raw_rows:
            valve_mm = safe_float(item.get("valve_mm"))
            plug_mm = safe_float(item.get("plug_mm"))
            stroke_p = safe_float(item.get("stroke_p_port"))
            stroke_q = safe_float(item.get("stroke_q_port"))

            dn_label = mm_to_jis_a(valve_mm) if valve_mm else None
            trim_label = mm_to_jis_a(plug_mm) if plug_mm else None

            # P-port High EQ
            cv_high = safe_float(item.get("cv_p_port_higheq_①"))
            if cv_high is not None:
                rows.append({
                    "series_code": "GV130",
                    "dn_label": dn_label,
                    "trim_label": trim_label,
                    "flow_char": "EQ%",
                    "trim_type": "P-port High EQ",
                    "pressure_rating": None,
                    "seat_type": None,
                    "rated_cv": cv_high,
                    "stroke_unit": "mm" if stroke_p else None,
                    "stroke_value": stroke_p,
                    "plug_mm": plug_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

            # P-port Large Cv
            cv_large = safe_float(item.get("cv_p_port_largecv_②"))
            if cv_large is not None:
                rows.append({
                    "series_code": "GV130",
                    "dn_label": dn_label,
                    "trim_label": trim_label,
                    "flow_char": "EQ%",
                    "trim_type": "P-port Large Cv",
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
            cv_q = safe_float(item.get("cv_q_port_onoff"))
            if cv_q is not None:
                rows.append({
                    "series_code": "GV130",
                    "dn_label": dn_label,
                    "trim_label": trim_label,
                    "flow_char": "ON-OFF",
                    "trim_type": "Q-port",
                    "pressure_rating": None,
                    "seat_type": None,
                    "rated_cv": cv_q,
                    "stroke_unit": "mm" if stroke_q else None,
                    "stroke_value": stroke_q,
                    "plug_mm": plug_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

        return rows
