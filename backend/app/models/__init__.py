"""数据库模型

层级关系：
项目 Project
  └─ 位号 Valve (以 tag_no 为索引)
       └─ 计算版本 Calculation (version_no 版本号)
            ├─ 阀门选型参数 ValveConfig (额定Cv/FL/xT/FD/阀型等)
            └─ 工艺工况 ProcessCase (单台最多5组 case_no 1..5)
                 ├─ 工艺参数(流量/进出口压力温度/介质状态)
                 └─ 计算结果 CalcResult (Cv/流态判定/噪音/详细中间量)

介质物性 Fluid：介质库配置，被 ProcessCase 引用
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Boolean,
    ForeignKey, UniqueConstraint, Index, DateTime as DateTimeType
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Project(Base):
    """项目"""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_code = Column(String(64), unique=True, nullable=False, index=True, comment="项目编号")
    project_name = Column(String(200), nullable=False, comment="项目名称")
    client = Column(String(200), comment="客户")
    description = Column(Text, comment="项目说明")
    status = Column(String(32), default="进行中", comment="状态")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    created_by = Column(String(64), default="admin", comment="创建人")

    valves = relationship("Valve", back_populates="project", cascade="all, delete-orphan")


class Valve(Base):
    """调节阀（位号）—— 项目内以 tag_no 为索引"""
    __tablename__ = "valves"
    __table_args__ = (
        UniqueConstraint("project_id", "tag_no", name="uq_project_tag"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_no = Column(String(64), nullable=False, comment="位号(仪表编号)，项目内唯一")
    valve_name = Column(String(200), comment="阀门名称/描述")
    service = Column(String(200), comment="用途/服务介质描述")
    line_size = Column(String(32), comment="管道规格")
    line_schedule = Column(String(32), comment="管道壁厚等级")
    valve_type = Column(String(64), comment="阀门类型(单座/套筒/球阀/蝶阀等)")
    reduced_port = Column(Boolean, default=False, comment="是否缩径")
    status = Column(String(32), default="设计中", comment="状态")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    remark = Column(Text, comment="备注")

    project = relationship("Project", back_populates="valves")
    calculations = relationship("Calculation", back_populates="valve", cascade="all, delete-orphan")


class Calculation(Base):
    """计算版本——同一台阀门多次计算有版本号"""
    __tablename__ = "calculations"
    __table_args__ = (
        UniqueConstraint("valve_id", "version_no", name="uq_valve_version"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    valve_id = Column(Integer, ForeignKey("valves.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no = Column(Integer, nullable=False, comment="版本号，从1递增")
    version_label = Column(String(64), comment="版本标识/说明")
    is_current = Column(Boolean, default=True, comment="是否当前生效版本")
    calc_standard = Column(String(64), default="IEC60534", comment="计算标准(IEC60534/GBT17213/ISA75.01)")
    status = Column(String(32), default="草稿", comment="状态: 草稿/已计算/已归档")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(String(64), default="admin")
    remark = Column(Text)

    valve = relationship("Valve", back_populates="calculations")
    valve_config = relationship("ValveConfig", back_populates="calculation", uselist=False, cascade="all, delete-orphan")
    process_cases = relationship("ProcessCase", back_populates="calculation", cascade="all, delete-orphan", order_by="ProcessCase.case_no")


class ValveConfig(Base):
    """阀门选型/配置参数（额定Cv、压力恢复系数FL、临界压差比xT等）

    依据 IEC 60534-2-1 / GB/T 17213.2，阀门系数由厂家样本或 IEC 典型值给出。
    """
    __tablename__ = "valve_configs"
    __table_args__ = (
        UniqueConstraint("calculation_id", name="uq_calc_config"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    calculation_id = Column(Integer, ForeignKey("calculations.id", ondelete="CASCADE"), nullable=False)
    valve_style = Column(String(64), default="单座柱塞阀", comment="阀门结构形式")
    flow_characteristic = Column(String(32), comment="流量特性: 等百分比/线性/快开")
    port_diameter = Column(Float, comment="阀座口径 mm")
    rated_cv = Column(Float, comment="额定Cv")
    fl = Column(Float, comment="无附件液阻压力恢复系数 FL")
    flp = Column(Float, comment="带附件液阻压力恢复系数 FLp")
    fp = Column(Float, comment="管件几何系数 Fp")
    xt = Column(Float, comment="无附件临界压差比系数 xT")
    xtp = Column(Float, comment="带附件临界压差比系数 xTp")
    fd = Column(Float, comment="阀门类型修正系数 FD")
    stages = Column(Integer, nullable=False, default=1, comment="降噪级数 (1=单级, >1=多级降噪阀)")
    cv_table = Column(Text, comment="可选: 行程-Cv 特性曲线 JSON")
    curve_coeffs = Column(Text, comment="开度修正因子曲线多项式系数 JSON (FL/Kc/Fd vs φ)")
    # === 阀门选型字段 ===
    nominal_dn = Column(String(32), comment="阀门口径 (JIS A, 如 40A)")
    nominal_trim = Column(String(32), comment="阀芯尺寸 (JIS A)")
    flow_direction = Column(String(16), comment="流向: FTO/FTC")
    trim_characteristics = Column(String(32), comment="流量特性: EQ%/Linear")
    trim_seat_type = Column(String(64), comment="阀内件形式")
    pressure_rating = Column(String(32), comment="压力等级")
    stroke_mm = Column(Float, comment="行程 mm")
    rangeability = Column(Float, comment="可调比 R")
    seat_type_front = Column(String(64), comment="阀座形式(阀前)")
    seat_type_back = Column(String(64), comment="阀座形式(阀后)")
    nominal_dn_back = Column(String(32), comment="阀门口径(阀后)")
    # === 设计数据卡片 ===
    pipe_spec_front = Column(String(128), comment="管道规格(阀前, pipe_data.lookup_key)")
    pipe_spec_back = Column(String(128), comment="管道规格(阀后)")
    pipe_size_front = Column(String(64), comment="管道尺寸(阀前, nps_label)")
    pipe_size_back = Column(String(64), comment="管道尺寸(阀后)")
    sch_front = Column(String(16), comment="管道SCH(阀前)")
    sch_back = Column(String(16), comment="管道SCH(阀后)")
    pipe_wall_front = Column(String(64), comment="管道壁厚(阀前, 显示用字符串)")
    pipe_wall_back = Column(String(64), comment="管道壁厚(阀后, 显示用字符串)")
    pipe_material_front = Column(String(64), comment="管道材质(阀前)")
    pipe_material_back = Column(String(64), comment="管道材质(阀后)")
    design_pressure = Column(Float, comment="设计压力 MPa(G)")
    design_temp = Column(Float, comment="设计温度 °C")
    close_dp = Column(Float, comment="关闭压差 MPa")
    # === 阀门选型数据 - 连接相关 ===
    connection_type_front = Column(String(64), comment="连接形式(阀前)")
    connection_type_back = Column(String(64), comment="连接形式(阀后)")
    face_type_front = Column(String(32), comment="密封面形式(阀前)")
    face_type_back = Column(String(32), comment="密封面形式(阀后)")
    flange_standard_front = Column(String(64), comment="法兰标准(阀前)")
    flange_standard_back = Column(String(64), comment="法兰标准(阀后)")
    pipe_accessory_front = Column(String(128), comment="接管附件(阀前)")
    pipe_accessory_back = Column(String(128), comment="接管附件(阀后)")
    pipe_material_2_front = Column(String(64), comment="接管材质(阀前)")
    pipe_material_2_back = Column(String(64), comment="接管材质(阀后)")
    # === 阀体属性 ===
    body_material = Column(String(64), comment="阀体材质")
    bonnet_material = Column(String(64), comment="阀盖材质")
    bonnet_form = Column(String(64), comment="阀盖形式")
    jacket_connection = Column(String(64), comment="夹套连接")
    packing_type = Column(String(64), comment="填料类型")
    packing_material = Column(String(64), comment="填料材质")
    trim_material = Column(String(64), comment="阀芯材质")
    seat_material = Column(String(64), comment="阀座材质")
    sleeve_material = Column(String(64), comment="套筒材质")
    stem_material = Column(String(64), comment="阀杆材质")
    balance_seal_ring = Column(String(64), comment="平衡密封环")
    # === 曲线内部存储 ===
    stroke_mode = Column(String(32), comment="曲线模式")
    eqcv = Column(Text, comment="EQ%曲线系数 JSON")
    fstk = Column(Float, comment="等比分值")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    calculation = relationship("Calculation", back_populates="valve_config")


class Fluid(Base):
    """介质物性配置（介质库）

    state: liquid / gas 介质相态
    自动判定：水的状态由 ProcessCase 录入温度压力按饱和曲线自动判定

    扩展字段来源于 Noise 2.3.xlsm / FluidData 页签（Valtek Engineering Data），
    用于后续计算引擎精化： Antoine 蒸汽压、Savage/Kyle/Shomate 比热多项式、
    偏心因子 ω、压缩因子 GFB 与沸点 TB 等。
    """
    __tablename__ = "fluids"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fluid_name = Column(String(128), nullable=False, unique=True, index=True, comment="介质英文名称(匹配 ValveData/Excel 引用)")
    fluid_name_cn = Column(String(128), index=True, comment="介质中文名称（来自中英文对照）")
    specific_name = Column(String(128), comment="Specific Name（FluidData 页签列B别名）")
    valtek_no = Column(Integer, comment="Valtek 编号")
    formula = Column(String(64), comment="分子式")
    default_state = Column(String(16), default="liquid", comment="默认相态 liquid/gas/twophase")
    density_liquid = Column(Float, comment="液相密度 kg/m³(标况)")
    density_gas = Column(Float, comment="气相密度 kg/m³(标况 1atm 0℃)")
    molecular_weight = Column(Float, comment="摩尔质量 kg/kmol (= MW)")
    cp_cv_ratio = Column(Float, comment="比热比 γ=cp/cv (=k)")
    critical_pressure = Column(Float, comment="临界压力 kPa(abs) = Pc(barA)×100")
    critical_temp = Column(Float, comment="临界温度 K (= Tc)")
    boiling_point = Column(Float, comment="正常沸点 K (= TB)")
    acentric_factor = Column(Float, comment="偏心因子 ω")
    gf_constant = Column(Float, comment="Gf 常数 GFB（用于气体密度/压缩因子插值）")
    antoine_a = Column(Float, comment="Antoine 系数 A  [Pv(barA)=exp(A-B/(T(K)+C))]")
    antoine_b = Column(Float, comment="Antoine 系数 B")
    antoine_c = Column(Float, comment="Antoine 系数 C")
    antoine_tmin_k = Column(Float, comment="Antoine 方程适用下限温度 K")
    # 比热多项式 - Kyle (气体 Cp0 kJ/kg·K = a + b·T + c·T² + d·T³, T in K)
    cp_a = Column(Float)
    cp_b = Column(Float)
    cp_c = Column(Float)
    cp_d = Column(Float)
    # 比热多项式 - Shomate 气体 Cp = A + B·t + C·t² + D·t³ + E/t²  (t = T(K)/1000)
    shomate_a = Column(Float)
    shomate_b = Column(Float)
    shomate_c = Column(Float)
    shomate_d = Column(Float)
    shomate_e = Column(Float)
    shomate_f = Column(Float)
    shomate_g = Column(Float)
    shomate_h = Column(Float)
    # 比热多项式 - Savage 液体 Cp = C1 + C2·Tc + C3·Tc² + C4/(1-Tc)² ... (Tc 对比温度)
    savage_c1 = Column(Float)
    savage_c2 = Column(Float)
    savage_c3 = Column(Float)
    savage_c4 = Column(Float)
    savage_c5 = Column(Float)
    savage_c6 = Column(Float)
    savage_c7 = Column(Float)
    savage_c8 = Column(Float)
    savage_c9 = Column(Float)
    # 通用字段
    vapor_pressure = Column(Float, comment="饱和蒸汽压 kPa(abs) @工况温度")
    viscosity = Column(Float, comment="动力粘度 cP / μPa·s")
    temperature_base = Column(Float, default=273.15, comment="物性参考温度 K")
    pressure_base = Column(Float, default=101.325, comment="物性参考压力 kPa(abs)")
    is_water = Column(Boolean, default=False, comment="是否水/水蒸汽(自动判定相态)")
    remark = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ProcessCase(Base):
    """工艺工况——单台阀门最多5组(case_no 1..5)

    每组包含完整工艺参数与对应计算结果。
    """
    __tablename__ = "process_cases"
    __table_args__ = (
        UniqueConstraint("calculation_id", "case_no", name="uq_calc_case"),
        Index("ix_calc_case", "calculation_id", "case_no"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    calculation_id = Column(Integer, ForeignKey("calculations.id", ondelete="CASCADE"), nullable=False, index=True)
    case_no = Column(Integer, nullable=False, comment="工况序号 1..5")
    case_name = Column(String(128), comment="工况名称: 最大/正常/最小/开工/事故")

    # 介质 —— fluid_id 可选（未选基础库时为 NULL，使用 fluid_name_custom 提供自定义名）
    fluid_id = Column(Integer, ForeignKey("fluids.id"), nullable=True)
    fluid_name_custom = Column(String(128), comment="自定义介质名（未选基础库时填入）")
    fluid_formula_custom = Column(String(64), comment="自定义介质分子式（可选）")
    fluid_state_override = Column(String(16), comment="相态覆盖 liquid/gas; 留空按介质自动判定")

    # 流量（存储值已按录入单位转换为内部统一单位）
    flow_mass = Column(Float, comment="质量流量 kg/h(内部单位)")
    flow_vol = Column(Float, comment="体积流量 m³/h(液) 或 Nm³/h(气标况,内部单位)")
    flow_unit = Column(String(16), default="mass", comment="流量录入方式 mass/vol")

    # 压力温度（存储值已按录入单位转换为内部统一单位）
    p1 = Column(Float, comment="阀前绝压 kPa(abs,内部单位)")
    p2 = Column(Float, comment="阀后绝压 kPa(abs,内部单位)")
    t1 = Column(Float, comment="阀前温度 ℃(内部单位)")
    t2 = Column(Float, comment="阀后温度 ℃(内部单位)")

    # 单位选择（记录用户录入时选用的单位，用于界面反显）
    p1_unit = Column(String(32), default="kPa")
    p2_unit = Column(String(32), default="kPa")
    t1_unit = Column(String(32), default="C")
    t2_unit = Column(String(32), default="C")
    flow_mass_unit = Column(String(32), default="kg_h")
    flow_vol_unit = Column(String(32), default="m3_h")
    mass_flow_gas_unit = Column(String(32), default="kg_h")
    mass_flow_liquid_unit = Column(String(32), default="kg_h")
    pipe_diameter_unit = Column(String(32), default="mm")
    pipe_wall_unit = Column(String(32), default="mm")
    distance_unit = Column(String(32), default="m")
    density_override_unit = Column(String(32), default="kg_m3")
    viscosity_override_unit = Column(String(32), default="cP")
    molecular_weight_override_unit = Column(String(32), default="kg_kmol")
    density_gas_unit = Column(String(32), default="kg_m3")
    density_liquid_unit = Column(String(32), default="kg_m3")

    # 工况密度/粘度(可选覆盖介质库默认值，存储值已转换)
    density_override = Column(Float, comment="工况密度覆盖 kg/m³(内部单位)")
    viscosity_override = Column(Float, comment="工况粘度覆盖 cP(内部单位)")
    molecular_weight_override = Column(Float, comment="摩尔质量覆盖(内部单位 kg/kmol)")
    gamma_override = Column(Float, comment="比热比覆盖(无量纲)")

    # 噪音相关（存储值已转换）
    pipe_diameter = Column(Float, comment="下游管道内径 mm(内部单位)")
    pipe_wall = Column(Float, comment="管道壁厚 mm(内部单位)")
    pipe_schedule = Column(String(32), comment="管道壁厚等级(可选用)")
    distance = Column(Float, default=1.0, comment="噪音测点距离 m(内部单位)")
    downstream_density = Column(Float, comment="下游介质密度(内部单位 kg/m³)")

    # 两相流参数（存储值已转换）
    mass_flow_gas = Column(Float, comment="气相质量流量 kg/h(两相,内部单位)")
    mass_flow_liquid = Column(Float, comment="液相质量流量 kg/h(两相,内部单位)")
    twophase_method = Column(String(32), default="additive", comment="两相计算方法 additive/homogeneous")
    density_gas = Column(Float, comment="两相气相密度 kg/m³(内部单位)")
    density_liquid = Column(Float, comment="两相液相密度 kg/m³(内部单位)")

    is_active = Column(Boolean, default=True, comment="是否参与计算")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    calculation = relationship("Calculation", back_populates="process_cases")
    fluid = relationship("Fluid")
    result = relationship("CalcResult", back_populates="process_case", uselist=False, cascade="all, delete-orphan")


class CalcResult(Base):
    """计算结果（每组工况一行）"""
    __tablename__ = "calc_results"
    __table_args__ = (
        UniqueConstraint("process_case_id", name="uq_case_result"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    process_case_id = Column(Integer, ForeignKey("process_cases.id", ondelete="CASCADE"), nullable=False)

    # Cv 计算结果
    cv_required = Column(Float, comment="所需Cv")
    cv_rated_selected = Column(Float, comment="选用额定Cv")
    cv_opening = Column(Float, comment="开度 %")
    flow_regime = Column(String(64), comment="流态判定: 非阻塞/阻塞/闪蒸/空化/临界")

    # 中间量
    dp = Column(Float, comment="压差 kPa")
    dp_choked = Column(Float, comment="临界压差 kPa")
    x = Column(Float, comment="压差比 x=ΔP/P1")
    x_t_eff = Column(Float, comment="有效临界压差比")
    y = Column(Float, comment="膨胀系数 Y")
    fl_eff = Column(Float, comment="有效FL")
    reynolds = Column(Float, comment="雷诺数")
    fp = Column(Float, comment="管件几何系数 Fp")

    # 噪音
    noise_dba = Column(Float, comment="A计权声压级 dB(A)")
    noise_freq_peak = Column(Float, comment="峰值频率 Hz")
    noise_method = Column(String(64), comment="噪音计算方法: IEC60534-8-3/8-4")

    # 状态
    status = Column(String(32), comment="计算状态: 成功/警告/失败")
    message = Column(Text, comment="警告/错误信息")
    detail = Column(Text, comment="详细中间过程 JSON")
    calculated_at = Column(DateTime, default=datetime.now)

    process_case = relationship("ProcessCase", back_populates="result")


class User(Base):
    """用户(轻量级，MVP 内置管理员即可)"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    display_name = Column(String(64))
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default="engineer")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class ValveType(Base):
    """KELK 阀门产品系列字典

    用于阀门选型时下拉选择结构形式（型号系列）。
    数据来源：KELK 产品系列样本。
    """
    __tablename__ = "valve_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_code = Column(String(32), nullable=False, unique=True, index=True, comment="产品系列代码，如 GC120/BT210")
    series_name = Column(String(128), nullable=False, comment="系列名称，如 套筒导向型单座调节阀")
    valve_category = Column(String(32), nullable=False, comment="阀门大类: globe/ball/butterfly")
    product_line = Column(String(32), nullable=True, comment="产品大类: 调节阀/球阀/蝶阀/闸阀")
    factor_group = Column(String(255), nullable=True, comment="系数曲线组(对应Eq%/FL/Kc/Fd Index)")
    eq_index = Column(Integer, nullable=True, comment="默认行程系数曲线 Eq% Index 1..N")
    fl_default = Column(Float, nullable=True, comment="默认液阻压力恢复系数 FL (与额定Cv对应的典型值)")
    xt_default = Column(Float, nullable=True, comment="默认临界压差比系数 xT")
    fd_default = Column(Float, nullable=True, comment="默认阀门型式修正系数 FD")
    kc_default = Column(Float, nullable=True, comment="默认空化系数 Kc")
    trim_option_pressure = Column(String(255), nullable=True, comment="系列支持的压力等级 (如 150#,300#)")
    trim_option_opening  = Column(String(255), nullable=True, comment="支持的开启角度/行程 (如 60 Deg, 90 Deg)")
    trim_option_types    = Column(String(255), nullable=True, comment="支持的 Trim 类型 (Damper / 15 Deg Sealed 等)")
    description = Column(Text, comment="应用说明")
    is_active = Column(Boolean, default=True, comment="是否启用")
    sort_order = Column(Integer, default=0, comment="排序值")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class UnitDefinition(Base):
    """单位字典配置（可选单位范围可由用户通过数据表设置）

    所有录入参数先按此处定义的 factor/offset 转换为系统内部统一单位，
    再送入计算引擎。is_primary=True 的记录即为该类别的内部主单位。

    压力单位区分绝压(absolute)/表压(gauge)：
      绝压: result = value × factor + offset(=0)
      表压: result = value × factor + offset(=101.325, 即1个大气压kPa)
    """
    __tablename__ = "unit_definitions"
    __table_args__ = (
        Index("ix_unit_cat_active", "category", "is_active"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(32), nullable=False, index=True, comment="参数类别: pressure/temperature/mass_flow/...")
    unit_code = Column(String(32), nullable=False, comment="单位代码，如 kPaA/barG/C/F")
    unit_label = Column(String(64), nullable=False, comment="界面显示标签，如 kPa(abs)/bar(表)/℃")
    factor = Column(Float, nullable=False, default=1.0, comment="转换系数: value * factor + offset → 内部单位")
    offset = Column(Float, nullable=False, default=0.0, comment="转换偏移量（温度/表压等场景）")
    unit_group = Column(String(16), default="metric", comment="单位制: metric(公制) / imperial(英制)")
    pressure_type = Column(String(16), nullable=True, comment="压力类型: absolute(绝压) / gauge(表压) / NULL(非压力)")
    is_primary = Column(Boolean, default=False, comment="是否该类别的内部主单位(转换目标)")
    sort_order = Column(Integer, default=0, comment="排序值，数字越小越靠前")
    is_active = Column(Boolean, default=True, comment="是否启用，false 时从下拉框隐藏")
    remark = Column(String(200), comment="备注")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ---------------------------------------------------------------------------
# 管道尺寸表：来源于 Noise 2.3.xlsm / PipeData 页签
# ---------------------------------------------------------------------------
class PipeData(Base):
    """管道规格数据（ASME B36.10 / B36.19M 常用 NPS 与 Sch 组合）

    数据来源于 Noise 2.3.xlsm / PipeData 页签。
    录入时支持直接根据 NPS + Schedule 自动查询 OD / Thk / ID，
    避免用户自行查表。
    """
    __tablename__ = "pipe_data"
    __table_args__ = (
        UniqueConstraint("nps_label", "schedule", name="uq_nps_sch"),
        Index("ix_nps_sch", "nps_label", "schedule"),
        Index("ix_dn_sch", "dn_mm", "schedule"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    lookup_key = Column(String(64), unique=True, index=True, comment="Excel 原始查找键, 如 '0.5in (12mm), Schd 40'")
    nps_label = Column(String(16), comment="NPS 英寸标注, 如 0.5 / 1 / 2 / 24")
    dn_mm = Column(Integer, index=True, comment="公制 DN mm, 如 15 / 25 / 50 / 600")
    schedule = Column(String(16), comment="壁厚等级, 如 10S / 40 / 40S / STD / 80 / XS / XXS")
    od_in = Column(Float, comment="外径 in.")
    od_mm = Column(Float, comment="外径 mm (= 25.4 * od_in)")
    thk_in = Column(Float, comment="壁厚 in.")
    thk_mm = Column(Float, comment="壁厚 mm (= 25.4 * thk_in)")
    id_in = Column(Float, comment="内径 in.")
    id_mm = Column(Float, comment="内径 mm (= 25.4 * id_in)")
    note_col_e = Column(Float, comment="Excel 列E 保留(噪音 TL 辅助值)")
    note_col_f = Column(Float, comment="Excel 列F 保留(管壁厚等级辅助值)")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ---------------------------------------------------------------------------
# 阀门计算系数表：来源于 Noise 2.3.xlsm / ValveData 页签
# ---------------------------------------------------------------------------
class ValveSizingIndex(Base):
    """阀门选型系数（Cv/d²、FL、xT、FD、Kc 及噪音计算关键指标）

    数据来源：Noise 2.3.xlsm / ValveData 页签 "Table 1. Valve Sizing Indices"。
    其中：
      - Cv/d² 用于由 Cv 反推阀芯直径 d(mm)：d = 25.4 * sqrt(Cv / (Cv/d²))
      - FL/xT/Kc 参与 IEC 60534-2-1 Cv 阻塞流判定
      - No/Aeta/Stp/dSPLsw 参与 IEC 60534-8-3 气动噪音计算
      - fd_labeled 指示该阀门是否可按 FD 公式进行声功率修正
    """
    __tablename__ = "valve_sizing_indices"
    __table_args__ = (
        UniqueConstraint("valve_type", name="uq_valve_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    valve_type = Column(String(128), nullable=False, unique=True, index=True,
                        comment="Valve Type 原始名称, 与 Excel/界面选择一致")
    cv_per_d2 = Column(Float, comment="Cv/d²  (流量密度系数, d 单位 in)")
    fl = Column(Float, comment="无附件液阻压力恢复系数 FL")
    xt = Column(Float, comment="无附件临界压差比系数 xT")
    fd = Column(Float, comment="阀门型式修正系数 FD (射流直径修正)")
    kc = Column(Float, comment="空化系数 Kc")
    opt_pn = Column(Integer, comment="OptPn 优化路径编号 (1=流道, 2=阀芯)")
    no_coefficient = Column(String(32), comment="No (噪音编号) 或 Calc'd")
    aeta_db = Column(Float, comment="Aeta 声功率效率修正 dB (=10·log10 η_ref)")
    stp = Column(Float, comment="Stp 斯特劳哈尔数 St = f·d/U")
    d_spl_sw_db = Column(Float, comment="dSPLsw 管壁/路径附加修正 dB")
    fd_flag = Column(Integer, comment="FD? 是否启用 FD 修正标志 0/1")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ---------------------------------------------------------------------------
# 额定阀门内径矩阵（按 Class 压力等级 / 通径 查表）
# 来源于 Noise 2.3.xlsm / ValveData 下半段 Nominal Valve Size 矩阵
# 用于 Excel 中 VLOOKUP(E27,ValveData!A28:C51,3) 查 NVS 阀腔直径
# ---------------------------------------------------------------------------
class ValveNominalSize(Base):
    __tablename__ = "valve_nominal_sizes"
    __table_args__ = (
        UniqueConstraint("size_label", name="uq_valve_size_label"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    size_label = Column(String(32), unique=True, index=True, comment="通径标签如 0.5in (15mm)")
    nps_in = Column(Float, comment="NPS in.")
    dn_mm = Column(Integer, index=True, comment="DN mm")
    # 各压力等级下阀腔内径 mm（Class 150/300/600/900/1500/2500/4500）
    id_class_150 = Column(Float)
    id_class_300 = Column(Float)
    id_class_600 = Column(Float)
    id_class_900 = Column(Float)
    id_class_1500 = Column(Float)
    id_class_2500 = Column(Float)
    id_class_4500 = Column(Float)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ---------------------------------------------------------------------------
# 公称尺寸对照表 (Nominal Size Reference)
# 英制 in ↔ 公制 mm ↔ JIS A ↔ DN 的相互映射
# ---------------------------------------------------------------------------
class NominalSizeRef(Base):
    __tablename__ = "nominal_size_refs"
    __table_args__ = (
        UniqueConstraint("dn_mm", name="uq_nominal_dn_mm"),
        Index("ix_nominal_in", "nps_in"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    nps_in = Column(String(16), nullable=False, index=True, comment="公称尺寸英制 in 标签: 1/4, 1, 1 1/2, 4")
    nps_in_decimal = Column(Float, comment="nps_in 换算为小数, 如 1/4→0.25, 1 1/2→1.5")
    dn_mm = Column(Float, nullable=True, index=True, comment="公称直径 mm: 6, 25, 100, 1.6")
    jis_a = Column(String(16), comment="JIS A 标注: 25A, 100A")
    dn_label = Column(String(16), comment="DN 标注: DN25, DN100 (部分小尺寸无 DN)")
    sort_order = Column(Integer, default=0, comment="按 nps_in_decimal 升序")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ---------------------------------------------------------------------------
# 阀门系数多项式曲线 (Eq% 行程曲线 / FL / Kc / Fd 曲线)
# 来源于 KELK CalcCv Valve & Trim Factors.xlsm: Eq% Data / FL Data / Kc Data / Fd Data
# 每条曲线由 eq_index 编号，f(x)=P4·x⁴+P3·x³+P2·x²+P1·x+P0 (FL/Kc/Fd)
# Eq% 曲线则使用 A0~A6: f(x)=A6·x⁶+A5·x⁵+...+A0
# ---------------------------------------------------------------------------
class ValveFactorCurve(Base):
    __tablename__ = "valve_factor_curves"
    __table_args__ = (
        UniqueConstraint("factor_type", "eq_index", name="uq_factor_type_eq_index"),
        Index("ix_factor_type", "factor_type"),
    )
    FACTOR_EQCV = "eqcv"   # 等百分比行程曲线 (A0~A6)
    FACTOR_FL = "fl"       # 液体压力恢复 FL (P0~P4)
    FACTOR_KC = "kc"       # 空化系数 Kc (P0~P4)
    FACTOR_FD = "fd"       # 阀门型式修正 FD (P0~P4)

    id = Column(Integer, primary_key=True, autoincrement=True)
    factor_type = Column(String(16), nullable=False, index=True, comment="eqcv / fl / kc / fd")
    eq_index = Column(Integer, nullable=False, comment="Eq% Index 1..N，同 valve_types.eq_index")
    value_min = Column(Float, comment="该 index 对应最小系数值 (FL/Kc/Fd 的最小值)")
    value_max = Column(Float, comment="该 index 对应最大系数值")
    # 4 次多项式系数 (FL/Kc/Fd 使用)
    p0 = Column(Float, comment="常数项 x^0")
    p1 = Column(Float, comment="一次项 x^1")
    p2 = Column(Float, comment="二次项 x^2")
    p3 = Column(Float, comment="三次项 x^3")
    p4 = Column(Float, comment="四次项 x^4")
    p5 = Column(Float, comment="五次项 (预留)")
    p6 = Column(Float, comment="六次项 (eqcv 使用 A6)")
    # 六次多项式系数别名 (Eq% 使用 A0~A6)
    a0 = Column(Float, comment="Eq% A0 (等同 P0)")
    a1 = Column(Float, comment="Eq% A1 (等同 P1)")
    a2 = Column(Float, comment="Eq% A2 (等同 P2)")
    a3 = Column(Float, comment="Eq% A3 (等同 P3)")
    a4 = Column(Float, comment="Eq% A4 (等同 P4)")
    a5 = Column(Float, comment="Eq% A5 (等同 P5)")
    a6 = Column(Float, comment="Eq% A6 (等同 P6)")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ---------------------------------------------------------------------------
# 阀门 Trim / Cv 表格 (Series × ASME Class × DN × Trim Size → Stroke + Rated Cv)
# 每行是一条完整记录，不同系列结构不同：
#   GC120/GC210: asme + dn + trim_inch + plug + stroke + cv_eq + cv_linear
#   BT120/BT210: asme + dn + cv_min + cv_60deg + cv_90deg + stk_index
#   BC110/BE120: dn + cv_min + cv_metal_seat + cv_soft_seat + stk_index
#   GV120/GV410: asme + dn + trim_type + stroke + plug (无 Cv)
#   GV110: dn + cv_min + cv_rated + stroke + plug
# 来源于 KELK CalcCv Valve & Trim Factors.xlsm 的每个 Series Sheet
# ---------------------------------------------------------------------------
class ValveTrimSize(Base):
    """阀门 Trim / Cv 表格 (Series × ASME Class × DN × Trim Size → Stroke + Rated Cv + Plug Size Range)

    GV120 系列的完整数据结构:
      Table 1: Trim Type + Pressure Rating + Nominal Valve Size → Stroke + Plug Size Min/Max
      Table 2: Trim Type + Plug Size → Minimum Cv + Rated Cv + %Stk Index
    本表整合 Table1 的 dn 级别记录 (含 plug_min_mm/plug_max_mm) 和
    Table2 的 plug 级别记录 (含 cv_min/cv_eq/stk_index)。

    其他系列 (GC120/GC210/BT120/BT210/GV110 等) 沿用原结构。
    """
    __tablename__ = "valve_trim_sizes"
    __table_args__ = (
        Index("ix_trim_series", "series_code"),
        Index("ix_trim_dn", "series_code", "asme_class", "dn_mm"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    series_code = Column(String(32), nullable=False, index=True, comment="阀门系列代码, 如 GC120")
    asme_class = Column(String(16), comment="ASME 压力等级: to 600# / 900# / 1500# / 2500# / 150# / 300#")
    dn_inch = Column(String(16), comment="公称口径 in 标签, 如 1, 1 1/2, 3/4")
    dn_mm = Column(Float, comment="公称直径 mm, 如 25 / 40 / 80")
    trim_inch = Column(String(16), comment="阀芯公称尺寸 in, 如 5/8, 1, 1 1/2")
    plug_mm = Column(Float, comment="阀芯/Plug 尺寸 mm (Table2: 用于查 Cv 和 stk_index)")
    plug_min_mm = Column(Float, comment="Plug Size 最小 mm (Table1: DN 级别的可选范围下限)")
    plug_max_mm = Column(Float, comment="Plug Size 最大 mm (Table1: DN 级别的可选范围上限)")
    stroke_mm = Column(Float, comment="全行程 mm")
    trim_type = Column(String(64), comment="Trim 类型/座类型: Standard P-port, Metal Seat, Soft Seat...")

    # 额定 Cv 数据 (按特性/类型并列，不同系列用不同列)
    cv_min = Column(Float, comment="最小 Cv (Table2: Minimum Capacity)")
    cv_eq = Column(Float, comment="等百分比额定 Cv (Table2: Rated Capacity)")
    cv_linear = Column(Float, comment="线性额定 Cv (GC120)")
    cv_60deg = Column(Float, comment="60° 额定 Cv (蝶阀)")
    cv_90deg = Column(Float, comment="90° 额定 Cv (蝶阀)")
    cv_metal_seat = Column(Float, comment="金属座额定 Cv (球阀)")
    cv_soft_seat = Column(Float, comment="软座额定 Cv (球阀)")

    stk_index = Column(Integer, comment="%Stk Index (Table2: Plug Size 对应的 eqcv 曲线索引)")
    stk_index_pct = Column(Float, comment="%Stk Index (%行程索引, 旧字段)")
    kfd = Column(Float, comment="阀门型式修正系数 Fd 的查表值 (mm, 如 GC210 的 KFd)")
    kfo = Column(Float, comment="Flow-to-Open 方向额定 Cv (GC210 Fd 公式用)")
    kfb = Column(Float, comment="Flow-to-Close 方向额定 Cv (GC210 Fd 公式用)")
    remark = Column(String(255), comment="备注")
    is_active = Column(Boolean, default=True, nullable=True, comment="是否启用")


# ---------------------------------------------------------------------------
# 阀芯尺寸 → %Stk Index 映射表 (按系列 + 压力等级)
# 来源于各系列 Sheet "Choices for Graphs" 上方的查找表
# 用于根据 Pressure Rating + Plug Size 确定 Eq% 曲线的索引
# ---------------------------------------------------------------------------
class ValvePlugIndexMap(Base):
    __tablename__ = "valve_plug_index_map"
    __table_args__ = (
        UniqueConstraint("series_code", "asme_class", "plug_mm", name="uq_plug_map"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    series_code = Column(String(32), nullable=False, index=True)
    asme_class = Column(String(32), nullable=False)
    plug_mm = Column(Float, nullable=False)
    stk_index = Column(Integer, nullable=False, comment="%Stk Index → eqcv 曲线索引")


# ---------------------------------------------------------------------------
# 系列曲线配置 — 每个系列的 FL/Kc/Fd/Stroke 曲线索引和计算方式
# 来源于各系列 Excel Sheet "Choices for Graphs" 区域
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 各系列筛选器配置 — 按 Excel 中 "Choices for Graphs / Cv vs Travel Graph" 区域定义
# 每个系列可配置多个筛选器，前端动态渲染
# ---------------------------------------------------------------------------
class ValveFilterConfig(Base):
    __tablename__ = "valve_filter_config"
    __table_args__ = (
        UniqueConstraint("series_code", "filter_key", name="uq_filter_config"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    series_code = Column(String(32), nullable=False, index=True)
    filter_key = Column(String(32), nullable=False, comment="筛选器内部名: trim_type/pressure_rating/plug_size/nominal_dn/trim_characteristics/flow_direction/opening_angle/seat_type/bore_type")
    display_label = Column(String(64), nullable=False, comment="前端显示标签，如 'Trim Type'")
    filter_order = Column(Integer, nullable=False, default=10, comment="前端显示顺序")
    is_enabled = Column(Boolean, nullable=False, default=True)
    option_source = Column(String(32), nullable=False, comment="选项来源: data(从数据表取)/hardcoded(静态选项)/cascade(级联动态)")
    hardcoded_options = Column(Text, nullable=True, comment="hardcoded 时的 JSON 选项列表")
    default_value = Column(String(64), nullable=True, comment="默认选项值")
    dependent_on = Column(String(128), nullable=True, comment="依赖哪个上游 filter_key 做级联过滤，多级用逗号分隔")
    value_field = Column(String(32), nullable=True, comment="数据来源 ORM 字段名，如 'asme_class'/'plug_mm'/'dn_mm'")
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class ValveSeriesCurveConfig(Base):
    """每个系列的系数曲线配置
    
    stroke_mode 取值:
      - eq_index:     使用 Eq% 多项式曲线 (从 valve_plug_index_map 查 index)
      - ln_eqn:       对数方程 %Stk = Ln(phi)/Ln(Fstk) + 1  (GC120/GV410)
      - exp_formula:  Exp(A4*ln(phi)+A3*phi+A1/(phi+A2)+A0)/divisor  (BT110/BT120)
      - poly_div60:   (A5*phi^5+...+A0)/60  (BT210)
      - linear:       phi = %Stk 直接相等 (GV110)
    """
    __tablename__ = "valve_series_curve_config"
    __table_args__ = (
        UniqueConstraint("series_code", "pressure_rating", name="uq_series_curve_config_rating"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    series_code = Column(String(32), nullable=False, index=True)
    pressure_rating = Column(String(64), nullable=True, index=True,
                             comment="压力等级精确匹配值 (如 '2500#' / '< 600#' / None=默认)")
    stroke_mode = Column(String(32), nullable=False, comment="eq_index/ln_eqn/exp_formula/poly_div60/linear")
    stroke_eq_index = Column(Integer, nullable=True, comment="eq_index 模式时的默认索引")
    stroke_fstk = Column(Float, nullable=True, comment="ln_eqn 模式时的 Fstk 参数")
    stroke_divisor = Column(Float, nullable=True, comment="poly_div60/exp_formula 模式的除数 (通常 60)")
    stroke_a0 = Column(Float, nullable=True)
    stroke_a1 = Column(Float, nullable=True)
    stroke_a2 = Column(Float, nullable=True)
    stroke_a3 = Column(Float, nullable=True)
    stroke_a4 = Column(Float, nullable=True)
    stroke_a5 = Column(Float, nullable=True)
    stroke_a6 = Column(Float, nullable=True)
    fl_eq_index = Column(Integer, nullable=False, comment="FL 曲线全局索引")
    kc_eq_index = Column(Integer, nullable=False, comment="Kc 曲线全局索引")
    fd_mode = Column(String(16), nullable=False, comment="table/eqn")
    fd_eq_index = Column(Integer, nullable=True, comment="fd_mode=table 时的索引")
    remark = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ---------------------------------------------------------------------------
# 阀门额定Cv与行程表 (Valve Cv & Stroke)
# 来源: CV&Stk.xlsx — 统一存储所有阀型的额定Cv和行程数据
# 约束条件: series_code + dn_label + trim_label + flow_char + trim_type
#           + pressure_rating + seat_type (不同区块填充不同字段, 其余为 NULL)
# 目标输出: rated_cv, stroke_mm
# ---------------------------------------------------------------------------
class ValveCvStk(Base):
    __tablename__ = "valve_cv_stk"
    __table_args__ = (
        Index("ix_valve_cv_stk_series", "series_code"),
        Index("ix_valve_cv_stk_composite", "series_code", "dn_label", "trim_label"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_code = Column(String(20), nullable=False, comment="阀门型号: GV120, BC110, BT210 等")
    dn_label = Column(String(20), nullable=False, comment="阀门通径: 15A, 25A, 100A 等")
    trim_label = Column(String(20), nullable=False, comment="阀芯尺寸: 6A, 25A, 80A 等")
    flow_char = Column(String(30), nullable=True, comment="流量特性: EQ%, Linear, ON-OFF, Inherent Character")
    trim_type = Column(String(50), nullable=True, comment="阀内件形式: Standard, Large Cv, Modified, Full, Full Anti-Cav, 8 Stage 等")
    pressure_rating = Column(String(20), nullable=True, comment="压力等级: 150#, 300#, 600# 等")
    seat_type = Column(String(50), nullable=True, comment="阀座形式: Soft, Metal, Damper, 15 Deg Sealed 等")
    rated_cv = Column(Float, nullable=True, comment="额定Cv (计算用目标输出)")
    stroke_value = Column(Float, nullable=True, comment="行程数值 (mm 或度)")
    stroke_unit = Column(String(10), nullable=True, comment="行程单位: mm (直行程) 或 ° (角行程)")
    plug_mm = Column(Float, nullable=True, comment="阀芯直径 mm (有阀芯尺寸的型号才填)")
    stk_index = Column(Integer, nullable=True, comment="%Stk Index (GV120 Large Cv P-port)")
    kfd = Column(Float, nullable=True, comment="GC210 Fd公式: KFd (型式修正系数)")
    kfo = Column(Float, nullable=True, comment="GC210 Fd公式: KFo (Flow-to-Open方向额定Cv)")
    kfb = Column(Float, nullable=True, comment="GC210 Fd公式: KFb (Flow-to-Close方向额定Cv)")
    cv_min = Column(Float, nullable=True, comment="最小 Cv")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ---------------------------------------------------------------------------
# 公共选项数据：阀门选型下拉（连接形式、密封面、材质、填料等）
# 由前端 COMMON_DATA 迁移而来，支持通过 API 读取，便于后端统一维护
# ---------------------------------------------------------------------------
class PublicOption(Base):
    __tablename__ = "public_options"
    __table_args__ = (
        Index("ix_public_options_group", "group_key"),
        Index("ix_public_options_group_order", "group_key", "sort_order"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_key = Column(String(50), nullable=False, comment="分组键: connection_type / face_type / body_material 等")
    value = Column(String(100), nullable=False, comment="选项值")
    label = Column(String(100), nullable=True, comment="显示标签 (为空时取 value)")
    sort_order = Column(Integer, nullable=False, default=0, comment="排序")
    is_default = Column(Boolean, nullable=False, default=False, comment="是否默认选项")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ---------------------------------------------------------------------------
# 选型模块新增表 (P0 基础设施)
# 依据: docs/选型模块优化方案.md v2.0 §2.1 ~ §2.4
# ---------------------------------------------------------------------------


class SelectionRule(Base):
    """选型规则库

    规则分四阶段执行:
      scope(10) → constraint(20) → preference(30) → post_filter(40)
    规则更新采用软删+新插模式，支持版本追溯。
    """
    __tablename__ = "selection_rules"
    __table_args__ = (
        Index("ix_selection_rule_category", "category", "target_series", "is_active"),
        Index("ix_selection_rule_priority", "priority"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_code = Column(String(64), unique=True, nullable=False, comment="规则编号 R-GV120-001")
    rule_name = Column(String(128), nullable=False, comment="规则名称")
    category = Column(String(32), nullable=False, comment="scope / constraint / preference / post_filter")
    target_series = Column(String(32), nullable=False, default="*", comment="目标系列，* 表示全局规则")
    condition_expr = Column(Text, nullable=True, comment="JSON 条件表达式")
    condition_op = Column(String(16), nullable=False, default="and", comment="and / or 条件组合方式")
    action = Column(String(32), nullable=False, comment="exclude / require / boost / set_field / flag / penalty")
    action_payload = Column(Text, nullable=True, comment="JSON 动作参数")
    priority = Column(Integer, nullable=False, default=10, comment="优先级: scope=10 / constraint=20 / preference=30 / post_filter=40")
    source_ref = Column(String(128), nullable=True, comment="来源（如 GV120_structured_data.json:p4）")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class BodyPtRating(Base):
    """阀体材质温压限制

    查询方式: (material_grade, pressure_class) 线性插值，与 source_series 无关
    """
    __tablename__ = "body_pt_ratings"
    __table_args__ = (
        UniqueConstraint("standard", "pressure_class", "material_grade", "temp_c", name="uq_body_pt_rating"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    standard = Column(String(16), nullable=False, comment="ANSI / PN")
    pressure_class = Column(String(16), nullable=False, comment="150# / 300# / PN16 等")
    material_grade = Column(String(32), nullable=False, comment="A216-WCB / A352-LCB / ZG230-450 等")
    temp_c = Column(Float, nullable=False, comment="温度 ℃")
    pressure_mpa_g = Column(Float, nullable=False, comment="允许压力 MPa(G)")
    source_series = Column(String(32), nullable=True, comment="数据来源系列（如 GC120/GA510/BV130）")
    created_at = Column(DateTime, default=datetime.now)


class AllowablePressureDrop(Base):
    """最大允许压差

    唯一约束: (series_code, actuator_family, actuator_size, packing,
              seat_type, plug_inch, air_supply)
    注: 同一组合在不同气源压力 (air_supply) 下允许压差不同, 气源压力必须入键
    """
    __tablename__ = "allowable_pressure_drops"
    __table_args__ = (
        UniqueConstraint("series_code", "actuator_family", "actuator_size", "packing", "seat_type", "plug_inch", "air_supply", name="uq_allowable_dp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_code = Column(String(32), nullable=False, comment="GC120 / GC210 / GC320 / BT110 / GV120 等")
    actuator_family = Column(String(32), nullable=True, comment="PD3000LA / PC3200LA 等")
    actuator_size = Column(String(16), nullable=True, comment="270 / 350 / 450 / 650 等")
    spring_range = Column(String(32), nullable=True, comment="80~200 / 120~300 等")
    packing = Column(String(32), nullable=True, comment="R.TFE / Grafoil 等")
    seat_type = Column(String(16), nullable=True, comment="Metal / Soft 等")
    plug_inch = Column(String(16), nullable=True, comment="阀芯尺寸 1\" / 2\" / ...")
    air_supply = Column(String(16), nullable=True, comment="气源压力 kPa(表压), 如 300(80)/340(120)/400/500")
    max_dp_mpa = Column(Float, nullable=False, comment="最大允许压差 MPa")
    created_at = Column(DateTime, default=datetime.now)


class SelectionRecord(Base):
    """选型历史记录"""
    __tablename__ = "selection_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    valve_id = Column(Integer, ForeignKey("valves.id"), nullable=False, comment="位号ID")
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, comment="项目ID")
    input_snapshot = Column(Text, nullable=True, comment="输入工艺条件 JSON")
    candidates_json = Column(Text, nullable=True, comment="候选清单 JSON（含打分）")
    selected_series = Column(String(32), nullable=True, comment="最终选中系列")
    selected_config = Column(Text, nullable=True, comment="选中的阀芯/口径/材质等 JSON")
    applied_rule_ids = Column(String(255), nullable=True, comment="触发的规则ID逗号分隔")
    created_at = Column(DateTime, default=datetime.now)
    created_by = Column(String(64), nullable=True, comment="创建人")
