"""单位转换引擎

内部统一单位（计算引擎直接使用这些单位）：
  压力(绝压)   kPa(abs)
  温度         ℃
  质量流量     kg/h
  体积流量     m³/h (液体)  Nm³/h (气体标况 0℃,101.325kPa)
  密度         kg/m³
  动力粘度     cP
  口径/直径    mm
  壁厚         mm
  距离         m
  Cv           无单位(美制 Cv)

压力单位区分绝压(absolute)/表压(gauge)：
  绝压: result = value × factor           (offset=0)
  表压: result = value × factor + 101.325  (offset=101.325 kPa, 即1个标准大气压)

所有录入参数先按单位字典转换为内部单位，再送入计算引擎。
单位字典来源于数据库 unit_definitions 表，初始种子从 Excel 单位换算表导入。
"""
from __future__ import annotations
from typing import Optional


# ---- 内置默认单位字典（从 Excel 单位换算.xlsm 导入，Cv 计算相关） ----
# 格式: (category, unit_code, unit_label, factor, offset, is_primary, unit_group, pressure_type)
# factor: 乘以此系数得到内部单位值
# offset: 加以此偏移得到内部单位值（温度、表压等场景）
# unit_group: metric(公制) / imperial(英制)
# pressure_type: absolute(绝压) / gauge(表压) / None(非压力)

BUILTIN_UNITS = [
    # ==================== 压力 (→ kPa abs) ====================
    # 公制 - 绝压
    ("pressure", "kPaA", "kPa(A)", 1.0, 0.0, True, "metric", "absolute"),
    ("pressure", "barA", "bar(A)", 100.0, 0.0, False, "metric", "absolute"),
    ("pressure", "MPaA", "MPa(A)", 1000.0, 0.0, False, "metric", "absolute"),
    ("pressure", "kgf_cm2A", "kgf/cm²(A)", 98.0665, 0.0, False, "metric", "absolute"),
    ("pressure", "atm", "atm", 101.325, 0.0, False, "metric", "absolute"),
    # 公制 - 表压 (offset=101.325 kPa = 1 atm)
    ("pressure", "kPaG", "kPa(G)", 1.0, 101.325, False, "metric", "gauge"),
    ("pressure", "barG", "bar(G)", 100.0, 101.325, False, "metric", "gauge"),
    ("pressure", "MPaG", "MPa(G)", 1000.0, 101.325, False, "metric", "gauge"),
    ("pressure", "kgf_cm2G", "kgf/cm²(G)", 98.0665, 101.325, False, "metric", "gauge"),
    # 英制
    ("pressure", "psiA", "psi(A)", 6.894757, 0.0, False, "imperial", "absolute"),
    ("pressure", "psiG", "psi(G)", 6.894757, 101.325, False, "imperial", "gauge"),

    # ==================== 温度 (→ ℃) ====================
    ("temperature", "C", "℃", 1.0, 0.0, True, "metric", None),
    ("temperature", "K", "K", 1.0, -273.15, False, "metric", None),
    ("temperature", "F", "℉", 5.0 / 9.0, -32.0 * 5.0 / 9.0, False, "imperial", None),
    ("temperature", "R", "°R", 5.0 / 9.0, -273.15, False, "imperial", None),

    # ==================== 质量流量 (→ kg/h) ====================
    ("mass_flow", "kg_h", "kg/h", 1.0, 0.0, True, "metric", None),
    ("mass_flow", "kg_s", "kg/s", 3600.0, 0.0, False, "metric", None),
    ("mass_flow", "t_h", "t/h", 1000.0, 0.0, False, "metric", None),
    ("mass_flow", "lb_h", "lb/h", 0.45359237, 0.0, False, "imperial", None),
    ("mass_flow", "kpph", "k lb/h", 453.59237, 0.0, False, "imperial", None),

    # ==================== 液体体积流量 (→ m³/h) ====================
    ("vol_flow_liquid", "m3_h", "m³/h", 1.0, 0.0, True, "metric", None),
    ("vol_flow_liquid", "L_min", "L/min", 0.06, 0.0, False, "metric", None),
    ("vol_flow_liquid", "m3_s", "m³/s", 3600.0, 0.0, False, "metric", None),
    ("vol_flow_liquid", "L_h", "L/h", 0.001, 0.0, False, "metric", None),
    ("vol_flow_liquid", "kL_h", "kL/h", 1.0, 0.0, False, "metric", None),
    ("vol_flow_liquid", "GPM", "GPM", 0.22712470704, 0.0, False, "imperial", None),
    ("vol_flow_liquid", "BPD", "BPD", 0.006624470622, 0.0, False, "imperial", None),

    # ==================== 气体体积流量 (→ Nm³/h 标况0℃) ====================
    ("vol_flow_gas", "Nm3_h", "Nm³/h(0℃)", 1.0, 0.0, True, "metric", None),
    ("vol_flow_gas", "Nm3_h_20", "Nm³/h(20℃)", 0.9327, 0.0, False, "metric", None),
    ("vol_flow_gas", "SCFM", "SCFM", 1.699, 0.0, False, "imperial", None),

    # ==================== 密度 (→ kg/m³) ====================
    ("density", "kg_m3", "kg/m³", 1.0, 0.0, True, "metric", None),
    ("density", "g_cm3", "g/cm³", 1000.0, 0.0, False, "metric", None),
    ("density", "lb_ft3", "lb/ft³", 16.0185, 0.0, False, "imperial", None),

    # ==================== 粘度 (→ cP) ====================
    ("viscosity", "cP", "cP", 1.0, 0.0, True, "metric", None),
    ("viscosity", "mPa_s", "mPa·s", 1.0, 0.0, False, "metric", None),
    ("viscosity", "Pa_s", "Pa·s", 1000.0, 0.0, False, "metric", None),

    # ==================== 口径/直径 (→ mm) ====================
    ("diameter", "mm", "mm", 1.0, 0.0, True, "metric", None),
    ("diameter", "cm", "cm", 10.0, 0.0, False, "metric", None),
    ("diameter", "m", "m", 1000.0, 0.0, False, "metric", None),
    ("diameter", "inch", "inch", 25.4, 0.0, False, "imperial", None),

    # ==================== 壁厚 (→ mm) ====================
    ("wall_thickness", "mm", "mm", 1.0, 0.0, True, "metric", None),
    ("wall_thickness", "inch", "inch", 25.4, 0.0, False, "imperial", None),

    # ==================== 距离 (→ m, 噪音测点) ====================
    ("distance", "m", "m", 1.0, 0.0, True, "metric", None),
    ("distance", "cm", "cm", 0.01, 0.0, False, "metric", None),
    ("distance", "ft", "ft", 0.3048, 0.0, False, "imperial", None),

    # ==================== 摩尔质量 (→ kg/kmol) ====================
    ("molecular_weight", "kg_kmol", "kg/kmol", 1.0, 0.0, True, "metric", None),
    ("molecular_weight", "g_mol", "g/mol", 1.0, 0.0, False, "metric", None),
]


