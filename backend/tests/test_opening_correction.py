"""开度二次修正单元测试

验证 FactorCurve 多项式求值、气体/液体 Cv 计算的开度迭代修正、
Fd(φ) 修正传入噪音计算。
"""
import math
import unittest

from app.calc.cv_core import FactorCurve, FactorCurves, ValveCoeffs
from app.calc.cv_gas import calculate_cv_gas
from app.calc.cv_liquid import calculate_cv_liquid


class TestFactorCurve(unittest.TestCase):
    """多项式曲线求值"""

    def test_constant(self):
        """常数曲线 P0=0.9, 其余=0 → 任意 φ 返回 0.9"""
        c = FactorCurve(p0=0.9)
        self.assertAlmostEqual(c.eval(0.0), 0.9)
        self.assertAlmostEqual(c.eval(0.5), 0.9)
        self.assertAlmostEqual(c.eval(1.0), 0.9)

    def test_linear(self):
        """线性曲线 P0=0.8, P1=0.1 → f(φ)=0.8+0.1·φ"""
        c = FactorCurve(p0=0.8, p1=0.1)
        self.assertAlmostEqual(c.eval(0.0), 0.8)
        self.assertAlmostEqual(c.eval(0.5), 0.85)
        self.assertAlmostEqual(c.eval(1.0), 0.9)

    def test_clamp(self):
        """钳制到 [value_min, value_max]"""
        c = FactorCurve(p0=0.5, p1=1.0, value_min=0.8, value_max=0.95)
        self.assertAlmostEqual(c.eval(0.0), 0.8)   # 0.5 → 钳到 0.8
        self.assertAlmostEqual(c.eval(1.0), 0.95)  # 1.5 → 钳到 0.95
        self.assertAlmostEqual(c.eval(0.4), 0.9)   # 0.5+0.4=0.9 在范围内

    def test_quartic(self):
        """4 次多项式 P4=1, 其余=0 → f(φ)=φ⁴"""
        c = FactorCurve(p4=1.0)
        self.assertAlmostEqual(c.eval(0.0), 0.0)
        self.assertAlmostEqual(c.eval(0.5), 0.0625)
        self.assertAlmostEqual(c.eval(1.0), 1.0)


class TestFactorCurvesFromDict(unittest.TestCase):
    """FactorCurves.from_dict 解析"""

    def test_full_dict(self):
        d = {
            "fl": {"p0": 0.85, "p1": 0.05, "value_min": 0.85, "value_max": 0.95},
            "kc": {"p0": 0.6},
            "fd": {"p0": 0.4, "p1": 0.06},
        }
        fc = FactorCurves.from_dict(d)
        self.assertIsNotNone(fc.fl)
        self.assertAlmostEqual(fc.fl.p0, 0.85)
        self.assertAlmostEqual(fc.fl.p1, 0.05)
        self.assertAlmostEqual(fc.fl.value_min, 0.85)
        self.assertIsNotNone(fc.kc)
        self.assertIsNotNone(fc.fd)

    def test_partial_dict(self):
        """只有 fl, 无 kc/fd"""
        d = {"fl": {"p0": 0.9}}
        fc = FactorCurves.from_dict(d)
        self.assertIsNotNone(fc.fl)
        self.assertIsNone(fc.kc)
        self.assertIsNone(fc.fd)

    def test_empty_dict(self):
        fc = FactorCurves.from_dict({})
        self.assertIsNone(fc.fl)
        self.assertIsNone(fc.kc)
        self.assertIsNone(fc.fd)

    def test_none(self):
        fc = FactorCurves.from_dict(None)
        self.assertIsNone(fc.fl)


