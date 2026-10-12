"""计算引擎验证用例"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.calc.cv_core import ValveCoeffs
from app.calc.cv_liquid import calculate_cv_liquid
from app.calc.cv_gas import calculate_cv_gas
from app.calc.properties import water_saturation_pressure_kpa, gas_density, _HAS_IAPWS

print(f"iapws 可用: {_HAS_IAPWS}")
print()

# ---------- 1. 液体 Cv 验证 ----------
# 水 Q=120 m³/h, P1=680 kPa, P2=220 kPa, ρ=1000, Pv@室温≈3.17kPa, Pc=22064
# 期望 Cv ≈ 64.7
pv = water_saturation_pressure_kpa(25)
print(f"水 25℃ 饱和蒸汽压 Psat = {pv:.2f} kPa (期望≈3.17)")
vc = ValveCoeffs(rated_cv=80, fl=0.9, xt=0.72, fd=0.46, port_diameter=50)
r = calculate_cv_liquid(
    p1=680, p2=220, density=1000, viscosity_cp=0.89,
    vapor_pressure=pv, critical_pressure=22064,
    mass_flow=120000, vol_flow=0, vc=vc, rated_cv_select=80,
)
print(f"[液体] Cv={r.cv_required:.2f} (期望≈64.7)  流态={r.flow_regime}  阻塞={r.choked}")
print(f"       ΔP={r.dp:.0f} ΔPch={r.dp_choked:.0f} 开度={r.opening_pct:.1f}%  警告:{r.warnings}")
print()

# ---------- 2. 阻塞流算例(高压差水) ----------
r2 = calculate_cv_liquid(
    p1=1000, p2=50, density=1000, viscosity_cp=0.5,
    vapor_pressure=water_saturation_pressure_kpa(80), critical_pressure=22064,
    mass_flow=50000, vc=vc, rated_cv_select=80,
)
print(f"[液体-高压差] Cv={r2.cv_required:.2f}  流态={r2.flow_regime}  ΔPch={r2.dp_choked:.0f}")
print()

# ---------- 3. 气体 Cv 验证 ----------
# 空气, 质量流量由 Cv=100 反推: 之前算得 W≈8627 kg/h @ P1=600,P2=400,T=300K
# 给定 W=8627 反算应得 Cv≈100
rho1 = gas_density(600, 27, 28.965)
print(f"空气 600kPa 27℃ 密度 ρ1={rho1:.3f} kg/m³")
vcg = ValveCoeffs(rated_cv=120, fl=0.9, xt=0.72, fd=0.46, port_diameter=50)
rg = calculate_cv_gas(
    p1=600, p2=400, density=rho1, viscosity_cp=0.018, gamma=1.4,
    mass_flow=8627, vc=vcg, rated_cv_select=120,
)
print(f"[气体] Cv={rg.cv_required:.2f} (期望≈100)  流态={rg.flow_regime}  Y={rg.y:.3f}  x={rg.x:.4f}  Fγ·xT={rg.x_t_eff:.3f}")
print(f"       阻塞={rg.choked}  开度={rg.opening_pct:.1f}%")
print()

# ---------- 4. 气体临界(阻塞)流 ----------
rg2 = calculate_cv_gas(
    p1=600, p2=100, density=gas_density(600,27,28.965), viscosity_cp=0.018, gamma=1.4,
    mass_flow=5000, vc=vcg, rated_cv_select=120,
)
print(f"[气体-临界] Cv={rg2.cv_required:.2f}  流态={rg2.flow_regime}  Y={rg2.y:.3f}  阻塞={rg2.choked}")
print()
print("验证完成")
