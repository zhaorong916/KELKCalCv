"""GC120/GC210 系列数据适配器

数据结构:
- rated_cv_stroke: 按系列分组的列表，每条包含 dn_inch/dn_mm/plug_inch/plug_mm/is_full_port/
  cv_eq_pct/cv_md_eq_pct/cv_linear/stroke_mm
- allowable_pressure_drops: 执行机构组合的压差表
- body_pressure_temperature_ratings: 阀体材质温压表

GC120: 有 EQ% / Linear / Md EQ% 三种流量特性
GC210: 有 Linear / Md EQ% 两种流量特性，多孔套筒降噪结构，需要 cv_min
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import SeriesAdapter, register_adapter, safe_float, parse_temp_range


@register_adapter
class Gc120210Adapter(SeriesAdapter):
    """GC120/GC210 系列适配器"""

    SERIES_CODES = ["GC120", "GC210"]
    JSON_FILENAME = "GC120_210_structured_data.json"  # 共用数据文件

    def __init__(self, series_code: str, json_path=None):
        # GC120 和 GC210 共用同一个 JSON 文件
        from . import DOCS_DIR
        json_path = json_path or (DOCS_DIR / self.JSON_FILENAME)
        super().__init__(series_code, json_path)

    def parse_rated_cv(self) -> List[Dict[str, Any]]:
        """解析 rated_cv_stroke → valve_cv_stk 行格式"""
        rows: List[Dict[str, Any]] = []
        rated_cv_data = self.data.get("rated_cv_stroke", {})

        for series_code in self.SERIES_CODES:
            series_rows = rated_cv_data.get(series_code, [])
            for item in series_rows:
                # 基础字段
                dn_label = self._norm_dn_label(dn_mm=item.get("dn_mm"))
                trim_label = self._norm_trim_label(plug_mm=item.get("plug_mm"))
                plug_mm = safe_float(item.get("plug_mm"))
                stroke_mm = safe_float(item.get("stroke_mm"))
                is_full_port = item.get("is_full_port", False)

                # GC120: 解析 EQ% / Linear / Md EQ% 三个流量特性
                if series_code == "GC120":
                    # EQ%
                    cv_eq = safe_float(item.get("cv_eq_pct"))
                    if cv_eq is not None:
                        rows.append({
                            "series_code": series_code,
                            "dn_label": dn_label,
                            "trim_label": trim_label,
                            "flow_char": "EQ%",
                            "trim_type": "Full" if is_full_port else "Standard",
                            "pressure_rating": None,  # GC120 不区分压力等级
                            "seat_type": None,
                            "rated_cv": cv_eq,
                            "stroke_unit": "mm" if stroke_mm else None,
                            "stroke_value": stroke_mm,
                            "plug_mm": plug_mm,
                            "cv_min": None,
                            "stk_index": None,
                            "kfd": None, "kfo": None, "kfb": None,
                        })
                    # Linear
                    cv_linear = safe_float(item.get("cv_linear"))
                    if cv_linear is not None:
                        rows.append({
                            "series_code": series_code,
                            "dn_label": dn_label,
                            "trim_label": trim_label,
                            "flow_char": "Linear",
                            "trim_type": "Full" if is_full_port else "Standard",
                            "pressure_rating": None,
                            "seat_type": None,
                            "rated_cv": cv_linear,
                            "stroke_unit": "mm" if stroke_mm else None,
                            "stroke_value": stroke_mm,
                            "plug_mm": plug_mm,
                            "cv_min": None,
                            "stk_index": None,
                            "kfd": None, "kfo": None, "kfb": None,
                        })
                    # Md EQ% (大口径等百分比)
                    cv_md = safe_float(item.get("cv_md_eq_pct"))
                    if cv_md is not None:
                        rows.append({
                            "series_code": series_code,
                            "dn_label": dn_label,
                            "trim_label": trim_label,
                            "flow_char": "Md EQ%",
                            "trim_type": "Full" if is_full_port else "Standard",
                            "pressure_rating": None,
                            "seat_type": None,
                            "rated_cv": cv_md,
                            "stroke_unit": "mm" if stroke_mm else None,
                            "stroke_value": stroke_mm,
                            "plug_mm": plug_mm,
                            "cv_min": None,
                            "stk_index": None,
                            "kfd": None, "kfo": None, "kfb": None,
                        })

                # GC210: 只有 Linear / Md EQ%，需要 cv_min
                elif series_code == "GC210":
                    cv_linear = safe_float(item.get("cv_linear"))
                    cv_md = safe_float(item.get("cv_md_eq_pct"))
                    cv_min = safe_float(item.get("cv_min"))  # GC210 特有

                    if cv_linear is not None:
                        rows.append({
                            "series_code": series_code,
                            "dn_label": dn_label,
                            "trim_label": trim_label,
                            "flow_char": "Linear",
                            "trim_type": "Full" if is_full_port else "Standard",
                            "pressure_rating": None,
                            "seat_type": None,
                            "rated_cv": cv_linear,
                            "stroke_unit": "mm" if stroke_mm else None,
                            "stroke_value": stroke_mm,
                            "plug_mm": plug_mm,
                            "cv_min": cv_min,
                            "stk_index": None,
                            "kfd": None, "kfo": None, "kfb": None,
                        })
                    if cv_md is not None:
                        rows.append({
                            "series_code": series_code,
                            "dn_label": dn_label,
                            "trim_label": trim_label,
                            "flow_char": "Md EQ%",
                            "trim_type": "Full" if is_full_port else "Standard",
                            "pressure_rating": None,
                            "seat_type": None,
                            "rated_cv": cv_md,
                            "stroke_unit": "mm" if stroke_mm else None,
                            "stroke_value": stroke_mm,
                            "plug_mm": plug_mm,
                            "cv_min": cv_min,
                            "stk_index": None,
                            "kfd": None, "kfo": None, "kfb": None,
                        })

        return rows

    def parse_allowable_dp(self) -> List[Dict[str, Any]]:
        """解析允许压差数据"""
        rows: List[Dict[str, Any]] = []
        dp_data = self.data.get("allowable_pressure_drops", {})

        for table_key, table in dp_data.items():
            if not isinstance(table, dict):
                continue
            actuator = table.get("actuator", "")
            packing = table.get("packing", "")
            plug_sizes = table.get("plug_sizes_inch", [])
            table_rows = table.get("rows", [])

            for row in table_rows:
                actuator_size = row.get("actuator_size")
                air_supply = row.get("air_supply_kPaG")
                spring_range = row.get("spring_range_kPaG")
                seat_type = row.get("seat_type")
                dp_by_plug = row.get("dp_MPa_by_plug", {})

                for plug_inch, max_dp in dp_by_plug.items():
                    # 转换 plug_inch → trim_label
                    plug_mm = self._plug_inch_to_mm(plug_inch)
                    trim_label = self._norm_trim_label(plug_mm=plug_mm) if plug_mm else None

                    rows.append({
                        "series_code": "GC120",  # 压差表主要用于 GC120
                        "dn_label": None,  # 压差表通常按 plug size 而非 dn
                        "trim_label": trim_label,
                        "plug_inch": plug_inch,  # 阀芯尺寸(英寸), 入库唯一键的一部分
                        "pressure_rating": None,
                        "seat_type": "Metal" if "金属" in str(seat_type) else "Soft" if "软" in str(seat_type) else None,
                        "max_dp_mpa": safe_float(max_dp),
                        "flow_direction": None,
                        "actuator_type": actuator,
                        "actuator_size": actuator_size,
                        "air_supply": air_supply,
                        "spring_range": spring_range,
                        "packing": packing,
                        "remark": f"source: {table_key}",
                    })

        return rows

    def parse_body_pt(self) -> List[Dict[str, Any]]:
        """解析阀体温压数据"""
        rows: List[Dict[str, Any]] = []
        pt_data = self.data.get("body_pressure_temperature_ratings", {})

        # body_pressure_temperature_ratings 的结构:
        # { "ansi": [...], "pn": {...} }
        ansi_list = pt_data.get("ansi", [])
        for item in ansi_list:
            rows.append({
                "series_code": "GC120",
                "body_material": item.get("material"),
                "standard": "ASME B16.34",
                "pressure_class": item.get("class"),
                "temp_c": safe_float(item.get("temp_c")),
                "max_pressure_mpa": safe_float(item.get("pressure_mpa")),
                "remark": None,
            })

        # PN 系列
        pn_dict = pt_data.get("pn", {})
        for material, temp_map in pn_dict.items():
            for temp_range, pn_map in temp_map.items():
                t_min, t_max = parse_temp_range(temp_range)
                for pn_class, pressure in pn_map.items():
                    rows.append({
                        "series_code": "GC120",
                        "body_material": material,
                        "standard": "HG/T20592",
                        "pressure_class": pn_class,
                        "temp_c": t_max,  # 使用上限温度
                        "temp_min_c": t_min,
                        "max_pressure_mpa": safe_float(pressure),
                        "remark": f"temp_range: {temp_range}",
                    })

        return rows

    def _plug_inch_to_mm(self, plug_inch: str) -> Optional[float]:
        """plug 尺寸 inch → mm"""
        from . import inch_to_mm
        return inch_to_mm(plug_inch)


# ---------------------------------------------------------------------------
# GC210 特殊处理：数据结构不同，linear/modified_eq_pct 是嵌套对象
# ---------------------------------------------------------------------------

@register_adapter
class Gc210Adapter(SeriesAdapter):
    """GC210 系列适配器（与 GC120 共用数据文件，但数据结构不同）

    GC210 的 rated_cv_stroke 中，linear 和 modified_eq_pct 是嵌套对象:
    {
        "linear": {"cv_min": 0.55, "cv_rated": 6.3, "rangeability": 11.5},
        "modified_eq_pct": {"cv_min": 0.17, "cv_rated": 5.7, "rangeability": 33.5}
    }
    """

    SERIES_CODES = ["GC210"]
    JSON_FILENAME = "GC120_210_structured_data.json"

    def __init__(self, series_code: str = "GC210", json_path=None):
        from . import DOCS_DIR
        json_path = json_path or (DOCS_DIR / self.JSON_FILENAME)
        super().__init__(series_code, json_path)

    def parse_rated_cv(self) -> List[Dict[str, Any]]:
        """解析 GC210 的 rated_cv_stroke → valve_cv_stk 行格式"""
        rows: List[Dict[str, Any]] = []
        rated_cv_data = self.data.get("rated_cv_stroke", {})
        gc210_rows = rated_cv_data.get("GC210", [])

        for item in gc210_rows:
            # 基础字段
            dn_label = self._norm_dn_label(dn_mm=item.get("dn_mm"))
            trim_label = self._norm_trim_label(plug_mm=item.get("plug_mm"))
            plug_mm = safe_float(item.get("plug_mm"))
            stroke_mm = safe_float(item.get("stroke_mm"))
            is_full_port = item.get("is_full_port", False)

            # Linear 特性
            linear = item.get("linear", {})
            if linear:
                cv_rated = safe_float(linear.get("cv_rated"))
                cv_min = safe_float(linear.get("cv_min"))
                if cv_rated is not None:
                    rows.append({
                        "series_code": "GC210",
                        "dn_label": dn_label,
                        "trim_label": trim_label,
                        "flow_char": "Linear",
                        "trim_type": "Full" if is_full_port else "Standard",
                        "pressure_rating": None,
                        "seat_type": None,
                        "rated_cv": cv_rated,
                        "stroke_unit": "mm" if stroke_mm else None,
                        "stroke_value": stroke_mm,
                        "plug_mm": plug_mm,
                        "cv_min": cv_min,
                        "stk_index": None,
                        "kfd": None, "kfo": None, "kfb": None,
                    })

            # Modified EQ% 特性
            md_eq = item.get("modified_eq_pct", {})
            if md_eq:
                cv_rated = safe_float(md_eq.get("cv_rated"))
                cv_min = safe_float(md_eq.get("cv_min"))
                if cv_rated is not None:
                    rows.append({
                        "series_code": "GC210",
                        "dn_label": dn_label,
                        "trim_label": trim_label,
                        "flow_char": "Md EQ%",
                        "trim_type": "Full" if is_full_port else "Standard",
                        "pressure_rating": None,
                        "seat_type": None,
                        "rated_cv": cv_rated,
                        "stroke_unit": "mm" if stroke_mm else None,
                        "stroke_value": stroke_mm,
                        "plug_mm": plug_mm,
                        "cv_min": cv_min,
                        "stk_index": None,
                        "kfd": None, "kfo": None, "kfb": None,
                    })

        return rows