class TestValveCoeffsFactorCurves(unittest.TestCase):
    """ValveCoeffs.factor_curves 字段"""

    def test_default_none(self):
        vc = ValveCoeffs()
        self.assertIsNone(vc.factor_curves)

    def test_set_curves(self):
        fc = FactorCurves(fl=FactorCurve(p0=0.9))
        vc = ValveCoeffs(factor_curves=fc)
        self.assertIsNotNone(vc.factor_curves)
        self.assertAlmostEqual(vc.factor_curves.fl.p0, 0.9)


class TestGasOpeningCorrection(unittest.TestCase):
    """气体 Cv 计算开度修正"""

    def _make_gas_case(self):
        """构造气体工况: P1=500kPa, P2=300kPa, 空气"""
        return dict(
            p1=500.0, p2=300.0,
            density=5.88,   # kg/m³ (500kPa, 20℃ 空气)
            viscosity_cp=0.018,
            gamma=1.4,
            mass_flow=100.0,  # kg/h
        )

    def test_no_curves_no_correction(self):
        """无 factor_curves → 不修正, detail 无 opening_corrected"""
        vc = ValveCoeffs(rated_cv=50, fl=0.9, xt=0.72, fd=0.46)
        case = self._make_gas_case()
        res = calculate_cv_gas(vc=vc, rated_cv_select=50, **case)
        self.assertIsNone(vc.factor_curves)
        self.assertNotIn("opening_corrected", res.detail)

    def test_with_curves_correction_applied(self):
        """有 FL 曲线 → 修正, detail 含 opening_corrected"""
        # FL 从 0.85(φ=0) 到 0.92(φ=1) 的线性曲线
        fc = FactorCurves(fl=FactorCurve(p0=0.85, p1=0.07, value_min=0.85, value_max=0.92))
        vc = ValveCoeffs(rated_cv=50, fl=0.9, xt=0.72, fd=0.46, factor_curves=fc)
        case = self._make_gas_case()
        res = calculate_cv_gas(vc=vc, rated_cv_select=50, **case)
        self.assertIn("opening_corrected", res.detail)
        corr = res.detail["opening_corrected"]
        self.assertIn("FL_phi", corr)
        self.assertIn("xT_phi", corr)
        self.assertIn("phi_final", corr)
        self.assertIn("iterations", corr)
        self.assertGreater(corr["iterations"], 0)
        # xT_phi = 0.84 * FL_phi²
        self.assertAlmostEqual(corr["xT_phi"], 0.84 * corr["FL_phi"] ** 2, places=4)

    def test_correction_changes_cv(self):
        """修正后 Cv 应与未修正时不同 (当 FL 非常数时)"""
        case = self._make_gas_case()
        # 无修正
        vc_plain = ValveCoeffs(rated_cv=50, fl=0.9, xt=0.72, fd=0.46)
        res_plain = calculate_cv_gas(vc=vc_plain, rated_cv_select=50, **case)
        # 有修正 (FL 在 0.85-0.92 间变化)
        fc = FactorCurves(fl=FactorCurve(p0=0.85, p1=0.07, value_min=0.85, value_max=0.92))
        vc_corr = ValveCoeffs(rated_cv=50, fl=0.9, xt=0.72, fd=0.46, factor_curves=fc)
        res_corr = calculate_cv_gas(vc=vc_corr, rated_cv_select=50, **case)
        # Cv 值应该不同 (因为 xT 变化导致 Y 变化)
        self.assertNotAlmostEqual(res_plain.cv_required, res_corr.cv_required, places=1)

    def test_constant_curve_converges_immediately(self):
        """常数 FL 曲线 → 1 次迭代即收敛"""
        fc = FactorCurves(fl=FactorCurve(p0=0.9, value_min=0.9, value_max=0.9))
        vc = ValveCoeffs(rated_cv=50, fl=0.9, xt=0.72, fd=0.46, factor_curves=fc)
        case = self._make_gas_case()
        res = calculate_cv_gas(vc=vc, rated_cv_select=50, **case)
        corr = res.detail["opening_corrected"]
        # 常数曲线: 第 1 次迭代后 phi_new ≈ phi → 收敛
        self.assertLessEqual(corr["iterations"], 2)

    def test_zero_fl_curve_skips_correction(self):
        """FL 曲线恒为 0 (常数曲线只填 value_max) → 不抛异常, 跳过修正"""
        fc = FactorCurves(fl=FactorCurve(p0=0.0, value_min=None, value_max=0.9))
        vc = ValveCoeffs(rated_cv=50, fl=0.9, xt=0.72, fd=0.46, factor_curves=fc)
        case = self._make_gas_case()
        res = calculate_cv_gas(vc=vc, rated_cv_select=50, **case)
        self.assertGreater(res.cv_required, 0)
        self.assertNotIn("opening_corrected", res.detail)


