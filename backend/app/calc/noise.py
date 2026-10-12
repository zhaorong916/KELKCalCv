"""阀门噪音预测

气体气动噪音: IEC 60534-8-3 方法(物理步骤)
液体水动力噪音: IEC 60534-8-4 方法(物理步骤)

五步法(IEC):
  1) 计算喉部(vena contracta)射流机械功率 Pow = ½·ṁ·U_vc²
  2) 声-机效率 η → 声功率 W_a = η·Pow
  3) 内部声功率级 L_Wi = 10·log10(W_a / W_ref),  W_ref=1e-12 W
  4) 管壁传声损失 TL(频率/壁厚/材料/介质相关)
  5) 距离与 A 计权 → 距管壁 1m 处 A 计权声压级 LpA

说明: 本实现为基于 IEC 方法的工程估算(单峰频带简化整体法)，
      系数见下方 NOISE_CFG，便于按实测/标准精化。
      完整倍频程法(含厂家声效率因子 Aη 实测)为后续增强。
单位: 压力 kPa(abs), 温度 ℃, 流量 kg/h, 管径 mm, 声压级 dB(A)。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Optional

W_REF = 1.0e-12        # 声功率参考 W
RHO_REF = 1.293        # 空气标况密度 kg/m³
STEEL_RHO = 7850.0     # 钢密度 kg/m³
STEEL_C = 5180.0       # 钢中纵波声速 m/s
AIR_C_REF = 343.0      # 空气声速参考 m/s


@dataclass
class NoiseResult:
    """噪音预测结果"""
    noise_dba: float = 0.0          # A计权声压级 dB(A) @1m
    noise_freq_peak: float = 0.0    # 峰值频率 Hz
    method: str = ""
    mach_outlet: float = 0.0        # 阀后马赫数
    vc_velocity: float = 0.0        # 喉部射流速度 m/s
    stream_power_w: float = 0.0     # 喉部机械功率 W
    acoustic_power_w: float = 0.0   # 声功率 W
    internal_lw: float = 0.0        # 内部声功率级 dB
    transmission_loss: float = 0.0  # 管壁传声损失 dB
    regime: str = ""
    regime_index: int = 0           # 5级 Regime 编号 1..5 (I..V)
    jet_diameter_m: float = 0.0     # 射流直径 Dj (Eq.9)
    vc_mach: float = 0.0            # 缩脉马赫数 Mvc (Eq.32)
    critical_mach: float = 0.0      # 临界马赫数 Mj
    aeta: float = 0.0               # 使用的声效率因子 10^Aeta
    warnings: list = None
    detail: dict = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.detail is None:
            self.detail = {}

    def to_dict(self) -> dict:
        return asdict(self)


# 简化系数(可按标准/实测精化)
NOISE_CFG = {
    "eta_subsonic": 1.2e-3,   # 亚临界声效率系数前因子 (η = a·Ma^n)
    "eta_sonic": 1.0e-2,      # 临界/超临界声效率
    "ma_exp": 3.5,            # 声效率马赫数幂次
    "strouhal": 0.20,         # 斯特鲁哈尔数(峰值频率)
    "tl_floor": 6.0,          # 传声损失下限 dB
    "distance_m": 1.0,        # 测点距离 m
    "a_weight_correction": -2.0,  # A计权整体修正 dB
}


def predict_gas_noise(
    *,
    cv_operating: float,
    fl: float,
    p1: float,            # kPa abs
    p2: float,
    t1_c: float,
    rho1: float,          # kg/m³
    molar_mass: float,
    gamma: float,
    mass_flow: float,     # kg/h
    pipe_diameter_mm: float,
    pipe_wall_mm: float,
    distance_m: float = 1.0,
    xt: float = 0.72,
    fgamma: float = 1.0,
    # 5-Regime 增强参数
    flp: Optional[float] = None,
    fd: float = 0.46,
    aeta_db: Optional[float] = None,
    enhanced: bool = False,
    octave: bool = False,
    # P3-1: 多级降噪阀
    stages: int = 1,
) -> NoiseResult:
    """气体气动噪音预测(IEC 60534-8-3)。

    enhanced=True 且 flp/aeta_db 可用时走 5 级 Regime 精确模型；
    否则自动降级到简化工程估算。
    stages>1 时启用多级降噪阀压降分配 (几何分布)。
    """
    if enhanced and flp is not None and aeta_db is not None and flp > 0:
        return _predict_gas_noise_5regime(
            cv_operating=cv_operating, fl=fl, flp=flp, fd=fd, aeta_db=aeta_db,
            p1=p1, p2=p2, t1_c=t1_c, rho1=rho1, molar_mass=molar_mass,
            gamma=gamma, mass_flow=mass_flow,
            pipe_diameter_mm=pipe_diameter_mm, pipe_wall_mm=pipe_wall_mm,
            distance_m=distance_m, octave=octave, stages=stages,
        )
    return _predict_gas_noise_simplified(
        cv_operating=cv_operating, fl=fl, p1=p1, p2=p2, t1_c=t1_c,
        rho1=rho1, molar_mass=molar_mass, gamma=gamma, mass_flow=mass_flow,
        pipe_diameter_mm=pipe_diameter_mm, pipe_wall_mm=pipe_wall_mm,
        distance_m=distance_m, xt=xt, fgamma=fgamma, stages=stages,
    )


def _predict_gas_noise_simplified(
    *, cv_operating, fl, p1, p2, t1_c, rho1, molar_mass, gamma,
    mass_flow, pipe_diameter_mm, pipe_wall_mm, distance_m, xt, fgamma, stages=1,
) -> NoiseResult:
    """气体气动噪音简化估算(原实现)。

    stages>1 时启用多级降噪阀压降分配 (几何分布)，
    将 detail 中补充 x_stage/r_stage/stages_needed 等字段。
    """
    res = NoiseResult(method="IEC60534-8-3(简化)", regime="气体气动")
    if p1 <= 0 or p2 <= 0 or mass_flow <= 0 or rho1 <= 0 or pipe_diameter_mm <= 0:
        res.warnings.append("输入参数不足，无法计算噪音")
        return res

    N_stg = max(int(stages), 1)
    R = 8314.0 / max(molar_mass, 1e-6)   # J/(kg·K)
    T1 = t1_c + 273.15
    gamma = gamma if gamma > 1.0 else 1.4
    # 等熵膨胀至阀后
    pr = max(p2 / p1, 1e-6)
    T2 = T1 * (pr ** ((gamma - 1.0) / gamma))
    rho2 = p2 * molar_mass / (8.314 * T2)  # kg/m³
    c2 = math.sqrt(gamma * R * T2)         # 阀后声速 m/s

    # 阀后流速与马赫
    A = math.pi * (pipe_diameter_mm / 1000.0) ** 2 / 4.0
    mdot = mass_flow / 3600.0
    U2 = mdot / (rho2 * A)
    Ma2 = U2 / c2
    res.mach_outlet = Ma2

    # 喉部(vena contracta)射流速度(用 FL 关联)
    fl = fl if 0 < fl < 1 else 0.9
    U_vc = U2 / fl
    U_vc = min(U_vc, math.sqrt(gamma * R * T1))  # 不超过声速量级
    res.vc_velocity = U_vc

    # 机械功率
    Pow = 0.5 * mdot * U_vc * U_vc
    res.stream_power_w = Pow

    # 声效率(亚临界/临界)
    x_total = (p1 - p2) / p1
    N_stg = max(int(stages), 1)

    if N_stg > 1:
        # 多级降噪: 每级按几何分布, 用每级压差比 x_stage 重算
        r_stage = (p2 / p1) ** (1.0 / N_stg)
        x = 1.0 - r_stage                                   # 每级压差比
        choked = x >= fgamma * xt
        # 每级射流速度按 √(x_stage/x_total) 缩放
        if x_total > 0:
            U_vc_stage = U_vc * math.sqrt(x / x_total)
        else:
            U_vc_stage = U_vc
        U_vc_stage = min(U_vc_stage, math.sqrt(gamma * R * T1))
        # 每级有效马赫数: 按射流速度缩放 (eta 的核心驱动量)
        Ma_stage = Ma2 * math.sqrt(x / x_total) if x_total > 0 and Ma2 > 0 else 0.0
        if choked:
            eta = NOISE_CFG["eta_sonic"]
            res.regime = f"气体气动-{N_stg}级-临界(阻塞)"
        else:
            eta = NOISE_CFG["eta_subsonic"] * (Ma_stage ** NOISE_CFG["ma_exp"]) if Ma_stage > 0 else 0.0
            res.regime = f"气体气动-{N_stg}级-亚临界"
        eta = min(max(eta, 1e-8), 0.5)
        Pow_stage = 0.5 * mdot * U_vc_stage * U_vc_stage
        # N 级声功率叠加 (非相干叠加: Wa_total = N × Wa_stage)
        Wa = N_stg * eta * Pow_stage
        res.vc_velocity = U_vc_stage
        res.stream_power_w = Pow_stage * N_stg
        res.acoustic_power_w = Wa
        Lwi = 10.0 * math.log10(max(Wa, 1e-15) / W_REF)
        res.internal_lw = Lwi
        # 峰值频率: TL 是管壁属性, 用总工况 U_vc 而非每级, 避免 TL 随级数变化抵消降噪
        d_vc = 0.6 * pipe_diameter_mm
        f_p = NOISE_CFG["strouhal"] * U_vc / (d_vc / 1000.0)
        res.noise_freq_peak = f_p
    else:
        x = x_total
        choked = x >= fgamma * xt
        if choked:
            eta = NOISE_CFG["eta_sonic"]
            res.regime = "气体气动-临界(阻塞)"
        else:
            eta = NOISE_CFG["eta_subsonic"] * (Ma2 ** NOISE_CFG["ma_exp"]) if Ma2 > 0 else 0.0
            res.regime = "气体气动-亚临界"
        eta = min(max(eta, 1e-8), 0.5)
        Wa = eta * Pow
        res.acoustic_power_w = Wa
        Lwi = 10.0 * math.log10(max(Wa, 1e-15) / W_REF)
        res.internal_lw = Lwi
        d_vc = 0.6 * pipe_diameter_mm
        f_p = NOISE_CFG["strouhal"] * U_vc / (d_vc / 1000.0)
        res.noise_freq_peak = f_p

    # 管壁传声损失(钢制圆管, 简化): 基于环频 f_r=c2/(π·d_i)
    d_i = pipe_diameter_mm / 1000.0
    t = max(pipe_wall_mm, 1.0) / 1000.0
    f_r = c2 / (math.pi * d_i) if d_i > 0 else 1.0
    # 面密度 m'' = ρ_steel·t ; 介质声阻抗 ρ_g·c_g
    m_pp = STEEL_RHO * t
    z_g = rho2 * c2
    # 简化传声损失(吻合效应简化): TL = 10log( (m''·ω)^2 / ( (ρ_g·c_g)^2·... ) )
    if f_p > 0 and z_g > 0:
        ratio = (m_pp * 2.0 * math.pi * f_p) / z_g
        TL = 10.0 * math.log10(1.0 + ratio * ratio) + 10.0 * math.log10(m_pp / max(z_g * d_i, 1e-9))
    else:
        TL = NOISE_CFG["tl_floor"]
    TL = max(TL, NOISE_CFG["tl_floor"])
    res.transmission_loss = TL

    # 外部声压级 @ 距离 r: Lp = Lwi - TL + 10log( S_rad / (4π·r²·S_ref) ) ...
    #   简化: LpA = Lwi - TL + 10log( D·d_i / (4·r) ) + A计权
    r = distance_m if distance_m > 0 else 1.0
    rad = 10.0 * math.log10(max(d_i * 1.0 / (4.0 * r), 1e-6))
    LpA = Lwi - TL + rad + NOISE_CFG["a_weight_correction"]
    res.noise_dba = LpA

    res.detail = {
        "T2_K": T2, "rho2": rho2, "c2_m_s": c2, "U2_m_s": U2, "Ma2": Ma2,
        "U_vc": res.vc_velocity, "FL": fl, "Pow_W": res.stream_power_w, "eta": eta, "Wa_W": Wa,
        "Lwi_dB": Lwi, "TL_dB": TL, "f_p_Hz": f_p, "f_r_Hz": f_r, "rad_dB": rad,
        "P1": p1, "P2": p2, "x": x, "x_total": x_total, "stages": N_stg, "choked": choked,
        "regime_label": res.regime,
    }
    if N_stg > 1:
        # detail 补充每级参数 (x_stage/r_stage 已在上方计算)
        res.detail["x_stage"] = x
        res.detail["r_stage"] = (p2 / p1) ** (1.0 / N_stg)
        # 估算避免阻塞所需最少级数
        xT_eff = fgamma * xt
        xT_safe = max(xT_eff, 1e-6)
        n_min = math.ceil(math.log(p2 / p1) / math.log(1.0 - xT_safe)) if xT_safe < 1 else 1
        res.detail["stages_needed"] = max(int(n_min), 1)
    if Ma2 > 0.3:
        res.warnings.append(f"阀后马赫数 {Ma2:.2f}>0.3，出口流速偏高，建议复核管径")
    if LpA > 85:
        res.warnings.append(f"预测噪音 {LpA:.0f} dB(A)>85，需考虑降噪措施")
    return res


def _predict_gas_noise_5regime(
    *, cv_operating, fl, flp, fd, aeta_db, p1, p2, t1_c, rho1,
    molar_mass, gamma, mass_flow, pipe_diameter_mm, pipe_wall_mm,
    distance_m, octave=False, stages=1,
) -> NoiseResult:
    """IEC 60534-8-3 完整 5 级 Regime 气体噪音预测。

    五步法:
      1. 压力比与 Regime 判定 (Eq.1-7)
      2. 射流直径 Dj (Eq.9)
      3. 缩脉条件 Mvc/cvc/Mj (Eq.32)
      4. 声功率（按 Regime 分别计算 η×Wm）
      5. 声压级 Lpi+Lg+TL+Lpe1m

    P3-1 多级降噪阀 (stages>1):
      总压差按几何分布分配到 N 级: r_stage=(p2/p1)^(1/N), x_stage=1-r_stage
      用 x_stage 进行 Regime 判定与 η 计算 (每级 Regime 显著降低)；
      声功率 Wa=η(x_stage)·Wm_total (N 级的 Wm/N × N 抵消)。
      降噪来源: 每级 x_stage 远小于总 x → Regime 降低 → η 大幅下降。
    """
    res = NoiseResult(method="IEC60534-8-3(5-Regime)", regime="气体气动")
    if p1 <= 0 or p2 <= 0 or mass_flow <= 0 or rho1 <= 0 or pipe_diameter_mm <= 0:
        res.warnings.append("输入参数不足，无法计算噪音")
        return res

    R = 8314.0 / max(molar_mass, 1e-6)
    T1 = t1_c + 273.15
    k = gamma if gamma > 1.0 else 1.4
    mdot = mass_flow / 3600.0
    N_stg = max(int(stages), 1)

    # ---- Step 1: 压力比与 Regime 判定 (Eq.1-7) ----
    x_total = (p1 - p2) / p1                                       # Eq.1 总压差比
    if N_stg > 1:
        # P3-1: 几何分布 — 每级压力比 r_stage=(p2/p1)^(1/N)
        r_stage = (p2 / p1) ** (1.0 / N_stg)
        x = 1.0 - r_stage                                          # 每级压差比
    else:
        x = x_total
    flp_eff = flp if flp and flp > 0 else (fl if fl > 0 else 0.9)
    xvcc = 1.0 - (2.0 / (k + 1.0)) ** (k / (k - 1.0))       # Eq.3
    xC = flp_eff ** 2 * xvcc                                 # Eq.4
    alpha = (1.0 - xvcc) / max(1.0 - xC, 1e-9)               # Eq.5
    xB = 1.0 - (1.0 / alpha) * (1.0 / k) ** (k / (k - 1.0))  # Eq.6
    xCE = 1.0 - 1.0 / (22.0 * alpha)                         # Eq.7

    if x <= xC:
        regime_idx = 1
    elif x <= xvcc:
        regime_idx = 2
    elif x <= xB:
        regime_idx = 3
    elif x <= xCE:
        regime_idx = 4
    else:
        regime_idx = 5
    res.regime_index = regime_idx
    res.aeta = aeta_db
    if N_stg > 1:
        res.regime = f"气体气动-{N_stg}级-Regime {['I','II','III','IV','V'][regime_idx-1]}"
    else:
        res.regime = f"气体气动-Regime {['I','II','III','IV','V'][regime_idx-1]}"

    # ---- Step 2: 射流直径 Dj (Eq.9) ----
    cn_eff = cv_operating  # Cn ≈ Cv (简化; Excel 用 Cn=Fd²·Cv 或厂家表)
    Dj = 4.9e-3 * fd * math.sqrt(max(cn_eff * flp_eff, 1e-9))  # Eq.9
    res.jet_diameter_m = Dj

    # ---- Step 3: 缩脉条件 (Eq.32) ----
    # 缩脉压力比
    term_vc = 1.0 - x / (flp_eff ** 2)
    term_vc = max(term_vc, 1e-9)
    # 缩脉马赫数 Mvc (Eq.32)
    Mvc_sq = 2.0 / (k - 1.0) * (term_vc ** ((1.0 - k) / k) - 1.0)
    Mvc = math.sqrt(max(Mvc_sq, 0.0)) if Mvc_sq > 0 else 0.0
    res.vc_mach = Mvc
    # 缩脉声速 cvc
    cvc = math.sqrt(k * 1e5 * p1 / rho1 * term_vc ** ((k - 1.0) / k))
    # 临界缩脉声速 cvcc (xvcc 处)
    cvcc = math.sqrt(k * 1e5 * p1 / rho1 * (1.0 - xvcc) ** ((k - 1.0) / k))
    # 临界马赫数 Mj
    mj_arg = min(22.0, 1.0 / (alpha * max(1.0 - x, 1e-9)))
    Mj_sq = 2.0 / (k - 1.0) * (mj_arg ** ((k - 1.0) / k) - 1.0)
    Mj = math.sqrt(max(Mj_sq, 0.0)) if Mj_sq > 0 else 0.0
    res.critical_mach = Mj

    # ---- Step 4: 声功率（按 Regime） ----
    eta_factor = 10.0 ** aeta_db  # 10^Aeta
    if regime_idx == 1:
        Wm = mdot * (cvc * Mvc) ** 2 / 2.0
        eta = eta_factor * flp_eff ** 2 * Mvc ** 3
    elif regime_idx == 2:
        Wm = mdot * cvcc ** 2 / 2.0
        eta = eta_factor * (x / max(xvcc, 1e-9)) * max(Mj, 1e-6) ** (6.6 * flp_eff ** 2)
    elif regime_idx == 3:
        Wm = mdot * cvcc ** 2 / 2.0
        eta = eta_factor * max(Mj, 1e-6) ** (6.6 * flp_eff ** 2)
    else:  # IV, V
        Wm = mdot * cvcc ** 2 / 2.0
        eta = eta_factor * (Mj ** 2 / 2.0) * (math.sqrt(2.0) ** (6.6 * flp_eff ** 2))
    eta = min(max(eta, 1e-10), 0.5)
    Wa = eta * Wm
    res.stream_power_w = Wm
    res.acoustic_power_w = Wa

    # ---- Step 5: 声压级与传递损失 ----
    # 阀后条件
    pr = max(p2 / p1, 1e-6)
    T2 = T1 * (pr ** ((k - 1.0) / k))
    rho2 = p2 * molar_mass / (8.314 * T2)
    c2 = math.sqrt(k * R * T2)
    A_pipe = math.pi * (pipe_diameter_mm / 1000.0) ** 2 / 4.0
    U2 = mdot / (rho2 * A_pipe) if rho2 > 0 else 0.0
    Ma2 = U2 / c2 if c2 > 0 else 0.0
    res.mach_outlet = Ma2

    # 马赫数修正 Lg (Eq.16)
    Mp = min(0.3, Ma2)
    Lg = 16.0 * math.log10(1.0 / max(1.0 - Mp, 1e-6)) if Mp > 0 else 0.0

    # 内部声压级 Lpi (Eq.18/31)
    D = pipe_diameter_mm / 1000.0
    Lpi = 10.0 * math.log10(3.2e9 * Wa * rho2 * c2 / max(D * D, 1e-9)) + Lg
    res.internal_lw = Lpi

    # 峰值频率（按 Regime）
    St = NOISE_CFG["strouhal"]
    if regime_idx == 1:
        f_p = St * Mvc * cvc / max(Dj, 1e-9)
    elif regime_idx in (2, 3):
        f_p = St * Mj * cvcc / max(Dj, 1e-9)
    else:
        f_p = 1.4 * St * cvcc / (max(Dj, 1e-9) * math.sqrt(max(Mj ** 2 - 1, 1e-9)))
    res.noise_freq_peak = f_p

    # 管壁传声损失（简化，与 simplified 版相同框架）
    d_i = pipe_diameter_mm / 1000.0
    t = max(pipe_wall_mm, 1.0) / 1000.0
    m_pp = STEEL_RHO * t
    z_g = rho2 * c2
    if f_p > 0 and z_g > 0:
        ratio = (m_pp * 2.0 * math.pi * f_p) / z_g
        TL = 10.0 * math.log10(1.0 + ratio * ratio) + 10.0 * math.log10(m_pp / max(z_g * d_i, 1e-9))
    else:
        TL = NOISE_CFG["tl_floor"]
    TL = max(TL, NOISE_CFG["tl_floor"])
    res.transmission_loss = TL

    # 外部声压级 @1m (Eq.24)
    r = distance_m if distance_m > 0 else 1.0
    rad = 10.0 * math.log10(max((d_i + 2 * t) / (4.0 * r), 1e-6))
    LpA = Lpi - TL + rad + NOISE_CFG["a_weight_correction"]
    LpA = max(LpA, 75.0)  # IEC 下限
    res.noise_dba = LpA

    # 倍频程分析（可选，先计算并入 detail 字典）
    octave_bands = None
    if octave:
        octave_bands = _octave_band_analysis(Lpi, d_i, t, rho2, c2, r)

    res.detail = {
        "regime_idx": regime_idx, "regime_label": res.regime,
        "x": x, "x_total": x_total, "stages": N_stg,
        "xvcc": xvcc, "xC": xC, "xB": xB, "xCE": xCE, "alpha": alpha,
        "Dj_m": Dj, "Mvc": Mvc, "cvc": cvc, "cvcc": cvcc, "Mj": Mj,
        "Wm_W": Wm, "eta": eta, "Wa_W": Wa, "Lpi_dB": Lpi, "Lg_dB": Lg,
        "TL_dB": TL, "f_p_Hz": f_p, "LpA_dB": LpA,
        "T2_K": T2, "rho2": rho2, "c2_m_s": c2, "U2_m_s": U2, "Ma2": Ma2,
        "FLp": flp_eff, "Fd": fd, "Aeta": aeta_db,
        "P1": p1, "P2": p2,
    }
    if octave_bands is not None:
        res.detail["octave_bands"] = octave_bands
    if N_stg > 1:
        res.detail["x_stage"] = x
        res.detail["r_stage"] = r_stage
        # 估算避免阻塞所需最少级数 (StgNeeded 概念)
        xC_safe = max(xC, 1e-6)
        n_min = math.ceil(math.log(p2 / p1) / math.log(1.0 - xC_safe)) if xC_safe < 1 else 1
        res.detail["stages_needed"] = max(int(n_min), 1)
    if Ma2 > 0.3:
        res.warnings.append(f"阀后马赫数 {Ma2:.2f}>0.3，出口流速偏高，建议复核管径")
    if LpA > 85:
        res.warnings.append(f"预测噪音 {LpA:.0f} dB(A)>85，需考虑降噪措施")
    return res


# IEC 61672 A-weighting 曲线 (1/3 倍频程 500Hz~10kHz)
A_WEIGHT_BANDS = [
    (500.0, -3.2), (630.0, -1.9), (800.0, -0.8), (1000.0, 0.0),
    (1250.0, +0.6), (1600.0, +1.0), (2000.0, +1.2), (2500.0, +1.3),
    (3150.0, +1.2), (4000.0, +1.0), (5000.0, +0.5), (6300.0, -0.1),
    (8000.0, -1.1), (10000.0, -2.5),
]


def _octave_band_analysis(Lpi: float, d_i: float, t: float,
                          rho2: float, c2: float, r: float) -> dict:
    """1/3 倍频程频带分析 (IEC 61672 A 计权)。

    返回 {"bands": [...], "total_dba": float}
    每频带: TL(f) 含环频率/重合频率；频带声压级 → A 计权 → 能量叠加。
    """
    m_pp = STEEL_RHO * t
    z_g = rho2 * c2
    # 环频率与重合频率
    fr = 5000.0 / (math.pi * d_i) if d_i > 0 else 1.0
    fo = fr * c2 / (4.0 * 343.0)
    fg = math.sqrt(3.0) * 343.0 ** 2 / (math.pi * t * 5000.0) if t > 0 else 1e6

    bands = []
    total_pow = 0.0
    for freq, a_w in A_WEIGHT_BANDS:
        # 传声损失 TL(f) — 简化质量定律 + 重合修正
        if z_g > 0 and freq > 0:
            ratio = (m_pp * 2.0 * math.pi * freq) / z_g
            TL_f = 10.0 * math.log10(1.0 + ratio * ratio) + 10.0 * math.log10(
                m_pp / max(z_g * d_i, 1e-9))
        else:
            TL_f = NOISE_CFG["tl_floor"]
        # 重合区域附加损失
        if abs(freq - fo) / max(fo, 1.0) < 0.5:
            TL_f += 5.0  # 内部重合区域附加损失
        TL_f = max(TL_f, NOISE_CFG["tl_floor"])

        # 频带声压级（简化: 宽带平坦分配到 14 频带）
        Lp_band = Lpi - TL_f + 10.0 * math.log10(1.0 / 14.0)  # 1/N 分配
        LpA_band = Lp_band + a_w
        bands.append({
            "freq_Hz": freq, "spl_raw_dB": round(Lp_band, 1),
            "TL_dB": round(TL_f, 1), "a_weight_dB": a_w,
            "splA_dB": round(LpA_band, 1),
        })
        if LpA_band > 0:
            total_pow += 10.0 ** (LpA_band / 10.0)

    total_dba = 10.0 * math.log10(max(total_pow, 1e-15))
    rad = 10.0 * math.log10(max((d_i + 2 * t) / (4.0 * r), 1e-6))
    total_dba += rad + NOISE_CFG["a_weight_correction"]
    return {
        "bands": bands,
        "total_dba": round(total_dba, 1),
        "fr_Hz": fr, "fo_Hz": fo, "fg_Hz": fg,
    }


def predict_liquid_noise(
    *,
    cv_operating: float,
    fl: float,
    p1: float,
    p2: float,
    density: float,
    vapor_pressure: float,
    critical_pressure: float,
    mass_flow: float,
    pipe_diameter_mm: float,
    pipe_wall_mm: float,
    distance_m: float = 1.0,
) -> NoiseResult:
    """液体水动力噪音预测(IEC 60534-8-4 物理步骤)。

    液体噪音主要由湍流及空化/闪蒸引起。简化基于:
      机械功率 Pow = ½·ṁ·U_vc² ; 空化时声效率显著增大。
    """
    res = NoiseResult(method="IEC60534-8-4", regime="液体水动力")
    if p1 <= 0 or p2 <= 0 or mass_flow <= 0 or density <= 0 or pipe_diameter_mm <= 0:
        res.warnings.append("输入参数不足，无法计算噪音")
        return res

    dp = p1 - p2
    # 临界压差与空化判定 — Ff 三分支 (与 cv_liquid.py 一致)
    pc = critical_pressure if critical_pressure > 0 else 22064.0
    pv = vapor_pressure if vapor_pressure > 0 else 0.0
    if pv <= 0:
        ff = 0.96
    elif pc > 0 and pv < pc:
        ff = max(min(0.96 - 0.28 * math.sqrt(pv / pc), 1.0), 0.0)
    else:
        ff = 0.68
    fl = fl if 0 < fl < 1 else 0.9
    dp_choked = (fl ** 2) * (p1 - ff * pv)
    choked = dp >= dp_choked
    cavitating = choked and p2 > pv   # 空化
    flashing = p2 <= pv               # 闪蒸

    # 阀后流速
    A = math.pi * (pipe_diameter_mm / 1000.0) ** 2 / 4.0
    mdot = mass_flow / 3600.0
    U2 = mdot / (density * A)
    U_vc = U2 / fl
    res.vc_velocity = U_vc
    res.mach_outlet = 0.0
    Pow = 0.5 * mdot * U_vc * U_vc
    res.stream_power_w = Pow

    # 声效率: 单相湍流较小; 空化大幅增加; 闪蒸最大
    if flashing:
        eta = 1.0e-3
        res.regime = "液体水动力-闪蒸"
    elif cavitating:
        eta = 3.0e-4
        res.regime = "液体水动力-空化"
    else:
        eta = 5.0e-6 * max(dp / 100.0, 1.0)
        res.regime = "液体水动力-湍流"
    eta = min(max(eta, 1e-9), 0.5)
    Wa = eta * Pow
    res.acoustic_power_w = Wa
    Lwi = 10.0 * math.log10(max(Wa, 1e-15) / W_REF)
    res.internal_lw = Lwi

    # 峰值频率(液体, Strouhal on pipe)
    f_p = NOISE_CFG["strouhal"] * U_vc / (pipe_diameter_mm / 1000.0)
    res.noise_freq_peak = f_p

    # 管壁传声损失(液体介质声阻抗大)
    d_i = pipe_diameter_mm / 1000.0
    t = max(pipe_wall_mm, 1.0) / 1000.0
    m_pp = STEEL_RHO * t
    c_liq = 1400.0  # 水中声速近似
    z_l = density * c_liq
    if f_p > 0 and z_l > 0:
        ratio = (m_pp * 2.0 * math.pi * f_p) / z_l
        TL = 10.0 * math.log10(1.0 + ratio * ratio) + 10.0 * math.log10(m_pp / max(z_l * d_i, 1e-9))
    else:
        TL = NOISE_CFG["tl_floor"]
    # 液体管壁传声损失通常更高
    TL = max(TL + 6.0, NOISE_CFG["tl_floor"])
    res.transmission_loss = TL

    r = distance_m if distance_m > 0 else 1.0
    rad = 10.0 * math.log10(max(d_i / (4.0 * r), 1e-6))
    LpA = Lwi - TL + rad + NOISE_CFG["a_weight_correction"]
    res.noise_dba = LpA

    res.detail = {
        "U2_m_s": U2, "U_vc": U_vc, "FL": fl, "Pow_W": Pow, "eta": eta, "Wa_W": Wa,
        "Lwi_dB": Lwi, "TL_dB": TL, "f_p_Hz": f_p, "ΔP": dp, "ΔPch": dp_choked,
        "FF": ff, "Pv": pv, "choked": choked, "cavitating": cavitating, "flashing": flashing,
    }
    if cavitating or flashing:
        res.warnings.append(f"存在{'空化' if cavitating else '闪蒸'}，噪音及冲刷风险高")
    if LpA > 85:
        res.warnings.append(f"预测噪音 {LpA:.0f} dB(A)>85，需考虑降噪措施")
    return res
