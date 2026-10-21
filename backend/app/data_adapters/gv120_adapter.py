"""GV120 系列数据适配器（顶部导向型单座调节阀）

数据结构:
- rated_cv_stroke.table_3.rows: 二维数组，列为:
  [阀门口径inch, 阀门口径mm, 阀芯尺寸inch, 阀芯尺寸mm, EQ%, Md EQ%, Linear, ON-OFF,
   行程P-port金属密封, 行程P-port软密封, 行程ON-OFF金属密封, 行程ON-OFF软密封]

GV120 有 EQ% / Md EQ% / Linear / ON-OFF 四种流量特性。
P-port 分金属密封和软密封两种行程。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import SeriesAdapter, register_adapter, safe_float, mm_to_jis_a


@register_adapter
class Gv120Adapter(SeriesAdapter):
    """GV120 系列适配器"""

    SERIES_CODES = ["GV120"]

    def parse_rated_cv(self) -> List[Dict[str, Any]]:
        """解析 rated_cv_stroke.table_3.rows → valve_cv_stk 行格式"""
        rows: List[Dict[str, Any]] = []
        table_3 = self.data.get("rated_cv_stroke", {}).get("table_3", {})
        raw_rows = table_3.get("rows", [])

        for row in raw_rows:
            if len(row) < 12:
                continue

            # 解析列
            dn_inch, dn_mm, plug_inch, plug_mm = row[0], safe_float(row[1]), row[2], safe_float(row[3])
            cv_eq = safe_float(row[4])
            cv_md = safe_float(row[5])
            cv_linear = safe_float(row[6])
            cv_onoff = safe_float(row[7])
            stroke_p_metal = safe_float(row[8])
            stroke_p_soft = safe_float(row[9])
            stroke_onoff_metal = safe_float(row[10])
            stroke_onoff_soft = safe_float(row[11])

            dn_label = mm_to_jis_a(dn_mm) if dn_mm else None
            trim_label = mm_to_jis_a(plug_mm) if plug_mm else None

            # EQ%
            if cv_eq is not None:
                rows.append({
                    "series_code": "GV120",
                    "dn_label": dn_label,
                    "trim_label": trim_label,
                    "flow_char": "EQ%",
                    "trim_type": "P-port",
                    "pressure_rating": None,
                    "seat_type": "Metal" if stroke_p_metal else "Soft" if stroke_p_soft else None,
                    "rated_cv": cv_eq,
                    "stroke_unit": "mm",
                    "stroke_value": stroke_p_metal or stroke_p_soft,
                    "plug_mm": plug_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

            # Md EQ%
            if cv_md is not None:
                rows.append({
                    "series_code": "GV120",
                    "dn_label": dn_label,
                    "trim_label": trim_label,
                    "flow_char": "Md EQ%",
                    "trim_type": "P-port",
                    "pressure_rating": None,
                    "seat_type": "Metal" if stroke_p_metal else "Soft" if stroke_p_soft else None,
                    "rated_cv": cv_md,
                    "stroke_unit": "mm",
                    "stroke_value": stroke_p_metal or stroke_p_soft,
                    "plug_mm": plug_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

            # Linear
            if cv_linear is not None:
                rows.append({
                    "series_code": "GV120",
                    "dn_label": dn_label,
                    "trim_label": trim_label,
                    "flow_char": "Linear",
                    "trim_type": "P-port",
                    "pressure_rating": None,
                    "seat_type": "Metal" if stroke_p_metal else "Soft" if stroke_p_soft else None,
                    "rated_cv": cv_linear,
                    "stroke_unit": "mm",
                    "stroke_value": stroke_p_metal or stroke_p_soft,
                    "plug_mm": plug_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

            # ON-OFF
            if cv_onoff is not None:
                rows.append({
                    "series_code": "GV120",
                    "dn_label": dn_label,
                    "trim_label": trim_label,
                    "flow_char": "ON-OFF",
                    "trim_type": "Q-port",
                    "pressure_rating": None,
                    "seat_type": "Metal" if stroke_onoff_metal else "Soft" if stroke_onoff_soft else None,
                    "rated_cv": cv_onoff,
                    "stroke_unit": "mm",
                    "stroke_value": stroke_onoff_metal or stroke_onoff_soft,
                    "plug_mm": plug_mm,
                    "cv_min": None,
                    "stk_index": None,
                    "kfd": None, "kfo": None, "kfb": None,
                })

        return rows

    def parse_allowable_dp(self) -> List[Dict[str, Any]]:
        """解析允许压差数据"""
        rows: List[Dict[str, Any]] = []
        # GV120 的压差表在 table_4_1 ~ table_4_x 中
        for key in self.data.keys():
            if not key.startswith("table_4_"):
                continue
            table = self.data[key]
            if not isinstance(table, dict):
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
                    plug_mm = self._plug_inch_to_mm(plug_inch)
                    trim_label = mm_to_jis_a(plug_mm) if plug_mm else None

                    rows.append({
                        "series_code": "GV120",
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
                        "remark": f"source: {key}",
                    })

        return rows

    def _plug_inch_to_mm(self, plug_inch: str) -> Optional[float]:
        """plug 尺寸 inch → mm"""
        from . import inch_to_mm
        return inch_to_mm(plug_inch)