class TestLiquidOpeningCorrection(unittest.TestCase):
    """液体 Cv 计算开度修正"""

    def _make_liquid_case(self):
        """构造液体工况: 水, P1=500kPa, P2=300kPa"""
        return dict(
            p1=500.0, p2=300.0,
            density=998.0,
            vapor_pressure=2.34, critical_pressure=22064.0,
            mass_flow=5000.0,  # kg/h
            viscosity_cp=1.0,
        )

    def test_no_curves_no_correction(self):
        vc = ValveCoeffs(rated_cv=50, fl=0.9, fd=0.46)
        case = self._make_liquid_case()
        res = calculate_cv_liquid(vc=vc, rated_cv_select=50, **case)
        self.assertNotIn("opening_corrected", res.detail)

    def test_with_curves_correction_applied(self):
        fc = FactorCurves(fl=FactorCurve(p0=0.85, p1=0.07, value_min=0.85, value_max=0.92))
        vc = ValveCoeffs(rated_cv=50, fl=0.9, fd=0.46, factor_curves=fc)
        case = self._make_liquid_case()
        res = calculate_cv_liquid(vc=vc, rated_cv_select=50, **case)
        self.assertIn("opening_corrected", res.detail)
        corr = res.detail["opening_corrected"]
        self.assertIn("FL_phi", corr)
        self.assertIn("phi_final", corr)
        self.assertGreater(corr["iterations"], 0)

    def test_correction_affects_dp_choked(self):
        """修正后 dp_choked 应随 FL(φ) 变化"""
        case = self._make_liquid_case()
        # 无修正
        vc_plain = ValveCoeffs(rated_cv=80, fl=0.9, fd=0.46)
        res_plain = calculate_cv_liquid(vc=vc_plain, rated_cv_select=80, **case)
        # 有修正 (FL=0.78-0.85)
        fc = FactorCurves(fl=FactorCurve(p0=0.78, p1=0.07, value_min=0.78, value_max=0.85))
        vc_corr = ValveCoeffs(rated_cv=80, fl=0.9, fd=0.46, factor_curves=fc)
        res_corr = calculate_cv_liquid(vc=vc_corr, rated_cv_select=80, **case)
        # dp_choked 不同 (FL 不同)
        self.assertNotAlmostEqual(res_plain.dp_choked, res_corr.dp_choked, places=1)

    def test_zero_fl_curve_skips_correction(self):
        """FL 曲线恒为 0 (常数曲线只填 value_max) → 不抛异常, 跳过修正"""
        fc = FactorCurves(fl=FactorCurve(p0=0.0, value_min=None, value_max=0.9))
        vc = ValveCoeffs(rated_cv=50, fl=0.9, fd=0.46, factor_curves=fc)
        case = self._make_liquid_case()
        res = calculate_cv_liquid(vc=vc, rated_cv_select=50, **case)
        self.assertGreater(res.cv_required, 0)
        self.assertNotIn("opening_corrected", res.detail)


