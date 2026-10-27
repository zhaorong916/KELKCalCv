"""Pydantic 数据模型(请求/响应)"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ---------- 项目 ----------
class ProjectBase(BaseModel):
    project_code: str = Field(..., max_length=64, description="项目编号")
    project_name: str = Field(..., max_length=200, description="项目名称")
    client: Optional[str] = None
    description: Optional[str] = None
    status: str = "进行中"

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    client: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class ProjectOut(ProjectBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    valve_count: int = 0


# ---------- 阀门(位号) ----------
class ValveBase(BaseModel):
    tag_no: str = Field(..., max_length=64, description="位号")
    valve_name: Optional[str] = None
    service: Optional[str] = None
    line_size: Optional[str] = None
    line_schedule: Optional[str] = None
    valve_type: Optional[str] = None
    reduced_port: bool = False
    status: str = "设计中"
    remark: Optional[str] = None

class ValveCreate(ValveBase):
    pass

class ValveUpdate(BaseModel):
    valve_name: Optional[str] = None
    service: Optional[str] = None
    line_size: Optional[str] = None
    line_schedule: Optional[str] = None
    valve_type: Optional[str] = None
    reduced_port: Optional[bool] = None
    status: Optional[str] = None
    remark: Optional[str] = None

class ValveOut(ValveBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    calc_count: int = 0
    current_version: Optional[int] = None


# ---------- 阀门配置参数 ----------
class ValveConfigSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    valve_style: str = "单座柱塞阀"
    flow_characteristic: Optional[str] = None
    port_diameter: Optional[float] = Field(None, description="阀座口径 mm")
    rated_cv: Optional[float] = Field(None, description="额定 Cv")
    fl: Optional[float] = Field(None, description="压力恢复系数 FL")
    flp: Optional[float] = None
    fp: Optional[float] = None
    xt: Optional[float] = Field(None, description="临界压差比 xT")
    xtp: Optional[float] = None
    fd: Optional[float] = Field(None, description="阀门类型修正系数 FD")
    stages: Optional[int] = Field(None, description="降噪级数 (1=单级, >1=多级降噪阀)")
    cv_table: Optional[str] = None
    curve_coeffs: Optional[dict] = Field(None, description="开度修正因子曲线多项式系数 (FL/Kc/Fd vs φ)")
    # 阀门选型字段
    nominal_dn: Optional[str] = None
    nominal_trim: Optional[str] = None
    flow_direction: Optional[str] = None
    trim_characteristics: Optional[str] = None
    trim_seat_type: Optional[str] = None
    pressure_rating: Optional[str] = None
    stroke_mm: Optional[float] = None
    rangeability: Optional[float] = None
    seat_type_front: Optional[str] = None
    seat_type_back: Optional[str] = None
    nominal_dn_back: Optional[str] = None
    # 设计数据卡片
    pipe_spec_front: Optional[str] = None
    pipe_spec_back: Optional[str] = None
    pipe_size_front: Optional[str] = None
    pipe_size_back: Optional[str] = None
    sch_front: Optional[str] = None
    sch_back: Optional[str] = None
    pipe_material_front: Optional[str] = None
    pipe_material_back: Optional[str] = None
    design_pressure: Optional[float] = None
    design_temp: Optional[float] = None
    close_dp: Optional[float] = None
    # 连接相关
    connection_type_front: Optional[str] = None
    connection_type_back: Optional[str] = None
    face_type_front: Optional[str] = None
    face_type_back: Optional[str] = None
    flange_standard_front: Optional[str] = None
    flange_standard_back: Optional[str] = None
    pipe_accessory_front: Optional[str] = None
    pipe_accessory_back: Optional[str] = None
    pipe_material_2_front: Optional[str] = None
    pipe_material_2_back: Optional[str] = None
    # 阀体属性
    body_material: Optional[str] = None
    bonnet_material: Optional[str] = None
    bonnet_form: Optional[str] = None
    jacket_connection: Optional[str] = None
    packing_type: Optional[str] = None
    packing_material: Optional[str] = None
    trim_material: Optional[str] = None
    seat_material: Optional[str] = None
    sleeve_material: Optional[str] = None
    stem_material: Optional[str] = None
    balance_seal_ring: Optional[str] = None
    # 曲线内部存储
    stroke_mode: Optional[str] = None
    eqcv: Optional[dict] = None
    fstk: Optional[float] = None

    @field_validator('eqcv', mode='before')
    @classmethod
    def parse_eqcv_json(cls, v):
        """eqcv 在 DB 中存为 Text(JSON字符串), 读取时自动解析为 dict"""
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v

    @field_validator('curve_coeffs', mode='before')
    @classmethod
    def parse_curve_coeffs_json(cls, v):
        """curve_coeffs 在 DB 中存为 Text(JSON字符串), 读取时自动解析为 dict"""
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


# ---------- 介质 ----------
class FluidBase(BaseModel):
    fluid_name: str = Field(..., max_length=128)
    fluid_name_cn: Optional[str] = Field(None, max_length=128, description="中文名称")
    specific_name: Optional[str] = None
    valtek_no: Optional[int] = None
    formula: Optional[str] = None
    default_state: str = "liquid"
    density_liquid: Optional[float] = None
    density_gas: Optional[float] = None
    molecular_weight: Optional[float] = None
    cp_cv_ratio: Optional[float] = None
    critical_pressure: Optional[float] = None
    critical_temp: Optional[float] = None
    boiling_point: Optional[float] = None
    acentric_factor: Optional[float] = None
    gf_constant: Optional[float] = None
    antoine_a: Optional[float] = None
    antoine_b: Optional[float] = None
    antoine_c: Optional[float] = None
    antoine_tmin_k: Optional[float] = None
    cp_a: Optional[float] = None
    cp_b: Optional[float] = None
    cp_c: Optional[float] = None
    cp_d: Optional[float] = None
    shomate_a: Optional[float] = None
    shomate_b: Optional[float] = None
    shomate_c: Optional[float] = None
    shomate_d: Optional[float] = None
    shomate_e: Optional[float] = None
    shomate_f: Optional[float] = None
    shomate_g: Optional[float] = None
    shomate_h: Optional[float] = None
    savage_c1: Optional[float] = None
    savage_c2: Optional[float] = None
    savage_c3: Optional[float] = None
    savage_c4: Optional[float] = None
    savage_c5: Optional[float] = None
    savage_c6: Optional[float] = None
    savage_c7: Optional[float] = None
    savage_c8: Optional[float] = None
    savage_c9: Optional[float] = None
    vapor_pressure: Optional[float] = None
    viscosity: Optional[float] = None
    temperature_base: float = 273.15
    pressure_base: float = 101.325
    is_water: bool = False
    remark: Optional[str] = None

class FluidCreate(FluidBase):
    pass

class FluidOut(FluidBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------- 管道数据 ----------
class PipeDataBase(BaseModel):
    lookup_key: Optional[str] = None
    nps_label: Optional[str] = None
    dn_mm: Optional[int] = None
    schedule: Optional[str] = None
    od_in: Optional[float] = None
    od_mm: Optional[float] = None
    thk_in: Optional[float] = None
    thk_mm: Optional[float] = None
    id_in: Optional[float] = None
    id_mm: Optional[float] = None

class PipeDataOut(PipeDataBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- 管道材料许用应力 (ASME B31.3 Table A-1) ----------
class PipeMaterialStressBase(BaseModel):
    material_code: str
    material_group: Optional[str] = None
    temp_c: float
    s_mpa: float
    min_use_temp_c: Optional[float] = None
    max_use_temp_c: Optional[float] = None
    notes: Optional[str] = None

class PipeMaterialStressOut(PipeMaterialStressBase):
    model_config = ConfigDict(from_attributes=True)
    id: int

class PipeMaterialSummaryOut(BaseModel):
    """材质清单（用于前端下拉框）"""
    material_code: str
    material_group: Optional[str] = None
    min_temp_c: Optional[float] = None
    max_temp_c: Optional[float] = None
    max_use_temp_c: Optional[float] = None
    temp_points: int
    notes: Optional[str] = None

class AllowableStressOut(BaseModel):
    """某一温度下的许用应力查询结果（含线性插值标记）"""
    material_code: str
    temp_c: float
    s_mpa: float
    interpolated: bool
    lower_temp_c: float
    upper_temp_c: float
    max_use_temp_c: Optional[float] = None

class SchCandidateOut(BaseModel):
    """单个 SCH 候选的壁厚校核结果"""
    schedule: str
    thk_mm: float
    id_mm: Optional[float] = None
    margin_mm: float
    ok: bool

class SuggestSchOut(BaseModel):
    """SCH 推荐结果（ASME B31.3 式 3a + 腐蚀裕 + 制造负偏差）"""
    dn_mm: int
    nps_label: Optional[str] = None
    od_mm: float
    material_code: str
    design_pressure_mpa: float
    design_temp_c: float
    allowable_stress_mpa: float
    weld_factor_e: float
    temp_factor_y: float
    corrosion_allowance_mm: float
    mill_tolerance: float
    pressure_thickness_mm: float
    required_thk_mm: float
    recommended_schedule: Optional[str] = None
    candidates: List[SchCandidateOut]
    note: str


# ---------- 阀门计算系数 ----------
class ValveSizingIndexBase(BaseModel):
    valve_type: str
    cv_per_d2: Optional[float] = None
    fl: Optional[float] = None
    xt: Optional[float] = None
    fd: Optional[float] = None
    kc: Optional[float] = None
    opt_pn: Optional[int] = None
    no_coefficient: Optional[str] = None
    aeta_db: Optional[float] = None
    stp: Optional[float] = None
    d_spl_sw_db: Optional[float] = None
    fd_flag: Optional[int] = None

class ValveSizingIndexOut(ValveSizingIndexBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- 阀门 Trim 尺寸/Cv ----------
class ValveTrimSizeBase(BaseModel):
    series_code: str
    asme_class: Optional[str] = None
    dn_inch: Optional[str] = None
    dn_mm: Optional[float] = None
    trim_inch: Optional[str] = None
    plug_mm: Optional[float] = None
    stroke_mm: Optional[float] = None
    trim_type: Optional[str] = None
    cv_min: Optional[float] = None
    cv_eq: Optional[float] = None
    cv_linear: Optional[float] = None
    cv_60deg: Optional[float] = None
    cv_90deg: Optional[float] = None
    cv_metal_seat: Optional[float] = None
    cv_soft_seat: Optional[float] = None
    stk_index_pct: Optional[float] = None
    remark: Optional[str] = None
    is_active: Optional[bool] = True

class ValveTrimSizeOut(ValveTrimSizeBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- 阀门系数多项式曲线 ----------
class ValveFactorCurveBase(BaseModel):
    factor_type: str
    eq_index: int
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    p0: Optional[float] = None
    p1: Optional[float] = None
    p2: Optional[float] = None
    p3: Optional[float] = None
    p4: Optional[float] = None
    p5: Optional[float] = None
    p6: Optional[float] = None
    a0: Optional[float] = None
    a1: Optional[float] = None
    a2: Optional[float] = None
    a3: Optional[float] = None
    a4: Optional[float] = None
    a5: Optional[float] = None
    a6: Optional[float] = None

class ValveFactorCurveOut(ValveFactorCurveBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- 计算版本 ----------
class CalculationCreate(BaseModel):
    version_label: Optional[str] = None
    calc_standard: str = "IEC60534"
    remark: Optional[str] = None

class CalculationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    valve_id: int
    version_no: int
    version_label: Optional[str] = None
    is_current: bool
    calc_standard: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    remark: Optional[str] = None


# ---------- 工艺工况 ----------
class ProcessCaseSchema(BaseModel):
    case_no: int = Field(..., ge=1, le=5, description="工况序号 1..5")
    case_name: Optional[str] = None
    fluid_id: Optional[int] = None
    fluid_name_custom: Optional[str] = Field(None, description="自定义介质名（未选基础库时填入，仅保存在计算快照中）")
    fluid_formula_custom: Optional[str] = Field(None, description="自定义介质分子式（可选）")
    fluid_state_override: Optional[str] = None
    flow_mass: Optional[float] = Field(None, description="质量流量")
    flow_vol: Optional[float] = Field(None, description="体积流量")
    flow_unit: str = "mass"
    p1: Optional[float] = Field(None, description="阀前绝压")
    p2: Optional[float] = Field(None, description="阀后绝压")
    t1: Optional[float] = Field(None, description="阀前温度")
    t2: Optional[float] = None
    # ---- 用户选择的单位代码（前端传入，后端转换后入库） ----
    p1_unit: Optional[str] = None
    p2_unit: Optional[str] = None
    t1_unit: Optional[str] = None
    t2_unit: Optional[str] = None
    flow_mass_unit: Optional[str] = None
    flow_vol_unit: Optional[str] = None
    # ---- 覆盖参数 ----
    density_override: Optional[float] = None
    viscosity_override: Optional[float] = None
    molecular_weight_override: Optional[float] = None
    gamma_override: Optional[float] = None
    density_override_unit: Optional[str] = None
    viscosity_override_unit: Optional[str] = None
    molecular_weight_override_unit: Optional[str] = None
    # ---- 管道参数 ----
    pipe_diameter: Optional[float] = None
    pipe_wall: Optional[float] = None
    pipe_schedule: Optional[str] = None
    pipe_diameter_unit: Optional[str] = None
    pipe_wall_unit: Optional[str] = None
    distance: float = 1.0
    distance_unit: Optional[str] = None
    downstream_density: Optional[float] = None
    is_active: bool = True
    # ---- 两相 ----
    mass_flow_gas: Optional[float] = None
    mass_flow_liquid: Optional[float] = None
    mass_flow_gas_unit: Optional[str] = None
    mass_flow_liquid_unit: Optional[str] = None
    twophase_method: str = "additive"
    density_gas: Optional[float] = None
    density_liquid: Optional[float] = None
    density_gas_unit: Optional[str] = None
    density_liquid_unit: Optional[str] = None

class ProcessCaseOut(ProcessCaseSchema):
    model_config = ConfigDict(from_attributes=True)
    id: int
    calculation_id: int


# ---------- 计算请求 ----------
class CalculateRequest(BaseModel):
    """整版本计算请求: 阀门配置 + 最多5组工况"""
    valve_config: ValveConfigSchema
    cases: List[ProcessCaseSchema] = Field(..., max_length=5)
    rated_cv_select: Optional[float] = Field(None, description="选用额定Cv(开度计算)")

class CaseResultOut(BaseModel):
    """运行计算返回的单工况完整结果（扁平字段）"""
    case_no: int
    case_name: Optional[str] = None
    fluid_name: str = ""
    phase: str = ""
    # Cv 结果（扁平）
    cv_required: Optional[float] = None
    cv_rated_selected: Optional[float] = None
    cv_opening: Optional[float] = None
    flow_regime: Optional[str] = None
    dp: Optional[float] = None
    dp_choked: Optional[float] = None
    x: Optional[float] = None
    y: Optional[float] = None
    reynolds: Optional[float] = None
    # 噪音结果（扁平）
    noise_dba: Optional[float] = None
    noise_freq_peak: Optional[float] = None
    # 物性 + 状态
    resolved_properties: dict = {}
    status: str = "成功"
    message: str = ""
    detail: Optional[dict] = None


# ---------- 计算结果保存 ----------
class CalcResultSave(BaseModel):
    case_no: int
    cv_required: Optional[float] = None
    cv_rated_selected: Optional[float] = None
    cv_opening: Optional[float] = None
    flow_regime: Optional[str] = None
    dp: Optional[float] = None
    dp_choked: Optional[float] = None
    x: Optional[float] = None
    x_t_eff: Optional[float] = None
    y: Optional[float] = None
    fl_eff: Optional[float] = None
    reynolds: Optional[float] = None
    fp: Optional[float] = None
    noise_dba: Optional[float] = None
    noise_freq_peak: Optional[float] = None
    noise_method: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    detail: Optional[str] = None


# ---------- 阀门产品系列 ----------
class ValveTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    series_code: str
    series_name: str
    valve_category: str
    product_line: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0
    # ---- 扩展字段（系数曲线组 / 默认 IEC 系数 / Trim 选项） ----
    factor_group: Optional[str] = None
    eq_index: Optional[int] = None
    fl_default: Optional[float] = None
    xt_default: Optional[float] = None
    fd_default: Optional[float] = None
    kc_default: Optional[float] = None
    trim_option_pressure: Optional[str] = None
    trim_option_opening: Optional[str] = None
    trim_option_types: Optional[str] = None


# ---------- 阀门额定Cv与行程 ----------
class ValveCvStkBase(BaseModel):
    series_code: str
    dn_label: str
    trim_label: str
    flow_char: Optional[str] = None
    trim_type: Optional[str] = None
    pressure_rating: Optional[str] = None
    seat_type: Optional[str] = None
    rated_cv: Optional[float] = None
    stroke_value: Optional[float] = None
    stroke_unit: Optional[str] = None
    plug_mm: Optional[float] = None
    stk_index: Optional[int] = None
    kfd: Optional[float] = None
    kfo: Optional[float] = None
    kfb: Optional[float] = None
    cv_min: Optional[float] = None


class ValveCvStkOut(ValveCvStkBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# 选型模块 Schema (P0.2)
# 依据: docs/选型模块优化方案.md v2.0
# ---------------------------------------------------------------------------


class SelectionRuleBase(BaseModel):
    rule_code: str = Field(..., max_length=64, description="规则编号")
    rule_name: str = Field(..., max_length=128, description="规则名称")
    category: str = Field(..., description="scope / constraint / preference / post_filter")
    target_series: str = Field(default="*", max_length=32, description="目标系列，* 表示全局")
    condition_expr: Optional[dict] = Field(None, description="JSON 条件表达式")
    condition_op: str = Field(default="and", description="and / or")
    action: str = Field(..., description="exclude / require / boost / set_field / flag / penalty")
    action_payload: Optional[dict] = Field(None, description="JSON 动作参数")
    priority: int = Field(default=10, description="优先级")
    source_ref: Optional[str] = Field(None, max_length=128, description="来源参考")
    is_active: bool = Field(default=True, description="是否启用")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"scope", "constraint", "preference", "post_filter"}
        if v not in allowed:
            raise ValueError(f"category 必须是 {allowed} 之一")
        return v

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"exclude", "require", "boost", "set_field", "flag", "penalty"}
        if v not in allowed:
            raise ValueError(f"action 必须是 {allowed} 之一")
        return v


class SelectionRuleCreate(SelectionRuleBase):
    pass


class SelectionRuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    category: Optional[str] = None
    target_series: Optional[str] = None
    condition_expr: Optional[dict] = None
    condition_op: Optional[str] = None
    action: Optional[str] = None
    action_payload: Optional[dict] = None
    priority: Optional[int] = None
    source_ref: Optional[str] = None
    is_active: Optional[bool] = None


class SelectionRuleOut(SelectionRuleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------- 选型输入/输出 ----------

class SelectionCaseIn(BaseModel):
    """单个工况的工艺参数（多工况综合选型）"""
    case_no: Optional[int] = None
    case_name: Optional[str] = None
    media: Optional[str] = None
    fluid_name: Optional[str] = None
    flow_rate: Optional[float] = None
    flow_rate_unit: Optional[str] = None
    p1: Optional[float] = None
    p1_unit: Optional[str] = None
    p2: Optional[float] = None
    p2_unit: Optional[str] = None
    t1: Optional[float] = None
    t1_unit: Optional[str] = None
    dp: Optional[float] = None
    pipe_size: Optional[float] = None
    pipe_size_unit: Optional[str] = None
    cv_required: Optional[float] = None


class SelectionInput(BaseModel):
    """选型输入（提交工艺条件）"""
    project_id: int
    valve_id: int
    media: str = Field(..., description="liquid / gas / twophase / steam")
    fluid_name: Optional[str] = None
    flow_rate: Optional[float] = Field(None, description="流量（按单位）")
    flow_rate_unit: Optional[str] = None
    p1: Optional[float] = Field(None, description="阀前压力（按 p1_unit）")
    p1_unit: Optional[str] = Field(None, description="压力单位代码, 默认按 kPa(A)")
    p2: Optional[float] = Field(None, description="阀后压力（按 p2_unit）")
    p2_unit: Optional[str] = Field(None, description="压力单位代码, 默认按 kPa(A)")
    t1: Optional[float] = Field(None, description="温度（按 t1_unit）")
    t1_unit: Optional[str] = Field(None, description="温度单位代码, 默认按 ℃")
    t2: Optional[float] = None
    dp: Optional[float] = Field(None, description="压差 kPa")
    pipe_size: Optional[float] = Field(None, description="管道尺寸（按 pipe_size_unit）")
    pipe_size_unit: Optional[str] = Field(None, description="管径单位代码, 默认按 mm")
    leakage_class: Optional[str] = Field(None, description="IV / V / VI")
    valve_action: Optional[str] = Field(None, description="modulating / on_off")
    special_req: Optional[dict] = Field(None, description="特殊要求: nace/fire_safe/low_temp/high_temp/copper_free 等")
    rangeability_required: Optional[float] = Field(None, description="可调比要求")
    cv_required: Optional[float] = Field(None, description="所需 Cv（可选，由流量反算）")
    cases: Optional[List[SelectionCaseIn]] = Field(None, description="多工况（综合判断），为空则按顶层字段单工况")
    main_case_index: Optional[int] = Field(0, description="主工况下标（0 起）")

    @field_validator("media")
    @classmethod
    def validate_media(cls, v: str) -> str:
        allowed = {"liquid", "gas", "twophase", "steam"}
        if v not in allowed:
            raise ValueError(f"media 必须是 {allowed} 之一")
        return v


class CandidateOut(BaseModel):
    """单个候选输出"""
    rank: int
    series_code: str
    series_name: Optional[str] = None
    dn_label: Optional[str] = None
    trim_label: Optional[str] = None
    flow_char: Optional[str] = None
    rated_cv: Optional[float] = None
    cv_min: Optional[float] = None
    opening: Optional[float] = None
    opening_max: Optional[float] = Field(None, description="多工况最不利（最大）开度")
    opening_min: Optional[float] = Field(None, description="多工况最小开度")
    case_openings: Optional[List[dict]] = Field(None, description="各工况开度明细")
    rangeability: Optional[float] = None
    score: int = 0
    applied_rules: List[str] = Field(default_factory=list)
    flags: Optional[dict] = Field(None, description="特殊标志，如 fd_mode")
    actuator_recommend: Optional[dict] = None  # P6 阶段填充


class SelectionResultOut(BaseModel):
    """选型结果输出"""
    candidates: List[CandidateOut]
    applied_rule_count: int = 0
    warnings: List[str] = Field(default_factory=list)


# ---------- 选型记录 ----------

class SelectionRecordBase(BaseModel):
    valve_id: int
    project_id: int
    input_snapshot: Optional[dict] = None
    candidates_json: Optional[List[dict]] = None
    selected_series: Optional[str] = None
    selected_config: Optional[dict] = None
    applied_rule_ids: Optional[str] = None


class SelectionRecordCreate(SelectionRecordBase):
    pass


class SelectionRecordOut(SelectionRecordBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
