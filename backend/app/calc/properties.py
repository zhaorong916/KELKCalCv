"""物性参数服务

- 水/水蒸汽：使用 IAPWS-IF97(经 iapws 库) 精确计算，按温度/压力自动判定相态
  （液态/饱和/蒸汽），并提供密度、粘度、比热比、声速等。
- 其它介质：理想气体密度计算 + 介质库默认物性。
- 压力统一 kPa(abs)，温度 ℃。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Optional

try:
    from iapws import IAPWS97
    from iapws.iapws97 import _PSat_T, _TSat_P
    _HAS_IAPWS = True
except Exception:  # pragma: no cover - 依赖缺失时的兜底
    _HAS_IAPWS = False


WATER_CRITICAL_P_KPA = 22064.0   # 水的临界压力 kPa(abs)
WATER_CRITICAL_T_C = 373.946      # 临界温度 ℃
WATER_PC_KPA = WATER_CRITICAL_P_KPA


@dataclass
class FluidProperties:
    """通用介质工况物性结果"""
    name: str
    phase: str               # liquid / gas / saturated / twophase
    density: float           # kg/m3 (工况)
    viscosity_cp: float      # 动力粘度 cP(=mPa·s)
    vapor_pressure_kpa: float = 0.0  # 饱和蒸汽压 kPa(abs)
    critical_pressure_kpa: float = 0.0
    molecular_weight: float = 0.0
    gamma: float = 1.0       # 比热比 cp/cv
    speed_of_sound: float = 0.0  # m/s
    compressibility: float = 1.0  # Z 压缩因子 (气体 Redlich-Kwong，液 1.0)
    t_c: float = 0.0
    p_kpa: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# 水与水蒸汽 —— IAPWS-IF97
# ---------------------------------------------------------------------------
def water_saturation_pressure_kpa(t_c: float) -> float:
    """水饱和蒸汽压 (kPa abs)，温度 ℃。超临界温度返回临界压力。"""
    if t_c >= WATER_CRITICAL_T_C:
        return WATER_PC_KPA
    if not _HAS_IAPWS:
        # 兜底近似(Antoine 扩展)，仅低压段
        return _water_psat_fallback(t_c)
    return float(_PSat_T(t_c + 273.15)) * 1000.0


def water_saturation_temperature_c(p_kpa: float) -> float:
    """水饱和温度 (℃)，压力 kPa(abs)。"""
    if not _HAS_IAPWS:
        return _water_tsat_fallback(p_kpa)
    return float(_TSat_P(p_kpa / 1000.0)) - 273.15


def water_properties(t_c: float, p_kpa: float) -> FluidProperties:
    """水/水蒸汽工况物性，自动判定相态。

    判定逻辑：先求 Psat(T)。P > Psat → 液态；P < Psat → 过热蒸汽；近似相等 → 饱和。
    """
    psat_kpa = water_saturation_pressure_kpa(t_c)
    p_mpa = p_kpa / 1000.0
    tol = max(0.5, psat_kpa * 0.002)

    # 超临界温度(T > 373.946℃)：直接判定为气态(过热蒸汽/超临界流体按气体处理)
    if t_c >= WATER_CRITICAL_T_C:
        phase = "gas"
    elif abs(p_kpa - psat_kpa) <= tol:
        phase = "saturated"
    elif p_kpa > psat_kpa:
        phase = "liquid"
    else:
        phase = "gas"

    if _HAS_IAPWS:
        try:
            if phase == "saturated":
                # 饱和：取气相与液相的代表性值(用饱和蒸汽)
                sat = IAPWS97(P=p_mpa, x=0.5)
                rho = float(sat.Vapor.rho)
                mu = float(sat.Vapor.mu) * 1000.0  # Pa·s -> cP
                gamma = float(sat.Vapor.cp) / float(sat.Vapor.cv)
                w = float(sat.Vapor.w)
            else:
                st = IAPWS97(P=p_mpa, T=t_c + 273.15)
                rho = float(st.rho)
                mu = float(st.mu) * 1000.0  # Pa·s -> cP
                gamma = float(st.cp) / float(st.cv)
                w = float(st.w)
            return FluidProperties(
                name="水/蒸汽",
                phase=phase,
                density=rho,
                viscosity_cp=mu,
                vapor_pressure_kpa=psat_kpa,
                critical_pressure_kpa=WATER_PC_KPA,
                molecular_weight=18.015,
                gamma=gamma if math.isfinite(gamma) else 1.3,
                speed_of_sound=w,
                t_c=t_c,
                p_kpa=p_kpa,
            )
        except Exception:
            pass  # 落到兜底

    # 兜底近似
    if phase == "liquid":
        rho = _water_liquid_density(t_c)
        mu = _water_liquid_viscosity_cp(t_c)
        gamma, w = 1.0, 1400.0
    else:
        rho = _steam_density(t_c, p_kpa)
        mu = _steam_viscosity_cp(t_c)
        gamma, w = 1.327, 450.0
    return FluidProperties(
        name="水/蒸汽", phase=phase, density=rho, viscosity_cp=mu,
        vapor_pressure_kpa=psat_kpa, critical_pressure_kpa=WATER_PC_KPA,
        molecular_weight=18.015, gamma=gamma, speed_of_sound=w, t_c=t_c, p_kpa=p_kpa,
    )


def water_saturation_phase_densities(t_c: float, p_kpa: float) -> tuple:
    """返回饱和水/汽相密度 (rho_liquid, rho_vapor) kg/m³。

    用于湿蒸汽 Singleton 模型：给定饱和温度/压力，
    通过 IAPWS97 x=0 (饱和液) 和 x=1 (饱和汽) 获取各自密度。
    """
    if t_c >= WATER_CRITICAL_T_C:
        # 超临界：液汽不可分，返回单一密度
        return (322.0, 322.0)
    psat = water_saturation_pressure_kpa(t_c)
    p_mpa = (p_kpa if p_kpa > 0 else psat) / 1000.0
    if _HAS_IAPWS:
        try:
            sat_l = IAPWS97(P=p_mpa, x=0.0)
            sat_v = IAPWS97(P=p_mpa, x=1.0)
            return (float(sat_l.rho), float(sat_v.rho))
        except Exception:
            pass
    # 兜底近似 (100℃ 常压值)
    return (958.0, 0.598)


# ---------------------------------------------------------------------------
# 通用气体密度（理想气体 / Redlich-Kwong 实际气体）
# ---------------------------------------------------------------------------
def gas_compressibility_rk(p_kpa: float, t_c: float,
                           pc_kpa: float, tc_k: float) -> float:
    """Redlich-Kwong 状态方程压缩因子 Z (与 Excel GasPTPcTcZ 一致)。

    RK 方程:
        P = RT/(V-b) − a/(√T · V(V+b))
    其中:
        a = 0.42747 · R²·Tc^2.5 / Pc
        b = 0.08664 · R·Tc / Pc
    令 A = aP/(R²T^2.5), B = bP/(RT), V = ZRT/P，化简得压缩因子三次方程：
        Z³ − Z² + (A − B − B²)·Z − A·B = 0
    使用 Cardano 公式求解，并取 > B 的气体根（Vapor 根，排除液体根 Z<B）。
    """
    if pc_kpa <= 0 or tc_k <= 0 or p_kpa <= 0 or t_c <= -273.14:
        return 1.0
    T_K = t_c + 273.15
    Tr = T_K / tc_k
    Pr = p_kpa / pc_kpa
    if Pr <= 0:
        return 1.0
    if Tr < 0.55:
        # 近液化点 RK 蒸汽根不收敛，兜底理想气体
        return 1.0
    # 注意：R 的量纲必须与 P, V 单位体系自洽。
    # Excel 使用 bar 体系: R=0.08314 bar·L/(mol·K)，最终 Z 与单位体系无关。
    # 因此直接用对比态形式 A=Ωa·Pr/Tr^2.5,  B=Ωb·Pr/Tr  即可(量纲抵消)
    A = 0.42747 * Pr / (Tr ** 2.5)
    B = 0.08664 * Pr / Tr
    # 三次方程: Z³ - Z² + C1*Z + C0 = 0
    # 展开验证：Vapor 根满足 Z>B，液体根 Z<B
    C1 = A - B - B * B
    C0 = -A * B
    a_coef = 1.0
    b_coef = -1.0
    c_coef = C1
    d_coef = C0
    p3 = (3 * a_coef * c_coef - b_coef ** 2) / (3 * a_coef ** 2)
    q3 = (2 * b_coef ** 3 - 9 * a_coef * b_coef * c_coef + 27 * a_coef ** 2 * d_coef) / (27 * a_coef ** 3)
    disc = (q3 / 2.0) ** 2 + (p3 / 3.0) ** 3
    offset = -b_coef / (3 * a_coef)
    candidates = []
    if disc >= 0:
        s_disc = math.sqrt(disc)
        u1 = -q3 / 2.0 + s_disc
        v1 = -q3 / 2.0 - s_disc
        C1r = math.copysign(abs(u1) ** (1.0 / 3.0), u1)
        C2r = math.copysign(abs(v1) ** (1.0 / 3.0), v1)
        candidates.append(C1r + C2r + offset)
    else:
        r_d = math.sqrt((-p3 / 3.0) ** 3)
        phi = math.acos((-q3 / 2.0) / r_d)
        for k in (0, 1, 2):
            yk = 2 * math.sqrt(-p3 / 3.0) * math.cos(phi / 3 - 2 * math.pi * k / 3)
            candidates.append(yk + offset)
    # 取所有候选中 > B 且与 1.0 最接近的实根（Vapor root）
    roots = [z for z in candidates if math.isfinite(z) and z > B * 0.995]
    if not roots:
        roots = [z for z in candidates if math.isfinite(z) and 0.1 < z < 2.0]
    if not roots:
        return 1.0
    # 优先取合理气体区间 (0.2, 1.5) 最接近 1 的
    in_range = [z for z in roots if 0.2 < z < 1.5]
    Z = min(in_range if in_range else roots, key=lambda x: abs(x - 1.0))
    if not 0.05 < Z < 2.5:
        return 1.0
    return Z


def gas_density(p_kpa: float, t_c: float, molar_mass: float, z: float = 1.0) -> float:
    """气体密度 (kg/m³)。P kPa(abs), T ℃, M kg/kmol, Z 压缩因子。"""
    R = 8.314  # kPa·m³/(kmol·K)
    T = t_c + 273.15
    return p_kpa * molar_mass / (z * R * T)


def gas_speed_of_sound(t_c: float, gamma: float, molar_mass: float) -> float:
    """气体声速 (m/s)。

    理想气体形式 c=√(γ·R·T/M)。声速受压缩因子 Z 影响很小(高阶量)，
    与 Excel c1=(10⁵·k·P1/ρ1)^0.5 数值等价：代入 ρ1=P·M/(Z·R·T) 可得
    c = (Z·γ·R·T/M)^0.5 ，此处保持与旧函数接口兼容不引入 Z 参数；
    调用方可按需采用 Newton-Laplace 形式：√(γ*P/ρ1)。
    """
    R = 8314.0  # J/(kmol·K)
    T = t_c + 273.15
    return math.sqrt(gamma * R * T / molar_mass)


def gas_speed_of_sound_nl(t_c: float, gamma: float, p_kpa: float, rho1: float) -> float:
    """Newton-Laplace 声速，与 Excel c1=√(10⁵·γ·P1/ρ1) 一致。

    与 gas_speed_of_sound (理想气体) 相比：若实际气体 ρ1 中已含 RK 压缩因子 Z，
    此处自动通过 ρ1 吸收 Z，与 Excel 实现完全一致。
    """
    if rho1 <= 0 or p_kpa <= 0:
        return 0.0
    # 100000 * P_kPa * gamma / rho   (P_kPa->Pa 转换在 Excel 中为 10^5)
    return math.sqrt(100000.0 * p_kpa * gamma / rho1)


# ---------------------------------------------------------------------------
# P3-2: Antoine 蒸汽压温度修正
# ---------------------------------------------------------------------------
def antoine_vapor_pressure_kpa(t_c: float, a: float, b: float, c: float,
                                tmin_k: Optional[float] = None) -> float:
    """Antoine 方程饱和蒸汽压 kPa(abs)。

    公式 (与 Excel FluidData 一致):
        Pv(barA) = exp(A − B / (T(K) + C))
        Pv(kPa)  = Pv(barA) × 100

    参数:
        t_c: 工况温度 ℃
        a, b, c: Antoine 系数 (A, B, C)，来自介质库 antoine_a/b/c
        tmin_k: 方程适用下限温度 K；工况温度低于此值时钳制到下限
                (Antoine 方程在低温段外推会失真)
    """
    if not a or not b or a == 0 or b == 0:
        return 0.0
    T_K = t_c + 273.15
    if tmin_k and tmin_k > 0 and T_K < tmin_k:
        T_K = tmin_k
    denom = T_K + c
    if abs(denom) < 1e-9:
        return 0.0
    try:
        pv_bar = math.exp(a - b / denom)
    except OverflowError:
        return 0.0
    if not math.isfinite(pv_bar) or pv_bar <= 0:
        return 0.0
    return pv_bar * 100.0


# ---------------------------------------------------------------------------
# P3-3: 液体密度温度修正 (Excel Gf 公式)
# ---------------------------------------------------------------------------
def liquid_density_temperature_corrected(rho_base: float, t_c: float,
                                          tc_k: float, tb_k: float) -> float:
    """液体密度随温度修正 (与 Excel Gf 公式一致)。

    公式:
        ρ(T) = ρ_B × (2·Tc − T) / (2·Tc − TB)

    参数:
        rho_base: 基准密度 kg/m³ (density_liquid, 在沸点 TB 或参考温度下)
        t_c: 工况温度 ℃
        tc_k: 临界温度 K (critical_temp)
        tb_k: 正常沸点 K (boiling_point)

    说明:
        线性近似，在 TB~0.9Tc 区间较准确；接近临界温度时密度下降加速，
        此处钳制到临界密度下限 (100 kg/m³) 避免负值。
    """
    if tc_k <= 0 or tb_k <= 0 or rho_base <= 0:
        return rho_base
    T_K = t_c + 273.15
    denom = 2.0 * tc_k - tb_k
    if abs(denom) < 1e-9:
        return rho_base
    rho = rho_base * (2.0 * tc_k - T_K) / denom
    # 临界密度下限钳制 (大多数液体临界密度 200~400 kg/m³)
    return max(rho, 100.0)


# ---------------------------------------------------------------------------
# 兜底近似(仅当 iapws 不可用时)
# ---------------------------------------------------------------------------
def _water_psat_fallback(t_c: float) -> float:
    """低压段水饱和蒸汽压近似(kPa)。0~200℃ 有效。"""
    if t_c < 0:
        t_c = 0.0
    return 0.61094 * math.exp(17.625 * t_c / (t_c + 243.04))


def _water_tsat_fallback(p_kpa: float) -> float:
    if p_kpa <= 0:
        return 0.0
    return 243.04 * math.log(p_kpa / 0.61094) / (17.625 - math.log(p_kpa / 0.61094))


def _water_liquid_density(t_c: float) -> float:
    if t_c < 0:
        t_c = 0.0
    if t_c > 370:
        t_c = 370.0
    rho = 1000.6 - 0.1284 * t_c - 0.00378 * t_c * t_c + 1.2e-5 * t_c ** 3
    return max(rho, 300.0)


def _water_liquid_viscosity_cp(t_c: float) -> float:
    if t_c < 0:
        t_c = 0.0
    if t_c > 370:
        t_c = 370.0
    return max(1.790 * math.exp(-0.0335 * t_c) + 0.18 * math.exp(-0.0045 * t_c), 0.06)


def _steam_density(t_c: float, p_kpa: float) -> float:
    return gas_density(p_kpa, t_c, 18.015)


def _steam_viscosity_cp(t_c: float) -> float:
    if t_c < 100:
        t_c = 100.0
    return 0.012 + 0.000035 * (t_c - 100)


# ---------------------------------------------------------------------------
# 介质库默认物性(用于初始化数据库 Fluid 表)
#   state: 默认相态 liquid/gas
#   密度: liquid→kg/m3 工况近似; gas→标况(0℃,101.325kPa) kg/m3
# ---------------------------------------------------------------------------
DEFAULT_FLUIDS = [
    # name, formula, default_state, rho_liq, rho_gas, MW, gamma, Pc_kPa, Tc_K, Pv_kPa, viscosity_cP
    ("水", "H2O", "liquid", 1000.0, 0.804, 18.015, 1.327, 22064.0, 647.096, 3.17, 1.0, True),
    ("饱和蒸汽", "H2O", "gas", 0.0, 0.804, 18.015, 1.327, 22064.0, 647.096, 101.325, 0.012, True),
    ("过热蒸汽", "H2O", "gas", 0.0, 0.804, 18.015, 1.327, 22064.0, 647.096, 0.0, 0.02, True),
    ("空气", "Air", "gas", 0.0, 1.293, 28.965, 1.4, 3785.0, 132.5, 0.0, 0.018, False),
    ("氮气", "N2", "gas", 0.0, 1.251, 28.014, 1.4, 3398.0, 126.2, 0.0, 0.0175, False),
    ("氧气", "O2", "gas", 0.0, 1.429, 31.999, 1.4, 5043.0, 154.6, 0.0, 0.02, False),
    ("氢气", "H2", "gas", 0.0, 0.0899, 2.016, 1.41, 1297.0, 33.2, 0.0, 0.0088, False),
    ("二氧化碳", "CO2", "gas", 0.0, 1.977, 44.010, 1.3, 7388.0, 304.1, 5180.0, 0.015, False),
    ("一氧化碳", "CO", "gas", 0.0, 1.250, 28.010, 1.4, 3494.0, 132.9, 0.0, 0.0175, False),
    ("甲烷", "CH4", "gas", 0.0, 0.717, 16.043, 1.31, 4604.0, 190.6, 0.0, 0.011, False),
    ("天然气(典型)", "CH4+", "gas", 0.0, 0.78, 17.4, 1.32, 4600.0, 200.0, 0.0, 0.011, False),
    ("乙烯", "C2H4", "gas", 0.0, 1.260, 28.054, 1.24, 5061.0, 282.4, 0.0, 0.01, False),
    ("丙烯", "C3H6", "gas", 0.0, 1.915, 42.081, 1.16, 4601.0, 365.0, 0.0, 0.0085, False),
    ("氨", "NH3", "gas", 0.0, 0.771, 17.031, 1.31, 11333.0, 405.4, 1018.0, 0.010, False),
    ("氯气", "Cl2", "gas", 0.0, 3.214, 70.906, 1.36, 7711.0, 417.2, 1013.0, 0.013, False),
    ("乙醇", "C2H5OH", "liquid", 789.0, 2.043, 46.069, 1.13, 6140.0, 513.9, 5.95, 1.2, False),
    ("甲醇", "CH3OH", "liquid", 791.0, 1.429, 32.042, 1.20, 8097.0, 512.5, 16.9, 0.59, False),
    ("甘油", "C3H8O3", "liquid", 1261.0, 0.0, 92.095, 1.0, 7516.0, 723.0, 0.01, 1412.0, False),
    ("柴油", "C12-C16", "liquid", 840.0, 0.0, 180.0, 1.05, 1500.0, 700.0, 0.1, 3.5, False),
    ("导热油", "Mix", "liquid", 850.0, 0.0, 250.0, 1.05, 1200.0, 760.0, 0.1, 20.0, False),
]


def get_fluid_defaults() -> list:
    """返回介质库默认物性条目(用于初始化)。字段名与 Fluid 模型一致。"""
    cols = ["fluid_name", "formula", "default_state", "density_liquid", "density_gas",
            "molecular_weight", "cp_cv_ratio", "critical_pressure", "critical_temp",
            "vapor_pressure", "viscosity", "is_water"]
    return [dict(zip(cols, row)) for row in DEFAULT_FLUIDS]
