"""两相流 Cv 计算

气液两相(湿气/闪蒸)混合流，IEC 60534-2-1 未给出单一标准方程。本实现提供三种可切换方法:

方法 A(默认, 叠加法 additive):
    将气相与液相分别按各自公式计算所需 Cv，再相加:
        Cv = Cv_gas + Cv_liquid
    适用: 气液混合、不凝气夹带液体；保守、工程常用。

方法 B(均相膨胀系数法 homogeneous):
    按均相混合密度 ρmix = 1/(x_g/ρg + x_l/ρl) 处理，采用气体膨胀系数方程，
    Y 与 xT 取气相参数。适用: 湿气为主、相间平衡的工况。

方法 C(IEC 60534-2-1 Annex C iec_annexc):
    与 Excel Cv_2.1.xlsm LiqGas Sheet 完全一致的标准公式:
        C = (1/(31.6·Fp)) · √[(Wf+Wg) · (Wf/(ρ1f·ΔPfe) + Wg/(ρ1g·Y²·ΔPge))]
    分别考虑液/气相的有效压差 (考虑阻塞/FL/xT)，得到一个统一 Cv。
    适用: 正规工业选型、与 Excel Cv_2.1 对标。

质量含气率 x_g = m_gas / (m_gas + m_liquid) 由两组分流量确定。
"""
from __future__ import annotations

import math
from app.calc.cv_core import ValveCoeffs, CvResult, K_GAS, K_LIQ, compute_fp, xt_effective, fl_effective