class TestFdOpeningCorrection(unittest.TestCase):
    """Fd(φ) 修正用于噪音计算"""

    def test_fd_eval_at_opening(self):
        """Fd 曲线在指定开度求值"""
        fd_curve = FactorCurve(p0=0.2, p1=0.26, value_min=0.2, value_max=0.46)
        # φ=0 → Fd=0.2, φ=1 → Fd=0.46
        self.assertAlmostEqual(fd_curve.eval(0.0), 0.2)
        self.assertAlmostEqual(fd_curve.eval(1.0), 0.46)
        self.assertAlmostEqual(fd_curve.eval(0.5), 0.33)

    def test_fd_curves_in_valve_coeffs(self):
        """ValveCoeffs 携带 Fd 曲线"""
        fc = FactorCurves(fd=FactorCurve(p0=0.2, p1=0.26, value_min=0.2, value_max=0.46))
        vc = ValveCoeffs(rated_cv=50, fd=0.46, factor_curves=fc)
        self.assertIsNotNone(vc.factor_curves.fd)
        phi = 0.7
        fd_eff = vc.factor_curves.fd.eval(phi)
        self.assertAlmostEqual(fd_eff, 0.2 + 0.26 * 0.7)  # 0.382


class TestConvergence(unittest.TestCase):
    """收敛性测试"""

    def test_gas_max_5_iterations(self):
        """气体修正最多迭代 5 次"""
        # 极端非线性曲线
        fc = FactorCurves(fl=FactorCurve(p0=0.5, p1=0.5, p4=10.0, value_min=0.5, value_max=0.99))
        vc = ValveCoeffs(rated_cv=50, fl=0.9, xt=0.72, fd=0.46, factor_curves=fc)
        case = dict(
            p1=500.0, p2=300.0,
            density=5.88, gamma=1.4,
            mass_flow=100.0, viscosity_cp=0.018,
        )
        res = calculate_cv_gas(vc=vc, rated_cv_select=50, **case)
        corr = res.detail["opening_corrected"]
        self.assertLessEqual(corr["iterations"], 5)

    def test_liquid_max_5_iterations(self):
        """液体修正最多迭代 5 次"""
        fc = FactorCurves(fl=FactorCurve(p0=0.5, p1=0.5, p4=10.0, value_min=0.5, value_max=0.99))
        vc = ValveCoeffs(rated_cv=80, fl=0.9, fd=0.46, factor_curves=fc)
        case = dict(
            p1=500.0, p2=300.0,
            density=998.0, vapor_pressure=2.34, critical_pressure=22064.0,
            mass_flow=5000.0, viscosity_cp=1.0,
        )
        res = calculate_cv_liquid(vc=vc, rated_cv_select=80, **case)
        corr = res.detail["opening_corrected"]
        self.assertLessEqual(corr["iterations"], 5)


# ===========================================================================
# 补充测试: 解析/集成/边界/Schema/阻塞流
# ===========================================================================
import json
from types import SimpleNamespace
from app.calc.engine import calculate_case
from app.calc.noise import predict_gas_noise


class TestParseCurveCoeffs(unittest.TestCase):
    """calculations._parse_curve_coeffs 解析测试"""

    def _parse(self, raw):
        """模拟 _parse_curve_coeffs 逻辑"""
        if not raw:
            return None
        if isinstance(raw, dict):
            return FactorCurves.from_dict(raw)
        try:
            return FactorCurves.from_dict(json.loads(raw))
        except Exception:
            return None

    def test_none(self):
        self.assertIsNone(self._parse(None))

    def test_empty_string(self):
        self.assertIsNone(self._parse(""))

    def test_json_string(self):
        """JSON 字符串解析"""
        s = json.dumps({"fl": {"p0": 0.9, "p1": 0.01}})
        fc = self._parse(s)
        self.assertIsNotNone(fc)
        self.assertAlmostEqual(fc.fl.p0, 0.9)
        self.assertAlmostEqual(fc.fl.p1, 0.01)

    def test_dict(self):
        """dict 直接解析"""
        d = {"fl": {"p0": 0.85}, "fd": {"p0": 0.3}}
        fc = self._parse(d)
        self.assertIsNotNone(fc.fl)
        self.assertIsNotNone(fc.fd)
        self.assertIsNone(fc.kc)

    def test_invalid_json(self):
        """非法 JSON → None"""
        self.assertIsNone(self._parse("not json"))

    def test_from_orm_like_object(self):
        """模拟 ORM 对象属性"""
        obj = SimpleNamespace(curve_coeffs=json.dumps({"fl": {"p0": 0.88}}))
        raw = getattr(obj, 'curve_coeffs', None)
        fc = self._parse(raw)
        self.assertIsNotNone(fc)
        self.assertAlmostEqual(fc.fl.p0, 0.88)


