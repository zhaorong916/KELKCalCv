"""液体 Cv 计算 (IEC 60534-2-1 / GB/T 17213.2 / ISA-75.01.01)

基本方程(非阻塞湍流):
    Q[m³/h] = K_LIQ · Fp · Cv · √(ΔP[kPa] / ρ[kg/m³])           ... (IEC Eq.6/7)
    W[kg/h] = K_LIQ · Fp · Cv · √(ΔP[kPa] · ρ[kg/m³])           (质量流量形式)

阻塞(堵塞)流判定 (IEC Eq.3):
    FF   = 0.96 − 0.28·√(Pv/Pc)                                 液体临界压力比系数
    ΔPch = FL² · (P1 − FF·Pv)                                    临界压差
    若 ΔP ≥ ΔPch → 阻塞流(闪蒸/空化)，计算采用 ΔPch

闪蒸/空化判定:
    Pv = 介质饱和蒸汽压；P2 与 Pv 关系决定闪蒸(阀后)或空化(阀内)
"""
from __future__ import annotations

import math
from app.calc.cv_core import (
    ValveCoeffs, CvResult, K_LIQ, N2,
    compute_fp, fl_effective, reynolds_number, check_reynolds_correction,
    reynolds_factor,
)


def calculate_cv_liquid(
    *,
    p1: float,                 # 阀前绝压 kPa(abs)
    p2: float,                 # 阀后绝压 kPa(abs)
    density: float,            # 工况密度 kg/m³
    viscosity_cp: float,       # 动力粘度 cP
    vapor_pressure: float,     # 饱和蒸汽压 kPa(abs)
    critical_pressure: float,  # 临界压力 kPa(abs)
    mass_flow: float = 0.0,    # 质量流量 kg/h
    vol_flow: float = 0.0,     # 体积流量 m³/h
    vc: ValveCoeffs,
    rated_cv_select: float = 0.0,  # 选用额定Cv(用于开度)，0=用额定
) -> CvResult:
    """计算液体所需 Cv 及流态判定。"""
    res = CvResult(phase="liquid", density=density)
    res.dp = p1 - p2

    if res.dp <= 0:
        res.warnings.append("阀前后压差 ΔP≤0，无法计算")
        res.flow_regime = "无效"
        return res

    # 流量统一为质量流量
    if mass_flow <= 0 and vol_flow > 0:
        mass_flow = vol_flow * density
    if mass_flow <= 0:
        res.warnings.append("流量为0")
        res.flow_regime = "无效"
        return res
    res.mass_flow = mass_flow
    res.vol_flow = mass_flow / density

    # 阀门系数
    fp = compute_fp(vc)
    res.fp = fp
    fl = fl_effective(vc, fp)
    res.fl_eff = fl

    # 临界压差(IEC Eq.3) — Ff 三分支（与 cv_twophase Annex C 一致）
    pc = critical_pressure if critical_pressure > 0 else 22064.0
    pv = vapor_pressure if vapor_pressure > 0 else 0.0
    if pv <= 0:
        ff = 0.96
    elif pc > 0 and pv < pc:
        ff = 0.96 - 0.28 * math.sqrt(pv / pc)
        ff = max(min(ff, 1.0), 0.0)
    else:
        ff = 0.68   # Pv≥Pc 近临界兜底 (IEC Eq.12)
    dp_choked = (fl ** 2) * (p1 - ff * pv)
    dp_choked = max(dp_choked, 0.0)
    res.dp_choked = dp_choked

    # 阻塞流判定
    choked = res.dp >= dp_choked
    res.choked = choked
    dp_eff = min(res.dp, dp_choked)  # 阻塞时采用临界压差

    # Cv 计算(质量流量形式): W = K_LIQ·Fp·Cv·√(ΔP·ρ) → Cv = W/(K_LIQ·Fp·√(ΔP·ρ))
    denom = K_LIQ * fp * math.sqrt(dp_eff * density) if (dp_eff * density) > 0 else 0.0
    if denom <= 0:
        res.warnings.append("Cv 计算分母为0")
        res.flow_regime = "无效"
        return res
    cv_required = mass_flow / denom
    res.cv_required = cv_required

    # Flp 精炼迭代：缩径且用户未提供 Flp 时，用 cv_operating=cv_required 重算 Flp (IEC Eq.30)
    # 单次迭代，与 Excel 一致（不收敛到完全一致，避免隐式方程循环）
    if vc.reduced_port and vc.flp is None:
        fl_refined = fl_effective(vc, fp, cv_operating=cv_required)
        if abs(fl_refined - fl) > 0.001:
            fl = fl_refined
            res.fl_eff = fl
            dp_choked = (fl ** 2) * (p1 - ff * pv)
            dp_choked = max(dp_choked, 0.0)
            res.dp_choked = dp_choked
            choked = res.dp >= dp_choked
            res.choked = choked
            dp_eff = min(res.dp, dp_choked)
            denom = K_LIQ * fp * math.sqrt(dp_eff * density) if (dp_eff * density) > 0 else 0.0
            if denom > 0:
                cv_required = mass_flow / denom
                res.cv_required = cv_required

    # ---- 开度二次修正: 用 FL(φ) 曲线迭代修正 dp_choked/Cv ----
    rated = rated_cv_select or vc.rated_cv or cv_required
    fc = vc.factor_curves
    _corrected = None
    if fc and fc.fl and rated > 0:
        phi_new = None
        for _ in range(5):
            phi = max(min(cv_required / rated, 1.0), 0.0)
            fl_phi = fc.fl.eval(phi)
            dp_choked_phi = (fl_phi ** 2) * (p1 - ff * pv)
            dp_choked_phi = max(dp_choked_phi, 0.0)
            choked_phi = res.dp >= dp_choked_phi
            dp_eff_phi = min(res.dp, dp_choked_phi)
            denom_phi = K_LIQ * fp * math.sqrt(dp_eff_phi * density) if (dp_eff_phi * density) > 0 else 0.0
            if denom_phi <= 0:
                break
            cv_new = mass_flow / denom_phi
            phi_new = max(min(cv_new / rated, 1.0), 0.0)
            cv_required = cv_new
            if abs(phi_new - phi) < 0.001:
                break
        # 曲线无效（如 FL 恒为 0）时首轮即 break，phi_new 保持 None：不做修正
        if phi_new is not None:
            fl = fl_phi
            dp_choked = dp_choked_phi
            choked = choked_phi
            res.cv_required = cv_required
            res.fl_eff = fl
            res.dp_choked = dp_choked
            res.choked = choked
            _corrected = {
                "FL_phi": fl_phi, "phi_final": phi_new,
                "iterations": _ + 1,
            }

    # 雷诺数与粘度修正
    rev = reynolds_number(vc, density, viscosity_cp, mass_flow, cv_required)
    res.reynolds = rev
    # 相对容量 Cd = Cv/d²（IEC Fr 修正公式内部参数，Cv/d²，d 单位 mm）
    d_port = vc.port_diameter or 0.0
    cd_port = cv_required / (d_port * d_port) if (d_port > 0 and cv_required > 0) else 0.0
    if cd_port <= 0:
        # Cd 兜底近似（按常见 Cd=0.01~0.05 范围，Excel 用 ValveData Cd）
        cd_port = 0.016
    fr = reynolds_factor(rev, fl, cd_port)
    need_fr, fr_msg = check_reynolds_correction(rev)
    # Fr < 1 时，所需 Cv 除以 Fr（低雷诺数 Cv 增大）
    if fr < 0.9999:
        cv_required = cv_required / fr
        res.cv_required = cv_required
        if fr_msg:
            res.warnings.append(f"{fr_msg} (Fr={fr:.3f})")
    # detail 记录 Fr/Cd
    if "fr" not in res.detail:
        res.detail["Fr"] = fr
        res.detail["Cd"] = cd_port

    # 流态判定(闪蒸/空化)
    res.flow_regime = _liquid_regime(p1, p2, pv, dp_choked, res.dp, choked)

    # 开度（使用修正后的 cv_required 重新计算）
    res.cv_rated_selected = rated
    res.opening_pct = (cv_required / rated * 100.0) if rated > 0 else 0.0

    res.detail = {
        "FF": ff, "Pv_kPa": pv, "Pc_kPa": pc, "FL": fl, "Fp": fp, "Fr": fr, "Cd": cd_port,
        "ΔP_kPa": res.dp, "ΔPch_kPa": dp_choked,
        "cv_required": cv_required, "rated_cv": rated,
        "mass_flow_kgh": mass_flow, "vol_flow_m3h": res.vol_flow,
        "Rev": rev,
    }
    if _corrected:
        res.detail["opening_corrected"] = _corrected
    if res.opening_pct > 100:
        res.warnings.append(f"所需Cv({cv_required:.1f})>额定Cv({rated:.1f})，阀门偏小")
    return res


def _liquid_regime(p1, p2, pv, dp_choked, dp, choked) -> str:
    """判定液体流态描述。"""
    if choked:
        # 阻塞流: 比较 P2 与 Pv 判断闪蒸(阀后闪蒸) 或 空化(阀内阻塞后阀外P2>Pv)
        if p2 <= pv:
            return "阻塞流-闪蒸"
        else:
            return "阻塞流-空化"
    return "非阻塞(湍流)"