def calculate_cv_twophase(
    *,
    p1: float,
    p2: float,
    density_gas: float,        # 阀前气相密度 kg/m³
    density_liquid: float,     # 阀前液相密度 kg/m³
    viscosity_cp: float,
    gamma: float,
    vapor_pressure_kpa: float = 0.0,  # Annex C 液相阻塞 Ff·Pv 用
    critical_pressure_kpa: float = 0.0,
    pv_liquid: float = 0.0,           # 兼容变量名 (vapor_pressure_kpa 的别名)
    mass_flow_gas: float = 0.0,
    mass_flow_liquid: float = 0.0,
    vc: ValveCoeffs,
    method: str = "additive",  # additive / homogeneous / iec_annexc
    rated_cv_select: float = 0.0,
) -> CvResult:
    """两相流 Cv 计算。

    method:
        'additive'  - 叠加法 (默认, 保守)
        'homogeneous' - 均相膨胀系数法
        'iec_annexc' - IEC 60534-2-1 Annex C (与 Excel Cv_2.1 LiqGas 一致)
    """
    res = CvResult(phase="twophase")
    res.dp = p1 - p2
    if res.dp <= 0 or p1 <= 0:
        res.warnings.append("压差或阀前压力无效")
        res.flow_regime = "无效"
        return res
    mt = mass_flow_gas + mass_flow_liquid
    if mt <= 0:
        res.warnings.append("总质量流量为0")
        res.flow_regime = "无效"
        return res
    res.mass_flow = mt
    x_g = mass_flow_gas / mt
    res.detail["质量含气率x_g"] = x_g

    fp = compute_fp(vc)
    res.fp = fp
    x = res.dp / p1
    res.x = x
    xt = xt_effective(vc, fp)
    fgamma = (gamma if gamma > 0 else 1.4) / 1.4
    x_t_eff = fgamma * xt
    res.x_t_eff = x_t_eff
    choked = x >= x_t_eff
    res.choked = choked
    x_eff = min(x, x_t_eff)
    Y = max(1.0 - x_eff / (3.0 * x_t_eff) if x_t_eff > 0 else 1.0, 0.667)
    res.y = Y

    if method == "iec_annexc":
        # ================================================================
        # IEC 60534-2-1 Annex C  — 与 Excel Cv_2.1.xlsm LiqGas 公式一致
        #
        # C = (1/(31.6·Fp)) · √( (Wf+Wg) · ( Wf/(ρ1f·ΔPfe) + Wg/(ρ1g·Y²·ΔPge) ) )
        #
        # 有效压差 (各自考虑阻塞):
        #   ΔPfe = min(ΔP, FLp²·(P1 - Ff·Pv))        液相
        #   ΔPge = min(ΔP, Fγ·xTP·P1) = x_eff · P1   气相
        #
        # Ff (液体临界压比系数) = 0.96 - 0.28·√(Pv/Pc)；若 Pv≥Pc, Ff=0.68
        # 31.6 为 K_LIQ (Excel 在 LiqGas 中常数值)
        # ================================================================
        # 阻塞压力计算
        pv = pv_liquid if pv_liquid and pv_liquid > 0 else (vapor_pressure_kpa or 0.0)
        pc = critical_pressure_kpa
        if pv <= 0:
            Ff = 0.96  # 无蒸汽压数据 → 近似无闪蒸
        elif pc and pc > 0 and pv < pc:
            Ff = 0.96 - 0.28 * math.sqrt(pv / pc)
        else:
            Ff = 0.68  # 兜底: Excel IEC Eq.12 的 Pv≥Pc 情况
        # 有效 FL（考虑缩径时用 Flp；此处若 FLp 缺省近似取 FL 本身）
        fl_eff = fl_effective(vc, fp)
        # 液相有效压差 (阻塞压差 ΔPchoked = Fl²·(P1-Ff·Pv))
        dp_choked_f = (fl_eff ** 2) * (p1 - Ff * pv)
        dp_fe = min(res.dp, dp_choked_f)
        # 气相有效压差 (阻塞压差 ΔPchoked = x_eff·P1)
        dp_ge = x_eff * p1
        if dp_fe <= 0 or dp_ge <= 0:
            res.warnings.append("Annex C: 液/气相有效压差≤0，数据异常")
            res.flow_regime = "无效"
            return res
        # 两相加权项 — 系统统一使用 kPa 体系 K_LIQ
        # 等价形式 (IEC Annex C 变形):
        #   Cv_req² = (Wf/(K_LIQ·Fp))² / (ρf·ΔPfe) + (Wg/(K_GAS·Fp·Y))² / (ρg·ΔPge)
        # 但 Excel 原始公式是对两者先加再开根，所以以 IEC Annex C 标准量纲为准
        #   Cv = (1/K_LIQ/Fp) · √( (Wf+Wg)·(Wf/(ρf·ΔPfe) + Wg/(ρg·Y²·ΔPge)) )
        # 注意 Annex C 原本使用质量单位 kg/h、ΔP(kPa) 对应 K_LIQ = √(1000) × N1'
        # 这里直接用项目的 K_LIQ（kPa 体系，已经校验过水算例）
        term_f = 0.0
        if mass_flow_liquid > 0 and density_liquid > 0:
            term_f = mass_flow_liquid / (density_liquid * dp_fe)
        term_g = 0.0
        if mass_flow_gas > 0 and density_gas > 0:
            Y_sq = max(Y, 0.667) ** 2
            term_g = mass_flow_gas / (density_gas * Y_sq * dp_ge)
        inside = mt * (term_f + term_g)
        if inside <= 0:
            res.warnings.append("Annex C: 根号内≤0")
            res.flow_regime = "无效"
            return res
        cv_required = (1.0 / (K_LIQ * fp)) * math.sqrt(inside)
        res.detail["Ff"] = Ff
        res.detail["ΔPfe_kPa"] = dp_fe
        res.detail["ΔPge_kPa"] = dp_ge
        res.detail["Y_sq"] = Y * Y
        res.detail["FL_eff"] = fl_eff
        res.detail["Pv_kPa"] = pv
        choked_f = res.dp > dp_choked_f
        choked_g = bool(res.dp > dp_ge)
        regime_bits = []
        if choked_f: regime_bits.append("液相阻塞")
        if choked_g: regime_bits.append("气相阻塞")
        res.flow_regime = ("临界(阻塞)-Annex C[" + "/".join(regime_bits) + "]") if regime_bits else "亚临界-Annex C"

    elif method == "singleton":
        # ================================================================
        # Singleton (1991) 并联模型 — 湿蒸汽(单组分气液混合物)专用
        # 参考: Excel Cv_2.1.xlsm WtrStm Sheet; docs §8 line 374
        # 与 Annex C 结构类似，但使用并联等效密度:
        #   ρ1fe = ρ_liquid / (1-Q)     液相
        #   ρ1ge = ρ_gas · Y² / Q       气相
        #   Cv = (1/(K_LIQ·Fp)) · √(W_total · (1/(ρ1fe·ΔPfe) + 1/(ρ1ge·ΔPge)))
        # ================================================================
        if density_gas <= 0 or density_liquid <= 0:
            res.warnings.append("Singleton 法需要饱和气/液相密度均>0")
            res.flow_regime = "无效"
            return res
        if not (0.0 < x_g < 1.0):
            res.warnings.append(f"Singleton 法需要 0<Q<1，当前 Q={x_g:.4f}")
            res.flow_regime = "无效"
            return res

        # 有效压差（与 Annex C 相同的 Ff/FL/xT 阻塞判定）
        fl_eff = fl_effective(vc, fp)
        pv = pv_liquid if pv_liquid and pv_liquid > 0 else (vapor_pressure_kpa or 0.0)
        pc = critical_pressure_kpa
        if pv <= 0:
            Ff = 0.96
        elif pc and pc > 0 and pv < pc:
            Ff = 0.96 - 0.28 * math.sqrt(pv / pc)
            Ff = max(min(Ff, 1.0), 0.0)
        else:
            Ff = 0.68
        dp_choked_f = (fl_eff ** 2) * (p1 - Ff * pv)
        dp_fe = min(res.dp, dp_choked_f)
        dp_ge = x_eff * p1
        if dp_fe <= 0 or dp_ge <= 0:
            res.warnings.append("Singleton: 液/气相有效压差≤0")
            res.flow_regime = "无效"
            return res

        # Singleton 并联等效密度
        rho1fe = density_liquid / (1.0 - x_g)
        rho1ge = density_gas * (Y * Y) / x_g

        inside = (1.0 / (rho1fe * dp_fe)) + (1.0 / (rho1ge * dp_ge))
        if inside <= 0:
            res.warnings.append("Singleton: 根号内≤0")
            res.flow_regime = "无效"
            return res
        cv_required = (1.0 / (K_LIQ * fp)) * math.sqrt(mt * inside)
        res.density = 1.0 / (x_g / density_gas + (1.0 - x_g) / density_liquid)
        res.detail["Ff"] = Ff
        res.detail["ΔPfe_kPa"] = dp_fe
        res.detail["ΔPge_kPa"] = dp_ge
        res.detail["FL_eff"] = fl_eff
        res.detail["ρ1fe"] = rho1fe
        res.detail["ρ1ge"] = rho1ge
        res.detail["quality_Q"] = x_g
        choked_f = res.dp > dp_choked_f
        choked_g = bool(res.dp > dp_ge)
        bits = []
        if choked_f: bits.append("液相阻塞")
        if choked_g: bits.append("气相阻塞")
        res.flow_regime = (f"湿蒸汽-Singleton[{','.join(bits)}]"
                           if bits else "湿蒸汽-Singleton(亚临界)")

    elif method == "homogeneous":
        # 均相混合密度
        if density_gas <= 0 or density_liquid <= 0:
            res.warnings.append("均相法需要气/液相密度均>0")
            res.flow_regime = "无效"
            return res
        rho_mix = 1.0 / (x_g / density_gas + (1 - x_g) / density_liquid)
        res.density = rho_mix
        inner = x_eff * p1 * rho_mix
        if inner <= 0:
            res.warnings.append("Cv 计算根号内≤0")
            res.flow_regime = "无效"
            return res
        cv_required = mt / (K_GAS * fp * Y * math.sqrt(inner))
        res.flow_regime = "临界(阻塞)-均相" if choked else "亚临界-均相"
    else:  # additive (默认)
        # 气相 Cv
        cv_gas = 0.0
        if mass_flow_gas > 0 and density_gas > 0:
            inner_g = x_eff * p1 * density_gas
            if inner_g > 0:
                cv_gas = mass_flow_gas / (K_GAS * fp * Y * math.sqrt(inner_g))
        # 液相 Cv (非阻塞近似, 用全 ΔP)
        cv_liq = 0.0
        if mass_flow_liquid > 0 and density_liquid > 0:
            dp_use = max(res.dp, 0)
            if dp_use > 0:
                cv_liq = mass_flow_liquid / (K_LIQ * fp * math.sqrt(dp_use * density_liquid))
        cv_required = cv_gas + cv_liq
        res.density = 0.0  # 混合密度无单一值
        res.detail["Cv_gas"] = cv_gas
        res.detail["Cv_liquid"] = cv_liq
        res.flow_regime = "临界(阻塞)-叠加" if choked else "亚临界-叠加"

    res.cv_required = cv_required
    rated = rated_cv_select or vc.rated_cv or cv_required
    res.cv_rated_selected = rated
    res.opening_pct = (cv_required / rated * 100.0) if rated > 0 else 0.0
    res.detail.update({
        "method": method, "x": x, "Fγ·xT": x_t_eff, "Y": Y, "Fp": fp,
        "cv_required": cv_required, "rated_cv": rated, "mass_flow_total": mt,
    })
    if res.opening_pct > 100:
        res.warnings.append(f"所需Cv({cv_required:.1f})>额定Cv({rated:.1f})，阀门偏小")
    if method == "additive":
        res.warnings.append("两相采用叠加法(保守)，如需与 Excel 一致请切换为 IEC Annex C 模型")
    elif method == "iec_annexc":
        res.warnings.append("两相采用 IEC 60534-2-1 Annex C，与 Excel Cv_2.1 LiqGas 模型一致")
    elif method == "singleton":
        res.warnings.append("湿蒸汽采用 Singleton 并联模型，需饱和气/液相密度数据")
    return res