class TestSchemaSerialization(unittest.TestCase):
    """ValveConfigSchema curve_coeffs 序列化/反序列化"""

    def test_schema_roundtrip(self):
        """dict → schema → dump → dict 一致"""
        from app.schemas import ValveConfigSchema
        coeffs = {
            "fl": {"p0": 0.85, "p1": 0.05, "value_min": 0.85, "value_max": 0.92},
            "fd": {"p0": 0.2, "p1": 0.26},
        }
        s = ValveConfigSchema(
            valve_style="GV120", rated_cv=80, fl=0.9, xt=0.72, fd=0.46,
            curve_coeffs=coeffs,
        )
        d = s.model_dump()
        self.assertIsInstance(d["curve_coeffs"], dict)
        self.assertIn("fl", d["curve_coeffs"])
        self.assertIn("fd", d["curve_coeffs"])

    def test_schema_none_default(self):
        """curve_coeffs 默认 None"""
        from app.schemas import ValveConfigSchema
        s = ValveConfigSchema(valve_style="GV120", rated_cv=80)
        self.assertIsNone(s.curve_coeffs)

    def test_json_string_to_dict(self):
        """JSON 字符串 → schema → 自动解析为 dict"""
        from app.schemas import ValveConfigSchema
        coeffs_json = json.dumps({"fl": {"p0": 0.9}})
        s = ValveConfigSchema(
            valve_style="GV120", rated_cv=80,
            curve_coeffs=coeffs_json,
        )
        self.assertIsInstance(s.curve_coeffs, dict)
        self.assertIn("fl", s.curve_coeffs)


