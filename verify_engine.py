"""引擎端到端验证: calculate_case (含水自动相态判定)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.calc.engine import calculate_case
from app.calc.cv_core import ValveCoeffs

vc = ValveCoeffs(rated_cv=80, fl=0.9, xt=0.72, fd=0.46, port_diameter=50)

# 1. 水(液态自动判定): 25℃, 680→220 kPa, 120 m³/h
water_fluid = {"fluid_name":"水","is_water":True,"default_state":"liquid"}
r1 = calculate_case(
    case_no=1, case_name="水-正常", fluid=water_fluid, valve_coeffs=vc,
    p1=680, p2=220, t1=25, mass_flow=120000, flow_unit="mass",
    pipe_diameter=80, pipe_wall=4, distance=1.0, rated_cv_select=80,
)
print(f"[水-液态] 相态={r1.phase}  Cv={r1.cv.cv_required:.2f}  流态={r1.cv.flow_regime}  噪音={r1.noise.noise_dba:.1f}dB(A)  状态={r1.status}")

# 2. 水蒸汽(自动判定为蒸汽): 200℃, 1500→800 kPa
r2 = calculate_case(
    case_no=2, case_name="过热蒸汽", fluid=water_fluid, valve_coeffs=vc,
    p1=1500, p2=800, t1=200, mass_flow=5000, flow_unit="mass",
    pipe_diameter=100, pipe_wall=5, distance=1.0, rated_cv_select=80,
)
print(f"[水-蒸汽] 相态={r2.phase}  Cv={r2.cv.cv_required:.2f}  流态={r2.cv.flow_regime}  Y={r2.cv.y:.3f}  噪音={r2.noise.noise_dba:.1f}dB(A)")

# 3. 空气(气态)
air_fluid = {"fluid_name":"空气","is_water":False,"default_state":"gas","molecular_weight":28.965,"cp_cv_ratio":1.4,"critical_pressure":3785,"vapor_pressure":0,"viscosity":0.018}
r3 = calculate_case(
    case_no=3, case_name="空气", fluid=air_fluid, valve_coeffs=vc,
    p1=600, p2=400, t1=27, mass_flow=8627, flow_unit="mass",
    pipe_diameter=80, pipe_wall=4, distance=1.0, rated_cv_select=120,
)
print(f"[空气] 相态={r3.phase}  Cv={r3.cv.cv_required:.2f}  流态={r3.cv.flow_regime}  噪音={r3.noise.noise_dba:.1f}dB(A)  马赫={r3.noise.mach_outlet:.3f}")

# 4. 两相流(水+空气)
r4 = calculate_case(
    case_no=4, case_name="气液两相", fluid=air_fluid, valve_coeffs=vc,
    p1=600, p2=400, t1=27, mass_flow_gas=5000, mass_flow_liquid=2000,
    density_gas=6.96, density_liquid=1000, twophase_method="additive",
    pipe_diameter=80, pipe_wall=4, distance=1.0, rated_cv_select=120,
)
print(f"[两相] 相态={r4.phase}  Cv={r4.cv.cv_required:.2f}  流态={r4.cv.flow_regime}  方法={r4.cv.detail.get('method')}")

print("\n引擎端到端验证完成")
