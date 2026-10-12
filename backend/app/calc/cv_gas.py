"""气体/蒸汽 Cv 计算 (IEC 60534-2-1 膨胀系数法)

基本方程(质量流量):
    W[kg/h] = K_GAS · Fp · Cv · Y · √(x · P1[kPa] · ρ1[kg/m³])        ... (IEC Eq.11)
其中:
    x  = ΔP / P1                         压差比
    Y  = 1 − x / (3·Fγ·xT)               膨胀系数 (下限 0.667)
    Fγ = γ / 1.4                         比热比系数
    xT = 阀门临界压差比系数
阻塞(临界)流判定: x ≥ Fγ·xT → 临界(阻塞)，此时取 x=Fγ·xT, Y=0.667
"""
from __future__ import annotations

import math
from app.calc.cv_core import (
    ValveCoeffs, CvResult, K_GAS,
    compute_fp, xt_effective, reynolds_number,
)


def calculate_cv_gas(
    *,
    p1: float,                 # 阀前绝压 kPa(abs)
    p2: float,                 # 阀后绝压 kPa(abs)
    density: float,            # 阀前工况密度 kg/m³
    viscosity_cp: float,       # 动力粘度 cP(气体 ≈ μPa·s/1000)
    gamma: float,              # 比热比 cp/cv
    mass_flow: float = 0.0,    # 质量流量 kg/h
    vol_flow_op: float = 0.0,  # 工况体积流量 m³/h (阀前 P1,T1 下的体积，不是标况!)
    vc: ValveCoeffs,
    rated_cv_select: float = 0.0,
) -> CvResult:
    """计算气体/蒸汽所需 Cv 及流态判定。"""
    res = CvResult(phase="gas", density=density)
    res.dp = p1 - p2
    if res.dp <= 0 or p1 <= 0:
        res.warnings.append("压差或阀前压力无效")
        res.flow_regime = "无效"
        return res

    # 质量流量换算: vol_flow_op × 工况密度 = mass_flow
    #  (这是质量守恒 — 工况体积流量 × 工况密度 = 质量流量，任何标况/标准流量必须在进入此函数前
    #   由 convert_process_case 按 P1/T1 修正为工况 m³/h 再传入)
    if mass_flow <= 0 and vol_flow_op > 0 and density > 0:
        mass_flow = vol_flow_op * density   # ✓ 质量守恒
    if mass_flow <= 0:
        res.warnings.append("流量为0")
        res.flow_regime = "无效"
        return res
    res.mass_flow = mass_flow

    fp = compute_fp(vc)
    res.fp = fp
    xt = xt_effective(vc, fp)
    fgamma = (gamma if gamma > 0 else 1.4) / 1.4
    x = res.dp / p1
    res.x = x
    x_t_eff = fgamma * xt
    res.x_t_eff = x_t_eff

    # 临界(阻塞)判定
    choked = x >= x_t_eff
    res.choked = choked
    x_eff = min(x, x_t_eff)
    Y = 1.0 - x_eff / (3.0 * x_t_eff) if x_t_eff > 0 else 1.0
    Y = max(Y, 0.667)
    res.y = Y
    res.fl_eff = 0.0  # 气体不用 FL

    # Cv = W / (K_GAS·Fp·Y·√(x·P1·ρ1))
    inner = x_eff * p1 * density
    if inner <= 0:
        res.warnings.append("Cv 计算根号内≤0")
        res.flow_regime = "无效"
        return res
    denom = K_GAS * fp * Y * math.sqrt(inner)
    if denom <= 0:
        res.warnings.append("Cv 分母≤0")
        res.flow_regime = "无效"
        return res
    cv_required = mass_flow / denom
    res.cv_required = cv_required

    # xTP 精炼迭代：缩径且用户未提供 xTP 时，用 cv_operating=cv_required 重算 xTP (IEC Eq.33)
    if vc.reduced_port and vc.xtp is None:
        xt_refined = xt_effective(vc, fp, cv_operating=cv_required)
        if abs(xt_refined - xt) > 0.001:
            xt = xt_refined
            x_t_eff = fgamma * xt
            res.x_t_eff = x_t_eff
            choked = x >= x_t_eff
            res.choked = choked
            x_eff = min(x, x_t_eff)
            Y = 1.0 - x_eff / (3.0 * x_t_eff) if x_t_eff > 0 else 1.0
            Y = max(Y, 0.667)
            res.y = Y
            inner = x_eff * p1 * density
            if inner > 0:
                denom = K_GAS * fp * Y * math.sqrt(inner)
                if denom > 0:
                    cv_required = mass_flow / denom
                    res.cv_required = cv_required

    # ---- 开度二次修正: 用 FL(φ) 曲线迭代修正 xT/Cv ----
    rated = rated_cv_select or vc.rated_cv or cv_required
    fc = vc.factor_curves
    if fc and fc.fl and rated > 0:
        for _ in range(5):  # 最多迭代 5 次
            phi = max(min(cv_required / rated, 1.0), 0.0)
            fl_phi = fc.fl.eval(phi)
            xt_phi = 0.84 * fl_phi * fl_phi           # xT = 0.84·FL² (与前端一致)
            x_t_eff_phi = fgamma * xt_phi
            choked_phi = x >= x_t_eff_phi
            x_eff_phi = min(x, x_t_eff_phi)
            Y_phi = 1.0 - x_eff_phi / (3.0 * x_t_eff_phi) if x_t_eff_phi > 0 else 1.0
            Y_phi = max(Y_phi, 0.667)
            inner_phi = x_eff_phi * p1 * density
            if inner_phi <= 0:
                break
            denom_phi = K_GAS * fp * Y_phi * math.sqrt(inner_phi)
            if denom_phi <= 0:
                break
            cv_new = mass_flow / denom_phi
            phi_new = max(min(cv_new / rated, 1.0), 0.0)
            cv_required = cv_new
            if abs(phi_new - phi) < 0.001:
                break
        # 用收敛值更新结果
        xt = xt_phi
        x_t_eff = x_t_eff_phi
        choked = choked_phi
        Y = Y_phi
        res.cv_required = cv_required
        res.x_t_eff = x_t_eff
        res.y = Y
        res.choked = choked
        _corrected = {
            "FL_phi": fl_phi, "xT_phi": xt_phi, "phi_final": phi_new,
            "iterations": _ + 1,
        }

    rev = reynolds_number(vc, density, viscosity_cp, mass_flow, cv_required)
    res.reynolds = rev  # 气体一般高雷诺数，不需粘度修正

    res.flow_regime = "临界(阻塞)" if choked else "亚临界(非阻塞)"
    if choked:
        res.warnings.append("达到临界压差比，流量已阻塞(壅塞)")

    res.cv_rated_selected = rated
    res.opening_pct = (cv_required / rated * 100.0) if rated > 0 else 0.0

    res.detail = {
        "x": x, "xT": xt, "xTP": xt, "Fγ": fgamma, "Fγ·xT": x_t_eff, "Y": Y, "Fp": fp,
        "γ": gamma, "ρ1": density, "ΔP_kPa": res.dp, "P1_kPa": p1,
        "cv_required": cv_required, "rated_cv": rated, "mass_flow_kgh": mass_flow,
    }
    if fc and fc.fl:
        res.detail["opening_corrected"] = _corrected
    if res.opening_pct > 100:
        res.warnings.append(f"所需Cv({cv_required:.1f})>额定Cv({rated:.1f})，阀门偏小")
    return res