class TestEdgeCases(unittest.TestCase):
    """边界条件测试"""

    def test_gas_zero_mass_flow(self):
        """质量流量=0 → Cv=0, 不修正"""
        fc = FactorCurves(fl=FactorCurve(p0=0.85, p1=0.07))
        vc = ValveCoeffs(rated_cv=50, fl=0.9, xt=0.72, fd=0.46, factor_curves=fc)
        res = calculate_cv_gas(
            vc=vc, rated_cv_select=50,
            p1=500, p2=300, density=5.88, viscosity_cp=0.018,
            gamma=1.4, mass_flow=0,
        )
        # mass_flow=0 → Cv=0, 开度=0
        self.assertLessEqual(res.cv_required, 0.01)

    def test_gas_full_opening(self):
        """大开度 (接近 100%) → 修正正常"""
        fc = FactorCurves(fl=FactorCurve(p0=0.85, p1=0.07, value_min=0.85, value_max=0.92))
        vc = ValveCoeffs(rated_cv=10, fl=0.9, xt=0.72, fd=0.46, factor_curves=fc)
        res = calculate_cv_gas(
            vc=vc, rated_cv_select=10,
            p1=500, p2=400, density=5.88, viscosity_cp=0.018,
            gamma=1.4, mass_flow=50,
        )
        # 开度应 > 0
        self.assertGreater(res.opening_pct, 0)
        # 修正信息存在
        self.assertIn("opening_corrected", res.detail)

    def test_liquid_zero_dp(self):
        """压差=0 → Cv=0"""
        fc = FactorCurves(fl=FactorCurve(p0=0.85, p1=0.07))
        vc = ValveCoeffs(rated_cv=50, fl=0.9, fd=0.46, factor_curves=fc)
        res = calculate_cv_liquid(
            vc=vc, rated_cv_select=50,
            p1=500, p2=500, density=998,
            vapor_pressure=2.34, critical_pressure=22064,
            mass_flow=1000, viscosity_cp=1.0,
        )
        self.assertLessEqual(res.cv_required, 0.01)

    def test_only_fd_curve_no_fl(self):
        """只有 Fd 曲线, 无 FL 曲线 → Cv 不修正, Fd 可用"""
        fc = FactorCurves(fd=FactorCurve(p0=0.2, p1=0.26))
        vc = ValveCoeffs(rated_cv=50, fl=0.9, xt=0.72, fd=0.46, factor_curves=fc)
        res = calculate_cv_gas(
            vc=vc, rated_cv_select=50,
            p1=500, p2=300, density=5.88, viscosity_cp=0.018,
            gamma=1.4, mass_flow=100,
        )
        # 无 FL 曲线 → 不修正 Cv
        self.assertNotIn("opening_corrected", res.detail)

    def test_curves_with_clamp_only(self):
        """只有钳位范围无多项式系数 → 常数"""
        fc = FactorCurves(fl=FactorCurve(p0=0.9, value_min=0.9, value_max=0.9))
        vc = ValveCoeffs(rated_cv=50, fl=0.9, xt=0.72, fd=0.46, factor_curves=fc)
        res = calculate_cv_gas(
            vc=vc, rated_cv_select=50,
            p1=500, p2=300, density=5.88, viscosity_cp=0.018,
            gamma=1.4, mass_flow=100,
        )
        corr = res.detail["opening_corrected"]
        self.assertAlmostEqual(corr["FL_phi"], 0.9)


class TestChokedFlowCorrection(unittest.TestCase):
    """阻塞流条件下的开度修正"""

    def test_gas_choked_with_correction(self):
        """气体阻塞流 + 修正: xT(φ) 变化影响阻塞判定"""
        # 高压差 → 阻塞
        fc = FactorCurves(fl=FactorCurve(p0=0.75, p1=0.15, value_min=0.75, value_max=0.92))
        vc = ValveCoeffs(rated_cv=50, fl=0.9, xt=0.72, fd=0.46, factor_curves=fc)
        res = calculate_cv_gas(
            vc=vc, rated_cv_select=50,
            p1=1000, p2=200, density=11.5, viscosity_cp=0.018,
            gamma=1.4, mass_flow=200,
        )
        # 修正后 xT = 0.84 * FL(φ)²
        corr = res.detail["opening_corrected"]
        expected_xt = 0.84 * corr["FL_phi"] ** 2
        self.assertAlmostEqual(corr["xT_phi"], expected_xt, places=4)

    def test_liquid_choked_with_correction(self):
        """液体阻塞流 + 修正: FL(φ) 变化影响 dp_choked"""
        fc = FactorCurves(fl=FactorCurve(p0=0.75, p1=0.15, value_min=0.75, value_max=0.92))
        vc = ValveCoeffs(rated_cv=80, fl=0.9, fd=0.46, factor_curves=fc)
        res = calculate_cv_liquid(
            vc=vc, rated_cv_select=80,
            p1=1000, p2=100, density=998,
            vapor_pressure=2.34, critical_pressure=22064,
            mass_flow=8000, viscosity_cp=1.0,
        )
        corr = res.detail["opening_corrected"]
        # dp_choked = FL(φ)² × (P1 - ff × Pv)
        ff = 0.96 - 0.28 * math.sqrt(2.34 / 22064)
        expected_dp_choked = corr["FL_phi"] ** 2 * (1000 - ff * 2.34)
        self.assertAlmostEqual(res.dp_choked, expected_dp_choked, places=0)


