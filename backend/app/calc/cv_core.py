"""Cv 计算引擎 - 共享定义与阀门系数工具

单位约定(全引擎统一):
  压力 kPa(abs), 压差 kPa, 温度 ℃, 密度 kg/m³, 流量 m³/h(液) 或 kg/h(质量) 或 Nm³/h(气标况)
  口径 mm, 粘度 cP(=mPa·s), Cv 采用美制(US gpm/psi)。

关键数值常数(kPa 体系, Cv)，均由量纲推导并经算例验证:
  K_LIQ : 液体  Q[m³/h] = K_LIQ · Cv · √(ΔP[kPa] / ρ[kg/m³])
  K_GAS : 气体  W[kg/h] = K_GAS · Cv · Y · √(x · P1[kPa] · ρ1[kg/m³])
  N2    : Fp 计算用 (d 单位 mm) = 0.00214

参考标准: IEC 60534-2-1, GB/T 17213.2, ISA-75.01.01
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Optional

# ---------------------------------------------------------------------------
# 数值常数
# ---------------------------------------------------------------------------
K_LIQ = 2.7351   # 液体 Cv 流量方程系数 (kPa 体系, Cv 美制)  [算例验证: 水 Q120 ΔP460 → Cv64.7]
K_GAS = 2.7330   # 气体质量流量 Cv 方程系数 (kPa 体系, Cv 美制) [由 ISA N6=63.3 量纲换算得]
N2 = 0.00214     # Fp/Flp 管件计算用系数 (d 单位 mm, IEC Eq.20/30)
N5_PRIME = 0.00241  # xTP 管件计算用系数 (d 单位 mm, IEC Eq.33)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class FactorCurve:
    """单条因子曲线的 4 次多项式系数: f(φ) = P4·φ⁴ + P3·φ³ + P2·φ² + P1·φ + P0
    φ 为开度 (0~1), 结果钳制到 [value_min, value_max]。
    """
    p0: float = 0.0
    p1: float = 0.0
    p2: float = 0.0
    p3: float = 0.0
    p4: float = 0.0
    value_min: Optional[float] = None
    value_max: Optional[float] = None

    def eval(self, phi: float) -> float:
        """在开度 φ (0~1) 处求值, 钳制到 [value_min, value_max]"""
        if phi <= 0:
            v = self.p0
        else:
            v = ((((self.p4 * phi + self.p3) * phi + self.p2) * phi + self.p1) * phi + self.p0)
        if self.value_min is not None:
            v = max(v, self.value_min)
        if self.value_max is not None:
            v = min(v, self.value_max)
        return v


@dataclass
class FactorCurves:
    """开度相关的计算因数曲线集 (来自 Curve Feature Values 多项式系数)"""
    fl: Optional[FactorCurve] = None  # FL(φ) 液体压力恢复系数
    kc: Optional[FactorCurve] = None  # Kc(φ) 空化系数
    fd: Optional[FactorCurve] = None  # Fd(φ) 阀门型式修正系数

    @classmethod
    def from_dict(cls, d: dict) -> "FactorCurves":
        """从 JSON dict 构造 (兼容 curve_coeffs 字段)"""
        if not d or not isinstance(d, dict):
            return cls()
        def _parse(c):
            if not c or not isinstance(c, dict):
                return None
            return FactorCurve(
                p0=float(c.get("p0") or 0), p1=float(c.get("p1") or 0),
                p2=float(c.get("p2") or 0), p3=float(c.get("p3") or 0),
                p4=float(c.get("p4") or 0),
                value_min=float(c["value_min"]) if c.get("value_min") is not None else None,
                value_max=float(c["value_max"]) if c.get("value_max") is not None else None,
            )
        return cls(fl=_parse(d.get("fl")), kc=_parse(d.get("kc")), fd=_parse(d.get("fd")))


@dataclass
class ValveCoeffs:
    """阀门计算系数(IEC 60534-2-1)"""
    rated_cv: float = 0.0          # 额定 Cv
    fl: float = 0.9                # 液体压力恢复系数 FL (无附件)
    flp: Optional[float] = None    # 带附件 FLp (留空=用 FL)
    fp: Optional[float] = None     # 管件几何系数 Fp (留空=按几何算或取1)
    xt: float = 0.72               # 临界压差比 xT (无附件)
    xtp: Optional[float] = None    # 带附件 xTp
    fd: float = 0.46               # 阀门类型修正系数 FD (噪音用)
    port_diameter: Optional[float] = None  # 阀座口径 mm
    pipe_diameter: Optional[float] = None  # 管道内径 mm
    reduced_port: bool = False     # 是否缩径(影响 Fp)
    stages: int = 1                # 降噪级数 (1=单级, >1=多级降噪阀)
    factor_curves: Optional[FactorCurves] = None  # 开度相关因子曲线 (二次修正用)


@dataclass
class CvResult:
    """单组工况 Cv 计算结果"""
    cv_required: float = 0.0           # 所需 Cv
    cv_rated_selected: float = 0.0    # 选用额定 Cv
    opening_pct: float = 0.0          # 开度 %
    flow_regime: str = ""             # 流态: 非阻塞/阻塞/临界/闪蒸/空化/亚临界
    dp: float = 0.0                   # 实际压差 kPa
    dp_choked: float = 0.0            # 临界压差 kPa
    x: float = 0.0                    # 压差比 x = ΔP/P1
    x_t_eff: float = 0.0              # 有效临界压差比 Fγ·xT
    y: float = 1.0                    # 膨胀系数(气体)
    fl_eff: float = 0.0               # 有效 FL
    fp: float = 1.0                   # 管件几何系数
    reynolds: float = 0.0             # 雷诺数(阀门口径特征)
    choked: bool = False              # 是否阻塞流
    phase: str = ""                   # 介质相态 liquid/gas/twophase
    mass_flow: float = 0.0            # 质量流量 kg/h
    vol_flow: float = 0.0             # 体积流量 m³/h
    density: float = 0.0              # 工况密度 kg/m³
    warnings: list = field(default_factory=list)
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# 阀门系数工具
# ---------------------------------------------------------------------------
def _iecfittings(vc: ValveCoeffs) -> tuple:
    """IEC 60534-2-1 管件阻力系数 K1/K2/KB1/KB2 (Eq.20 前置)。

    K1 (进口): d<D 时 0.5*(1-β²)²;  d≥D 时 (1-(D/d)²)²/(D/d)^4
    K2 (出口): 同 K1
    KB1=KB2 = 1-β^4 (Bernoulli 系数)
    β = d/D (阀座口径/管道内径)

    无几何参数时返回 (0,0,0,0)。
    """
    d = vc.port_diameter
    D = vc.pipe_diameter
    if not d or not D or d <= 0 or D <= 0:
        return (0.0, 0.0, 0.0, 0.0)
    beta = d / D
    if beta >= 0.999:
        return (0.0, 0.0, 0.0, 0.0)
    if d < D:
        # 缩径: 标准 reducer
        K1 = 0.5 * (1.0 - beta * beta) ** 2
        K2 = 1.0 * (1.0 - beta * beta) ** 2
    else:
        # 扩径 (d≥D, 罕见)
        ratio = D / d
        K1 = 0.5 * (1.0 - ratio * ratio) ** 2 / (ratio ** 4)
        K2 = 1.0 * (1.0 - ratio * ratio) ** 2 / (ratio ** 4)
    KB1 = 1.0 - beta ** 4
    KB2 = KB1
    return (K1, K2, KB1, KB2)


def compute_fp(vc: ValveCoeffs, cv_operating: Optional[float] = None) -> float:
    """计算管件几何系数 Fp (IEC 60534-2-1 Eq.20)。

    若用户提供 fp 直接采用；否则当缩径且有几何尺寸时按 IEC Eq.20 计算；否则取 1.0。
    cv_operating: 工作点 Cv(用于迭代)，缺省用额定 Cv。
    """
    if vc.fp is not None:
        return vc.fp
    d = vc.port_diameter
    D = vc.pipe_diameter
    if not vc.reduced_port or not d or not D or D <= 0 or d <= 0:
        return 1.0
    cv = cv_operating if cv_operating else vc.rated_cv
    if cv <= 0 or d <= 0:
        return 1.0
    beta = d / D
    if beta >= 0.999:
        return 1.0
    # IEC Eq.20: Fp = 1/√(1 + (K1+K2+KB1-KB2)·Cd²/N2)
    K1, K2, KB1, KB2 = _iecfittings(vc)
    cd = cv / (d * d)  # 相对容量 Cv/d² (d 单位 mm)
    denom_term = (K1 + K2 + KB1 - KB2) * (cd ** 2) / N2
    fp = 1.0 / math.sqrt(1.0 + denom_term)
    return max(min(fp, 1.0), 0.1)


def fl_effective(vc: ValveCoeffs, fp: float,
                 cv_operating: Optional[float] = None) -> float:
    """有效液体压力恢复系数 (IEC 60534-2-1)。

    优先级: 用户提供 Flp > IEC Eq.30 计算 > 裸 FL。
    cv_operating: 工作点 Cv (Eq.30 需要)，缺省用额定 Cv。
    """
    if vc.flp is not None and vc.flp > 0:
        return vc.flp
    d = vc.port_diameter
    D = vc.pipe_diameter
    if vc.reduced_port and d and D and d > 0 and D > 0 and d < D:
        K1, _, KB1, _ = _iecfittings(vc)
        cv = cv_operating if cv_operating and cv_operating > 0 else vc.rated_cv
        if cv > 0 and d > 0:
            cd = cv / (d * d)
            # IEC Eq.30: Flp = FL / √(1 + FL²·(K1+KB1)·Cd²/N2)
            denom = 1.0 + (vc.fl ** 2) * (K1 + KB1) * (cd ** 2) / N2
            flp_calc = vc.fl / math.sqrt(denom)
            return max(min(flp_calc, vc.fl), 0.1)  # Flp ≤ FL
    return vc.fl


def xt_effective(vc: ValveCoeffs, fp: float,
                 cv_operating: Optional[float] = None) -> float:
    """有效临界压差比 xT (IEC 60534-2-1)。

    优先级: 用户提供 xTp > IEC Eq.33 计算 > 裸 xT。
    cv_operating: 工作点 Cv (Eq.33 需要)，缺省用额定 Cv。
    """
    if vc.xtp is not None and vc.xtp > 0:
        return vc.xtp
    d = vc.port_diameter
    D = vc.pipe_diameter
    if vc.reduced_port and d and D and d > 0 and D > 0 and d < D:
        K1, _, KB1, _ = _iecfittings(vc)
        cv = cv_operating if cv_operating and cv_operating > 0 else vc.rated_cv
        if cv > 0 and d > 0 and fp > 0 and vc.xt > 0:
            cd = cv / (d * d)
            # IEC Eq.33: xTP = (xT/Fp²) / (1 + xT·(K1+KB1)·Cd²/N5')
            denom = 1.0 + vc.xt * (K1 + KB1) * (cd ** 2) / N5_PRIME
            xtp_calc = (vc.xt / (fp * fp)) / denom
            return max(min(xtp_calc, vc.xt), 0.01)
    return vc.xt


def reynolds_number(vc: ValveCoeffs, density: float, viscosity_cp: float,
                    mass_flow: float, cv_operating: float) -> float:
    """阀门特征雷诺数(基于阀座口径流速)。

    Rev = ρ·U·d / μ ; U = (mass_flow/3600)/(ρ·A) , A=π·d²/4
    """
    d = vc.port_diameter
    if not d or d <= 0 or density <= 0 or viscosity_cp <= 0:
        return 0.0
    A = math.pi * d * d / 4.0 * 1e-6  # mm² -> m²
    U = (mass_flow / 3600.0) / (density * A)  # m/s
    mu_pa = viscosity_cp * 1e-3  # cP -> Pa·s
    Rev = density * U * (d / 1000.0) / mu_pa
    return Rev


def check_reynolds_correction(rev: float) -> tuple:
    """根据雷诺数判断是否需要粘度修正(IEC)。返回 (需修正, 提示)。"""
    if rev <= 0:
        return False, ""
    if rev < 40:
        return True, f"层流区(Rev={rev:.0f}<40)，已应用 IEC 粘度修正 Fr"
    if rev < 3000:
        return True, f"过渡区(Rev={rev:.0f})，已应用 IEC 粘度修正 Fr"
    return False, ""


def reynolds_factor(rev: float, fl: float, cd: float) -> float:
    """IEC 60534-2-1 Annex G 雷诺数修正系数 Fr (0,1]。

    Rev < 10000 时 Fr<1，Cv 需除以 Fr 以补偿低雷诺数区有效系数下降。
    公式来源: Cv_2.1.xlsm Liquid E99-E100 (IEC Eq.G.1a/G.2/G.3a/G.4):

    n 层流系数 (Eq.G.1b / G.3b):
        n = 0.00214/Cd²   (Cd ≥ 0.016)
        n = 1 + 127·Cd^(2/3) (Cd < 0.016)
    Fr (Eq.G.1a/G.2/G.3a/G.4):
        Rev < 10:   Fr = (0.026/Fl)·√(n·Rev)
        Rev < 10000:Fr = min(1,
                   1 + (0.33·√Fl / n^0.25)·log10(Rev/10000),
                   (0.026/Fl)·√(n·Rev))
        Rev ≥ 10000: Fr = 1
    参数:
        rev: 阀座雷诺数
        fl:  液体压力恢复系数 FL
        cd:  相对容量 Cv/d² (d 单位 mm)
    """
    if rev <= 0:
        return 1.0
    if rev >= 10000:
        return 1.0
    fl_in = fl if fl > 0 else 0.9
    cd_in = cd if cd > 0 else 0.016  # 兜底取边界值

    # 层流系数 n (注意: 常数 0.00214 与 d 单位 mm、Cv 单位一致)
    if cd_in >= 0.016:
        n = 0.00214 / (cd_in * cd_in)
    else:
        n = 1.0 + 127.0 * (cd_in ** (2.0 / 3.0))

    sqrt_n_rev = math.sqrt(n * max(rev, 1e-9))
    fr_a = (0.026 / fl_in) * sqrt_n_rev         # Eq.G.1a 下限

    if rev < 10:
        fr = fr_a
    else:
        # 湍流过渡式 Eq.G.2: 1 + 0.33·√Fl·log10(Rev/10000)/n^0.25
        fl_sqrt = math.sqrt(fl_in)
        n_4 = n ** 0.25
        log_term = math.log10(rev / 10000.0)
        fr_b = 1.0 + (0.33 * fl_sqrt / n_4) * log_term  # Rev<10000 时该项<1
        fr = min(1.0, max(fr_a, fr_b))
        fr = min(fr, fr_a)  # 保证：Fr 不超过层流下限公式(Eq.G.4)

    return max(min(fr, 1.0), 0.001)