def convert(value: Optional[float], unit_code: str, category: str) -> Optional[float]:
    """将 value 从指定单位转换为内部统一单位。

    Args:
        value: 输入值
        unit_code: 单位代码（BUILTIN_UNITS 中的 code）
        category: 参数类别（pressure/temperature/mass_flow/...）

    Returns:
        转换后的值（内部统一单位）；若 value 为 None 返回 None
    """
    if value is None or value == "":
        return None
    if unit_code is None:
        return float(value)
    # 查内置表
    for cat, code, label, factor, offset, is_pri, group, ptype in BUILTIN_UNITS:
        if cat == category and code == unit_code:
            if factor < 0:
                return None
            return float(value) * factor + offset
    # 未找到 → 返回原值（按内部单位处理）
    return float(value)


def get_units_by_category(category: str) -> list[dict]:
    """获取某参数类别的所有可选单位。"""
    out = []
    for cat, code, label, factor, offset, is_pri, group, ptype in BUILTIN_UNITS:
        if cat == category:
            out.append({
                "unit_code": code, "unit_label": label,
                "factor": factor, "offset": offset, "is_primary": is_pri,
                "unit_group": group, "pressure_type": ptype,
            })
    return out


def get_primary_unit(category: str) -> Optional[dict]:
    """获取某类别的内部主单位。"""
    for cat, code, label, factor, offset, is_pri, group, ptype in BUILTIN_UNITS:
        if cat == category and is_pri:
            return {"unit_code": code, "unit_label": label}
    return None


# 参数类别 → 默认单位代码映射（用于前端下拉框默认选中）
DEFAULT_UNIT_CODES = {
    "pressure": "kPaA",
    "temperature": "C",
    "mass_flow": "kg_h",
    "vol_flow_liquid": "m3_h",
    "vol_flow_gas": "Nm3_h",
    "density": "kg_m3",
    "viscosity": "cP",
    "diameter": "mm",
    "wall_thickness": "mm",
    "distance": "m",
    "molecular_weight": "kg_kmol",
}