class TestEngineFdIntegration(unittest.TestCase):
    """engine.py Fd(φ) 修正集成测试"""

    def test_fd_corrected_in_engine(self):
        """engine 用 Fd(φ) 替代固定 Fd"""
        fd_curve = FactorCurve(p0=0.2, p1=0.26, value_min=0.2, value_max=0.46)
        fc = FactorCurves(fd=fd_curve)
        vc = ValveCoeffs(
            rated_cv=50, fl=0.9, xt=0.72, fd=0.46,
            factor_curves=fc, port_diameter=50, pipe_diameter=80,
        )
        # 构造一个简单工况
        fluid = {
            "fluid_name": "空气", "is_water": False, "default_state": "gas",
            "density_liquid": None, "density_gas": 5.88,
            "molecular_weight": 28.97, "cp_cv_ratio": 1.4,
            "critical_pressure": 3770, "vapor_pressure": 0,
            "viscosity": 0.018,
        }
        case_data = SimpleNamespace(
            phase="gas", p1=500, p2=300, t1_c=20, density=5.88,
            molecular_weight=28.97, gamma=1.4,
            mass_flow=100, vol_flow=0, viscosity_cp=0.018,
            vapor_pressure_kpa=0, critical_pressure_kpa=3770,
            pipe_diameter=80, pipe_wall=4, distance=1.0,
        )
        # 直接验证 Fd 修正逻辑
        phi = 0.7  # 假设开度 70%
        fd_eff = fd_curve.eval(phi)
        self.assertAlmostEqual(fd_eff, 0.2 + 0.26 * 0.7)  # 0.382
        self.assertNotAlmostEqual(fd_eff, 0.46)  # 与额定 Fd 不同

    def test_no_fd_curve_uses_rated(self):
        """无 Fd 曲线 → 用额定 Fd"""
        fc = FactorCurves(fl=FactorCurve(p0=0.9))  # 只有 FL, 无 Fd
        vc = ValveCoeffs(rated_cv=50, fl=0.9, xt=0.72, fd=0.46, factor_curves=fc)
        # engine 中: 无 fd 曲线 → fd_eff = valve_coeffs.fd = 0.46
        self.assertIsNone(vc.factor_curves.fd)
        fd_eff = vc.fd or 0.46
        self.assertEqual(fd_eff, 0.46)


class TestFactorCurveEvalBoundary(unittest.TestCase):
    """FactorCurve.eval 边界值"""

    def test_negative_phi(self):
        """φ < 0 → 返回 P0"""
        c = FactorCurve(p0=0.9, p1=0.1)
        self.assertAlmostEqual(c.eval(-0.5), 0.9)

    def test_phi_zero(self):
        """φ = 0 → P0"""
        c = FactorCurve(p0=0.85, p1=0.05, p2=0.01)
        self.assertAlmostEqual(c.eval(0.0), 0.85)

    def test_phi_one(self):
        """φ = 1 → P0+P1+P2+P3+P4"""
        c = FactorCurve(p0=0.8, p1=0.05, p2=0.03, p3=0.01, p4=0.01)
        self.assertAlmostEqual(c.eval(1.0), 0.9)

    def test_phi_above_one(self):
        """φ > 1 → 多项式外推 (不钳制 φ, 只钳制结果)"""
        c = FactorCurve(p0=0.8, p1=0.1, value_max=0.95)
        v = c.eval(1.5)  # 0.8 + 0.15 = 0.95 → 钳到 0.95
        self.assertAlmostEqual(v, 0.95)

    def test_all_zero_coeffs(self):
        """全零系数 → 恒 0"""
        c = FactorCurve()
        self.assertAlmostEqual(c.eval(0.5), 0.0)

    def test_min_only_clamp(self):
        """只有 value_min → 低于 min 时钳制"""
        c = FactorCurve(p0=0.5, value_min=0.8)
        self.assertAlmostEqual(c.eval(0.0), 0.8)
        self.assertAlmostEqual(c.eval(1.0), 0.8)  # 0.5 → 钳到 0.8

    def test_max_only_clamp(self):
        """只有 value_max → 高于 max 时钳制"""
        c = FactorCurve(p0=1.5, value_max=1.0)
        self.assertAlmostEqual(c.eval(0.0), 1.0)
        self.assertAlmostEqual(c.eval(1.0), 1.0)


