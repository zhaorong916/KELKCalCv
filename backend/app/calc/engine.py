"""计算引擎编排器

输入: 一组工艺工况(ProcessCase 形态的字典) + 介质(Fluid) + 阀门系数(ValveCoeffs)
输出: 该工况的 Cv 计算结果 + 噪音预测结果(统一 CalcCaseResult)

自动判定:
  - 水介质: 由温度/压力经 IAPWS-IF97 自动判定液态/蒸汽，并取相应物性
  - 其它介质: 按介质默认相态 + 用户覆盖
  - 两相流: 当介质标记 twophase 或用户提供气液两相流量时启用两相 Cv
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional

from app.calc.cv_core import ValveCoeffs, CvResult
from app.calc.cv_liquid import calculate_cv_liquid
from app.calc.cv_gas import calculate_cv_gas
from app.calc.cv_twophase import calculate_cv_twophase
from app.calc.noise import predict_gas_noise, predict_liquid_noise, NoiseResult
from app.calc import properties as prop
from app.calc.properties import water_saturation_phase_densities


@dataclass
class CalcCaseResult:
    """单组工况完整计算结果"""
    case_no: int
    case_name: str = ""
    fluid_name: str = ""
    phase: str = ""                # 实际计算相态 liquid/gas/twophase
    cv: Optional[CvResult] = None
    noise: Optional[NoiseResult] = None
    resolved_properties: dict = field(default_factory=dict)
    status: str = "成功"
    message: str = ""

    def to_dict(self) -> dict:
        d = {
            "case_no": self.case_no,
            "case_name": self.case_name,
            "fluid_name": self.fluid_name,
            "phase": self.phase,
            "resolved_properties": self.resolved_properties,
            "status": self.status,
            "message": self.message,
        }
        # 拉平 cv 结果到顶层（与 CalcResultSave schema 对齐）
        if self.cv:
            cv_d = self.cv.to_dict()
            d["cv_required"] = cv_d.get("cv_required")
            d["cv_rated_selected"] = cv_d.get("cv_rated_selected")
            d["cv_opening"] = cv_d.get("opening_pct")
            d["flow_regime"] = cv_d.get("flow_regime")
            d["dp"] = cv_d.get("dp")
            d["dp_choked"] = cv_d.get("dp_choked")
            d["x"] = cv_d.get("x")
            d["y"] = cv_d.get("y")
            d["reynolds"] = cv_d.get("reynolds")
        # 拉平 noise 结果到顶层
        if self.noise:
            n_d = self.noise.to_dict()
            d["noise_dba"] = n_d.get("noise_dba")
            d["noise_freq_peak"] = n_d.get("noise_freq_peak")
        # detail: 合并 cv/noise 的中间过程 (含多级降噪压降分配)
        detail = {}
        if self.cv and self.cv.detail:
            detail["cv"] = self.cv.detail
        if self.noise and self.noise.detail:
            detail["noise"] = self.noise.detail
        if detail:
            d["detail"] = detail
        return d


def _resolve_fluid_properties(fluid: dict, t_c: float, p_kpa: float,
                              state_override: str = "",
                              density_override: Optional[float] = None,
                              viscosity_override: Optional[float] = None,
                              mw_override: Optional[float] = None,
                              gamma_override: Optional[float] = None) -> prop.FluidProperties:
    """解析介质工况物性。

    水介质(is_water): 用 IAPWS-IF97 精确计算并自动判定相态。
    其它介质: 用介质库默认值 + 理想气体密度计算。
    """
    is_water = fluid.get("is_water", False)
    name = fluid.get("fluid_name") or fluid.get("name", "")

    if is_water:
        fp = prop.water_properties(t_c, p_kpa)
        fp.name = name or fp.name
        if state_override in ("liquid", "gas"):
            fp.phase = "liquid" if state_override == "liquid" else "gas"
        if density_override and density_override > 0:
            fp.density = density_override
        if viscosity_override and viscosity_override > 0:
            fp.viscosity_cp = viscosity_override
        if gamma_override and gamma_override > 0:
            fp.gamma = gamma_override
        return fp

    # 非水介质
    default_state = fluid.get("default_state", "liquid")
    phase = state_override or default_state
    mw = mw_override or fluid.get("molecular_weight", 0.0) or 28.97
    gamma = gamma_override or fluid.get("cp_cv_ratio", 0.0) or 1.4
    pc = fluid.get("critical_pressure", 0.0)
    pv = fluid.get("vapor_pressure", 0.0)
    z_rk = 1.0
    pc_kpa = pc or 0.0

    # P3-2: Antoine 蒸汽压温度修正 — 有系数时用工况温度重算 Pv，否则用库静态值
    a_a = fluid.get("antoine_a")
    a_b = fluid.get("antoine_b")
    a_c = fluid.get("antoine_c")
    a_tmin = fluid.get("antoine_tmin_k")
    if a_a and a_b:
        pv_antoine = prop.antoine_vapor_pressure_kpa(t_c, a_a, a_b, a_c, a_tmin)
        if pv_antoine > 0:
            pv = pv_antoine

    if phase == "gas":
        # 压缩因子 Z（Redlich-Kwong，对标 Excel GasPTPcTcZ）
        tc_k = fluid.get("critical_temp", 0.0)
        # 优先用调用方显式传的 Pc(介质库 critical_pressure)；若缺省则兜底
        if pc_kpa <= 0:
            pc_kpa = fluid.get("critical_pressure", 0.0) or 0.0
        if not density_override or density_override <= 0:
            z_rk = prop.gas_compressibility_rk(p_kpa, t_c, pc_kpa, tc_k)
        if density_override and density_override > 0:
            rho = density_override
        else:
            rho = prop.gas_density(p_kpa, t_c, mw, z=z_rk)
        mu = viscosity_override or fluid.get("viscosity", 0.0) or 0.018
        # 声速用 Newton-Laplace (与 Excel c1 一致，吸收 Z 影响)
        w = prop.gas_speed_of_sound_nl(t_c, gamma, p_kpa, rho)
    else:  # liquid
        # P3-3: 液体密度温度修正 (Excel Gf 公式) — 无 override 时按工况温度修正
        rho_base = density_override or fluid.get("density_liquid", 0.0) or 1000.0
        if density_override and density_override > 0:
            rho = rho_base
        else:
            tc_k = fluid.get("critical_temp", 0.0)
            tb_k = fluid.get("boiling_point", 0.0)
            if tc_k > 0 and tb_k > 0:
                rho = prop.liquid_density_temperature_corrected(rho_base, t_c, tc_k, tb_k)
            else:
                rho = rho_base
        mu = viscosity_override or fluid.get("viscosity", 0.0) or 1.0
        w = 1400.0

    return prop.FluidProperties(
        name=name, phase=phase, density=rho, viscosity_cp=mu,
        vapor_pressure_kpa=pv, critical_pressure_kpa=pc_kpa if (pc_kpa and pc_kpa > 0) else pc,
        molecular_weight=mw, gamma=gamma, speed_of_sound=w,
        compressibility=(z_rk if phase == "gas" else 1.0),
        t_c=t_c, p_kpa=p_kpa,
    )


def calculate_case(
    *,
    case_no: int,
    case_name: str,
    fluid: dict,                       # Fluid 模型字典
    valve_coeffs: ValveCoeffs,
    # 工艺参数
    p1: float, p2: float, t1: float,
    mass_flow: float = 0.0,
    vol_flow: float = 0.0,
    flow_unit: str = "mass",           # mass / vol
    fluid_state_override: str = "",
    density_override: Optional[float] = None,
    viscosity_override: Optional[float] = None,
    mw_override: Optional[float] = None,
    gamma_override: Optional[float] = None,
    # 两相
    mass_flow_gas: float = 0.0,
    mass_flow_liquid: float = 0.0,
    twophase_method: str = "additive",
    density_gas: float = 0.0,
    density_liquid: float = 0.0,
    # 噪音/管道
    pipe_diameter: float = 0.0,
    pipe_wall: float = 0.0,
    distance: float = 1.0,
    rated_cv_select: float = 0.0,
    quality: float = 1.0,  # 湿蒸汽干度 0<Q<1, 默认1.0(纯汽)
) -> CalcCaseResult:
    """计算单组工况。"""
    res = CalcCaseResult(case_no=case_no, case_name=case_name, fluid_name=fluid.get("fluid_name", ""))

    # 物性解析
    fp = _resolve_fluid_properties(
        fluid, t1, p1, fluid_state_override,
        density_override, viscosity_override, mw_override, gamma_override,
    )
    res.resolved_properties = fp.to_dict()
    res.phase = fp.phase

    # 湿蒸汽检测: 水介质 + 饱和相态 + 0<Q<1
    is_wet_steam = (
        fluid.get("is_water", False)
        and fp.phase == "saturated"
        and 0.0 < quality < 1.0
    )
    is_twophase = (
        (mass_flow_gas > 0 and mass_flow_liquid > 0)
        or fluid.get("default_state") == "twophase"
        or is_wet_steam
    )

    warnings_all = []
    try:
        if is_twophase:
            if is_wet_steam:
                # 湿蒸汽: 用 quality 拆分质量流量 + IAPWS 饱和相密度
                rho_l_sat, rho_g_sat = water_saturation_phase_densities(t1, p1)
                m_total = mass_flow or (vol_flow * fp.density if flow_unit == "vol" else 0.0)
                cvr = calculate_cv_twophase(
                    p1=p1, p2=p2, density_gas=rho_g_sat, density_liquid=rho_l_sat,
                    viscosity_cp=fp.viscosity_cp, gamma=fp.gamma,
                    vapor_pressure_kpa=fp.vapor_pressure_kpa,
                    critical_pressure_kpa=fp.critical_pressure_kpa,
                    mass_flow_gas=m_total * quality,
                    mass_flow_liquid=m_total * (1.0 - quality),
                    vc=valve_coeffs, method="singleton", rated_cv_select=rated_cv_select,
                )
            else:
                rho_g = density_gas or fp.density
                rho_l = density_liquid or fp.density
                cvr = calculate_cv_twophase(
                    p1=p1, p2=p2, density_gas=rho_g, density_liquid=rho_l,
                    viscosity_cp=fp.viscosity_cp, gamma=fp.gamma,
                    vapor_pressure_kpa=fp.vapor_pressure_kpa,
                    critical_pressure_kpa=fp.critical_pressure_kpa,
                    mass_flow_gas=mass_flow_gas, mass_flow_liquid=mass_flow_liquid,
                    vc=valve_coeffs, method=twophase_method, rated_cv_select=rated_cv_select,
                )
            res.cv = cvr
        elif fp.phase in ("gas", "steam", "saturated"):
            # 饱和水蒸汽按气体处理
            cvr = calculate_cv_gas(
                p1=p1, p2=p2, density=fp.density, viscosity_cp=fp.viscosity_cp,
                gamma=fp.gamma, mass_flow=mass_flow,
                vol_flow_op=vol_flow if flow_unit == "vol" else 0.0,
                vc=valve_coeffs, rated_cv_select=rated_cv_select,
            )
            res.cv = cvr
        else:  # liquid
            cvr = calculate_cv_liquid(
                p1=p1, p2=p2, density=fp.density, viscosity_cp=fp.viscosity_cp,
                vapor_pressure=fp.vapor_pressure_kpa, critical_pressure=fp.critical_pressure_kpa,
                mass_flow=mass_flow, vol_flow=vol_flow if flow_unit == "vol" else 0.0,
                vc=valve_coeffs, rated_cv_select=rated_cv_select,
            )
            res.cv = cvr
        warnings_all.extend(res.cv.warnings)
    except Exception as e:
        res.status = "失败"
        res.message = f"Cv计算异常: {e}"
        return res

    # 噪音预测
    try:
        cv_op = res.cv.cv_required if res.cv and res.cv.cv_required > 0 else (rated_cv_select or valve_coeffs.rated_cv)
        # 开度修正后的 Fd(φ): 如有 Fd 曲线, 用收敛开度查值
        fd_eff = valve_coeffs.fd or 0.46
        fc = valve_coeffs.factor_curves
        if fc and fc.fd and res.cv and res.cv.cv_rated_selected and res.cv.cv_rated_selected > 0:
            phi = max(min(res.cv.cv_required / res.cv.cv_rated_selected, 1.0), 0.0)
            fd_eff = fc.fd.eval(phi)
        if fp.phase in ("gas", "steam", "saturated") and not is_twophase:
            fg = fp.gamma / 1.4
            # 5-Regime 增强参数: Flp/Fd/Aeta 可用时自动走 IEC 60534-8-3 五级模型
            flp_eff = (
                getattr(res.cv, "fl_eff", None)
                or getattr(res.cv, "flp", None)
                or valve_coeffs.flp
            )
            aeta_db = fluid.get("aeta_db")
            enhanced = (flp_eff is not None and aeta_db is not None and flp_eff > 0)
            nr = predict_gas_noise(
                cv_operating=cv_op, fl=valve_coeffs.fl, p1=p1, p2=p2, t1_c=t1,
                rho1=fp.density, molar_mass=fp.molecular_weight, gamma=fp.gamma,
                mass_flow=res.cv.mass_flow or mass_flow,
                pipe_diameter_mm=pipe_diameter, pipe_wall_mm=pipe_wall,
                distance_m=distance, xt=valve_coeffs.xt, fgamma=fg,
                # 5-Regime 参数
                flp=flp_eff, fd=fd_eff,
                aeta_db=aeta_db, enhanced=enhanced, octave=enhanced,
                # P3-1: 多级降噪阀
                stages=getattr(valve_coeffs, "stages", 1) or 1,
            )
        else:
            nr = predict_liquid_noise(
                cv_operating=cv_op, fl=valve_coeffs.fl, p1=p1, p2=p2, density=fp.density,
                vapor_pressure=fp.vapor_pressure_kpa, critical_pressure=fp.critical_pressure_kpa,
                mass_flow=res.cv.mass_flow or mass_flow,
                pipe_diameter_mm=pipe_diameter, pipe_wall_mm=pipe_wall, distance_m=distance,
            )
        res.noise = nr
        warnings_all.extend(nr.warnings)
    except Exception as e:
        res.noise = None
        warnings_all.append(f"噪音计算异常: {e}")

    res.message = "; ".join(warnings_all)
    if warnings_all and res.status == "成功":
        res.status = "警告"
    return res