# 工艺参数字段 → 单位类别映射
FIELD_TO_CATEGORY = {
    "p1": "pressure", "p2": "pressure",
    "t1": "temperature", "t2": "temperature",
    "flow_mass": "mass_flow",
    "flow_vol_liquid": "vol_flow_liquid",
    "flow_vol_gas": "vol_flow_gas",
    "mass_flow_gas": "mass_flow", "mass_flow_liquid": "mass_flow",
    "density_override": "density",
    "viscosity_override": "viscosity",
    "molecular_weight_override": "molecular_weight",
    "pipe_diameter": "diameter",
    "pipe_wall": "wall_thickness",
    "distance": "distance",
    "density_gas": "density", "density_liquid": "density",
}


def convert_process_case(raw_case: dict, db_session=None) -> dict:
    """将 ProcessCase 录入数据（带单位代码）转换为内部统一单位。

    输入 dict 中的 *_unit 字段表示对应数值字段的单位。
    转换后的 dict 数值全部为内部单位，去掉 *_unit 字段。

    Args:
        raw_case: 前端提交的工况 dict
        db_session: 可选 SQLAlchemy Session。传入时优先用数据库单位定义，
                    未传入或数据库无匹配时 fallback 到内置 BUILTIN_UNITS。
    """
    if db_session is not None:
        def _conv(val, code, cat): return convert_via_db(val, code, cat, db_session)
    else:
        _conv = convert

    out = dict(raw_case)
    # 压力
    if "p1" in out and out.get("p1_unit"):
        out["p1"] = _conv(out["p1"], out["p1_unit"], "pressure")
    if "p2" in out and out.get("p2_unit"):
        out["p2"] = _conv(out["p2"], out["p2_unit"], "pressure")
    # 温度
    if "t1" in out and out.get("t1_unit"):
        out["t1"] = _conv(out["t1"], out["t1_unit"], "temperature")
    if "t2" in out and out.get("t2_unit"):
        out["t2"] = _conv(out["t2"], out["t2_unit"], "temperature")
    # 流量
    if out.get("flow_mass") is not None and out.get("flow_mass_unit"):
        out["flow_mass"] = _conv(out["flow_mass"], out["flow_mass_unit"], "mass_flow")
    if out.get("flow_vol") is not None and out.get("flow_vol_unit"):
        cat = "vol_flow_liquid" if out.get("flow_unit") == "vol_liquid" else "vol_flow_gas"
        q_val = out["flow_vol"]
        q_unit = out["flow_vol_unit"]
        # 1) 先量纲换算到 m³/h (对 Nm3_h/Nm3_h_20/SCFM factor=1.0，值不变)
        q_op = _conv(q_val, q_unit, cat)
        # 2) 如果是气体标况/标准体积流量，按 P1/T1 修正到工况体积流量 m³/h
        #    V_op = V_std × (P_std / P_op) × (T_op_K / T_std_K)
        if out.get("flow_unit") == "vol" and cat == "vol_flow_gas":
            T_std_K = 273.15   # 默认 0℃ 标况 (IEC 60534)
            if "20" in q_unit:    # Nm3_h_20 等
                T_std_K = 293.15
            elif q_unit.upper().startswith("SCFM"):  # SCFM = 60°F ≈ 15.56℃
                T_std_K = 288.71
            if "Nm3" in q_unit or "nm3" in q_unit.lower() or "SCFM" in q_unit.upper():
                P_kpa = out.get("p1", 0) or 0.0
                T_c = out.get("t1", 0) or 0.0
                T_K = T_c + 273.15
                if P_kpa > 0 and T_K > 0:
                    q_op = q_op * (101.325 / P_kpa) * (T_K / T_std_K)
        out["flow_vol"] = q_op
    # 两相流量
    if out.get("mass_flow_gas") is not None and out.get("mass_flow_gas_unit"):
        out["mass_flow_gas"] = _conv(out["mass_flow_gas"], out["mass_flow_gas_unit"], "mass_flow")
    if out.get("mass_flow_liquid") is not None and out.get("mass_flow_liquid_unit"):
        out["mass_flow_liquid"] = _conv(out["mass_flow_liquid"], out["mass_flow_liquid_unit"], "mass_flow")
    # 密度（区分标况 kg/Nm3 与工况 kg/m3）
    if out.get("density_override") is not None and out.get("density_override_unit"):
        rho_val = out["density_override"]
        rho_unit = out["density_override_unit"]
        # 1) 先量纲换算到 kg/m3（对 kg_Nm3 factor=1.0，所以值不变）
        rho_op = _conv(rho_val, rho_unit, "density")
        # 2) 如果是标况密度（kg/Nm3 / kg.Nm3 / kgN m3 等变种），按 P1/T1 修正到工况密度
        if "Nm3" in rho_unit or "nm3" in rho_unit.lower():
            P_kpa = out.get("p1", 0) or 0.0
            T_c = out.get("t1", 0) or 0.0
            T_K = T_c + 273.15
            if P_kpa > 0 and T_K > 0:
                # ρ_op = ρ_std × (P_op / 101.325) × (273.15 / T_op_K)
                rho_op = rho_op * (P_kpa / 101.325) * (273.15 / T_K)
        out["density_override"] = rho_op
    if out.get("density_gas") is not None and out.get("density_gas_unit"):
        out["density_gas"] = _conv(out["density_gas"], out["density_gas_unit"], "density")
    if out.get("density_liquid") is not None and out.get("density_liquid_unit"):
        out["density_liquid"] = _conv(out["density_liquid"], out["density_liquid_unit"], "density")
    # 粘度
    if out.get("viscosity_override") is not None and out.get("viscosity_override_unit"):
        out["viscosity_override"] = _conv(out["viscosity_override"], out["viscosity_override_unit"], "viscosity")
    # 摩尔质量
    if out.get("molecular_weight_override") is not None and out.get("molecular_weight_override_unit"):
        out["molecular_weight_override"] = _conv(out["molecular_weight_override"], out["molecular_weight_override_unit"], "molecular_weight")
    # 管径/壁厚
    if out.get("pipe_diameter") is not None and out.get("pipe_diameter_unit"):
        out["pipe_diameter"] = _conv(out["pipe_diameter"], out["pipe_diameter_unit"], "diameter")
    if out.get("pipe_wall") is not None and out.get("pipe_wall_unit"):
        out["pipe_wall"] = _conv(out["pipe_wall"], out["pipe_wall_unit"], "wall_thickness")
    # 距离
    if out.get("distance") is not None and out.get("distance_unit"):
        out["distance"] = _conv(out["distance"], out["distance_unit"], "distance")

    # 清理 *_unit 字段（跳过特殊字段：flow_unit 不是值+单位格式，而是流量类型标记）
    _UNIT_SKIP = {"flow_unit"}
    to_remove = [k for k in out if k.endswith("_unit") and k not in _UNIT_SKIP]
    for k in to_remove:
        out.pop(k, None)

    return out