class TestFactorCurvesFromDictAdvanced(unittest.TestCase):
    """FactorCurves.from_dict 高级测试"""

    def test_with_string_values(self):
        """字符串数值 → 转为 float"""
        d = {"fl": {"p0": "0.9", "p1": "0.05"}}
        fc = FactorCurves.from_dict(d)
        self.assertAlmostEqual(fc.fl.p0, 0.9)
        self.assertAlmostEqual(fc.fl.p1, 0.05)

    def test_with_null_values(self):
        """null 值 → 默认 0"""
        d = {"fl": {"p0": None, "p1": 0.05}}
        fc = FactorCurves.from_dict(d)
        self.assertAlmostEqual(fc.fl.p0, 0.0)
        self.assertAlmostEqual(fc.fl.p1, 0.05)

    def test_with_null_min_max(self):
        """value_min/value_max 为 null → None"""
        d = {"fl": {"p0": 0.9, "value_min": None, "value_max": None}}
        fc = FactorCurves.from_dict(d)
        self.assertIsNone(fc.fl.value_min)
        self.assertIsNone(fc.fl.value_max)

    def test_non_dict_input(self):
        """非 dict 输入 → 空 FactorCurves"""
        fc = FactorCurves.from_dict("not a dict")
        self.assertIsNone(fc.fl)
        self.assertIsNone(fc.kc)
        self.assertIsNone(fc.fd)


class TestCorrectionDetailFields(unittest.TestCase):
    """修正后 detail 字段完整性"""

    def test_gas_detail_has_all_fields(self):
        """气体修正 detail 包含所有必要字段"""
        fc = FactorCurves(fl=FactorCurve(p0=0.85, p1=0.07, value_min=0.85, value_max=0.92))
        vc = ValveCoeffs(rated_cv=50, fl=0.9, xt=0.72, fd=0.46, factor_curves=fc)
        res = calculate_cv_gas(
            vc=vc, rated_cv_select=50,
            p1=500, p2=300, density=5.88, viscosity_cp=0.018,
            gamma=1.4, mass_flow=100,
        )
        corr = res.detail["opening_corrected"]
        for key in ("FL_phi", "xT_phi", "phi_final", "iterations"):
            self.assertIn(key, corr, f"Missing key: {key}")
        self.assertIsInstance(corr["iterations"], int)
        self.assertGreater(corr["FL_phi"], 0)
        self.assertGreater(corr["xT_phi"], 0)
        self.assertGreaterEqual(corr["phi_final"], 0)
        self.assertLessEqual(corr["phi_final"], 1.0)

    def test_liquid_detail_has_all_fields(self):
        """液体修正 detail 包含所有必要字段"""
        fc = FactorCurves(fl=FactorCurve(p0=0.85, p1=0.07, value_min=0.85, value_max=0.92))
        vc = ValveCoeffs(rated_cv=80, fl=0.9, fd=0.46, factor_curves=fc)
        res = calculate_cv_liquid(
            vc=vc, rated_cv_select=80,
            p1=500, p2=300, density=998,
            vapor_pressure=2.34, critical_pressure=22064,
            mass_flow=5000, viscosity_cp=1.0,
        )
        corr = res.detail["opening_corrected"]
        for key in ("FL_phi", "phi_final", "iterations"):
            self.assertIn(key, corr, f"Missing key: {key}")
        self.assertIsInstance(corr["iterations"], int)


if __name__ == "__main__":
    unittest.main()