# ==================== 数据库种子 & 运行时加载 ====================

def get_default_unit_rows() -> list[dict]:
    """将 BUILTIN_UNITS 转换为 UnitDefinition 模型的初始种子数据。"""
    rows = []
    sort_map: dict[str, int] = {}
    for cat, code, label, factor, offset, is_pri, group, ptype in BUILTIN_UNITS:
        sort = sort_map.get(cat, 0)
        sort_map[cat] = sort + 1
        rows.append({
            "category": cat, "unit_code": code, "unit_label": label,
            "factor": factor, "offset": offset, "is_primary": is_pri,
            "unit_group": group, "pressure_type": ptype,
            "sort_order": sort, "is_active": True,
            "remark": "内置主单位" if is_pri else None,
        })
    return rows


def seed_unit_definitions(db_session) -> int:
    """初始化 unit_definitions 表：若为空则从 BUILTIN_UNITS 注入。"""
    from app.models import UnitDefinition
    if db_session.query(UnitDefinition).count() > 0:
        return 0
    rows = get_default_unit_rows()
    for r in rows:
        db_session.add(UnitDefinition(**r))
    db_session.commit()
    return len(rows)


def load_units_from_db(db_session) -> list[tuple]:
    """从数据库加载单位字典，返回 BUILTIN_UNITS 相同的 tuple 格式。"""
    from app.models import UnitDefinition
    rows = db_session.query(UnitDefinition).filter(
        UnitDefinition.is_active == True
    ).order_by(
        UnitDefinition.category, UnitDefinition.sort_order
    ).all()
    if not rows:
        return list(BUILTIN_UNITS)
    return [
        (r.category, r.unit_code, r.unit_label,
         r.factor, r.offset, bool(r.is_primary),
         r.unit_group or "metric", r.pressure_type)
        for r in rows
    ]


def convert_via_db(value: Optional[float], unit_code: str, category: str, db_session) -> Optional[float]:
    """基于数据库单位定义执行转换。"""
    from app.models import UnitDefinition
    if value is None or value == "":
        return None
    if unit_code is None:
        return float(value)
    row = db_session.query(UnitDefinition).filter(
        UnitDefinition.category == category,
        UnitDefinition.unit_code == unit_code,
    ).first()
    if row is None:
        return convert(value, unit_code, category)
    if row.factor is not None and row.factor < 0:
        return None
    return float(value) * (row.factor or 1.0) + (row.offset or 0.0)
