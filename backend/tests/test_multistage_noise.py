"""多级降噪阀压降分配功能单元测试

测试范围:
  1. noise.py 简化路径: stages=1 时无多级字段; stages>1 时 x_stage/r_stage/stages_needed 正确
  2. noise.py 几何分布公式: r_stage=(p2/p1)^(1/N), x_stage=1-r_stage
  3. noise.py stages_needed 计算 (避免阻塞所需最少级数)
  4. engine.py CalcCaseResult.to_dict() 合并 cv/noise detail
  5. cv_core.py ValveCoeffs.stages 默认值与赋值
  6. calculations.py ValveCoeffs 从 cfg.stages 传入 (通过 ValveConfigSchema 校验)

运行方式:
  cd backend
  python -m unittest tests.test_multistage_noise -v
"""
import math
import unittest
import os
import sys

# 确保能导入 app 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestValveCoeffsStages(unittest.TestCase):
    """ValveCoeffs.stages 字段测试"""

    def test_default_stages_is_1(self):
        from app.calc.cv_core import ValveCoeffs
        vc = ValveCoeffs(rated_cv=80, fl=0.9, xt=0.72, fd=0.46)
        self.assertEqual(vc.stages, 1)

    def test_stages_can_be_set(self):
        from app.calc.cv_core import ValveCoeffs
        vc = ValveCoeffs(rated_cv=80, fl=0.9, xt=0.72, fd=0.46, stages=5)
        self.assertEqual(vc.stages, 5)


class TestNoiseSimplifiedSingleStage(unittest.TestCase):
    """简化路径 stages=1: 不应包含多级字段"""

    def _run(self, stages=1):
        from app.calc.noise import predict_gas_noise
        return predict_gas_noise(
            cv_operating=50, fl=0.9, p1=1000, p2=600, t1_c=50,
            rho1=10, molar_mass=28.97, gamma=1.4, mass_flow=500,
            pipe_diameter_mm=80, pipe_wall_mm=5, distance_m=1.0,
            xt=0.72, fgamma=1.0, stages=stages,
        )

    def test_single_stage_no_multistage_fields(self):
        """stages=1 时 detail 不含 x_stage/r_stage/stages_needed"""
        res = self._run(stages=1)
        self.assertIsNotNone(res.detail)
        self.assertNotIn("x_stage", res.detail)
        self.assertNotIn("r_stage", res.detail)
        self.assertNotIn("stages_needed", res.detail)

    def test_single_stage_has_stages_field(self):
        """stages=1 时 detail 仍包含 stages=1 和 x_total"""
        res = self._run(stages=1)
        self.assertEqual(res.detail.get("stages"), 1)
        self.assertIn("x_total", res.detail)

    def test_single_stage_regime_not_multistage(self):
        """stages=1 时 regime 不含 '级降噪'"""
        res = self._run(stages=1)
        self.assertNotIn("级降噪", res.regime)


class TestNoiseSimplifiedMultiStage(unittest.TestCase):
    """简化路径 stages>1: 多级压降分配字段正确"""

    def _run(self, p1=1000, p2=200, stages=3):
        from app.calc.noise import predict_gas_noise
        return predict_gas_noise(
            cv_operating=50, fl=0.9, p1=p1, p2=p2, t1_c=50,
            rho1=10, molar_mass=28.97, gamma=1.4, mass_flow=500,
            pipe_diameter_mm=80, pipe_wall_mm=5, distance_m=1.0,
            xt=0.72, fgamma=1.0, stages=stages,
        )

    def test_multistage_fields_present(self):
        """stages>1 时 detail 包含 x_stage/r_stage/stages_needed"""
        res = self._run(stages=3)
        self.assertIsNotNone(res.detail)
        for key in ("x_stage", "r_stage", "stages_needed", "stages", "x_total"):
            self.assertIn(key, res.detail, f"缺少字段: {key}")

    def test_stages_value_in_detail(self):
        """detail.stages 等于传入的级数"""
        res = self._run(stages=4)
        self.assertEqual(res.detail["stages"], 4)

    def test_x_total_equals_total_pressure_ratio(self):
        """x_total 等于总压差比 (p1-p2)/p1"""
        p1, p2 = 1000, 200
        res = self._run(p1=p1, p2=p2, stages=3)
        expected_x_total = (p1 - p2) / p1
        self.assertAlmostEqual(res.detail["x_total"], expected_x_total, places=6)

    def test_r_stage_geometric_distribution(self):
        """r_stage = (p2/p1)^(1/N) 几何分布"""
        p1, p2, N = 1000, 200, 3
        res = self._run(p1=p1, p2=p2, stages=N)
        expected_r = (p2 / p1) ** (1.0 / N)
        self.assertAlmostEqual(res.detail["r_stage"], expected_r, places=6)

    def test_x_stage_equals_1_minus_r_stage(self):
        """x_stage = 1 - r_stage"""
        res = self._run(p1=1000, p2=200, stages=3)
        expected_x = 1.0 - res.detail["r_stage"]
        self.assertAlmostEqual(res.detail["x_stage"], expected_x, places=6)

    def test_x_stage_smaller_than_x_total(self):
        """每级压差比应小于总压差比 (降噪原理)"""
        res = self._run(p1=1000, p2=200, stages=3)
        self.assertLess(res.detail["x_stage"], res.detail["x_total"])

    def test_stages_needed_positive(self):
        """stages_needed 至少为 1"""
        res = self._run(stages=3)
        self.assertGreaterEqual(res.detail["stages_needed"], 1)

    def test_stages_needed_decreases_with_more_stages(self):
        """级数越多，避免阻塞越容易 (但 stages_needed 是固定值，取决于压差)"""
        # stages_needed 是由总压差和 xT 决定的，与配置的 stages 无关
        res3 = self._run(stages=3)
        res5 = self._run(stages=5)
        self.assertEqual(res3.detail["stages_needed"], res5.detail["stages_needed"])

    def test_regime_label_has_multistage(self):
        """stages>1 时 regime 包含 '3级'"""
        res = self._run(stages=3)
        self.assertIn("3级", res.regime)
        self.assertIn("3级", res.detail.get("regime_label", ""))

    def test_two_stages(self):
        """stages=2 边界测试"""
        res = self._run(stages=2)
        self.assertEqual(res.detail["stages"], 2)
        self.assertIn("2级", res.regime)
        expected_r = (200 / 1000) ** 0.5
        self.assertAlmostEqual(res.detail["r_stage"], expected_r, places=6)


class TestStagesNeededCalculation(unittest.TestCase):
    """stages_needed (避免阻塞所需最少级数) 计算验证"""

    def _get_stages_needed(self, p1, p2, xt=0.72, fgamma=1.0):
        from app.calc.noise import predict_gas_noise
        res = predict_gas_noise(
            cv_operating=50, fl=0.9, p1=p1, p2=p2, t1_c=50,
            rho1=10, molar_mass=28.97, gamma=1.4, mass_flow=500,
            pipe_diameter_mm=80, pipe_wall_mm=5, distance_m=1.0,
            xt=xt, fgamma=fgamma, stages=2,
        )
        return res.detail.get("stages_needed")

    def test_low_pressure_drop_needs_1_stage(self):
        """低压差时 stages_needed=1"""
        # p1=600, p2=500, x=0.167, xT_eff=0.72
        n = self._get_stages_needed(600, 500)
        self.assertEqual(n, 1)

    def test_high_pressure_drop_needs_more_stages(self):
        """高压差时 stages_needed>1"""
        # p1=1000, p2=100, x=0.9, xT_eff=0.72
        n = self._get_stages_needed(1000, 100)
        self.assertGreater(n, 1)

    def test_stages_needed_matches_formula(self):
        """stages_needed = ceil(ln(p2/p1) / ln(1 - Fγ·xT))"""
        p1, p2, xt, fgamma = 1000, 200, 0.72, 1.0
        n = self._get_stages_needed(p1, p2, xt, fgamma)
        xT_eff = fgamma * xt
        expected = max(math.ceil(math.log(p2 / p1) / math.log(1.0 - xT_eff)), 1)
        self.assertEqual(n, expected)


class TestCalcCaseResultToDict(unittest.TestCase):
    """engine.py CalcCaseResult.to_dict() 包含 detail"""

    def test_to_dict_includes_detail_when_cv_noise_present(self):
        from app.calc.engine import CalcCaseResult
        from app.calc.cv_core import CvResult
        from app.calc.noise import NoiseResult
        cr = CalcCaseResult(case_no=1)
        cr.cv = CvResult(cv_required=10, detail={"x": 0.5})
        cr.noise = NoiseResult(noise_dba=80, detail={"stages": 3, "x_stage": 0.4})
        d = cr.to_dict()
        self.assertIn("detail", d)
        self.assertIn("cv", d["detail"])
        self.assertIn("noise", d["detail"])
        self.assertEqual(d["detail"]["noise"]["stages"], 3)

    def test_to_dict_no_detail_when_empty(self):
        from app.calc.engine import CalcCaseResult
        cr = CalcCaseResult(case_no=1)
        d = cr.to_dict()
        self.assertNotIn("detail", d)

    def test_to_dict_partial_detail(self):
        """只有 cv.detail 时, detail 只含 cv"""
        from app.calc.engine import CalcCaseResult
        from app.calc.cv_core import CvResult
        cr = CalcCaseResult(case_no=1)
        cr.cv = CvResult(cv_required=10, detail={"x": 0.5})
        cr.noise = None
        d = cr.to_dict()
        self.assertIn("detail", d)
        self.assertIn("cv", d["detail"])
        self.assertNotIn("noise", d["detail"])


class TestValveConfigSchemaStages(unittest.TestCase):
    """ValveConfigSchema 包含 stages 字段"""

    def test_schema_has_stages_field(self):
        from app.schemas import ValveConfigSchema
        schema = ValveConfigSchema(stages=3, valve_style="测试")
        self.assertEqual(schema.stages, 3)

    def test_schema_stages_defaults_none(self):
        from app.schemas import ValveConfigSchema
        schema = ValveConfigSchema(valve_style="测试")
        self.assertIsNone(schema.stages)

    def test_case_result_out_has_detail_field(self):
        from app.schemas import CaseResultOut
        self.assertTrue(hasattr(CaseResultOut.model_fields, "__contains__") or "detail" in CaseResultOut.model_fields)
        out = CaseResultOut(case_no=1, detail={"noise": {"stages": 2}})
        self.assertEqual(out.detail["noise"]["stages"], 2)


class TestPredictGasNoiseRouting(unittest.TestCase):
    """predict_gas_noise 正确路由 stages 到简化/增强路径"""

    def test_simplified_path_receives_stages(self):
        """未启用 enhanced 时, stages 传入简化路径"""
        from app.calc.noise import predict_gas_noise
        res = predict_gas_noise(
            cv_operating=50, fl=0.9, p1=1000, p2=200, t1_c=50,
            rho1=10, molar_mass=28.97, gamma=1.4, mass_flow=500,
            pipe_diameter_mm=80, pipe_wall_mm=5, distance_m=1.0,
            xt=0.72, fgamma=1.0, stages=3,
            # 不传 enhanced/flp/aeta_db → 走简化路径
        )
        self.assertIn("简化", res.method)
        self.assertEqual(res.detail.get("stages"), 3)

    def test_stages_does_not_crash_with_invalid_pressure(self):
        """无效压力时不崩溃"""
        from app.calc.noise import predict_gas_noise
        res = predict_gas_noise(
            cv_operating=50, fl=0.9, p1=0, p2=0, t1_c=50,
            rho1=10, molar_mass=28.97, gamma=1.4, mass_flow=500,
            pipe_diameter_mm=80, pipe_wall_mm=5, stages=3,
        )
        # 应返回带 warning 的空结果, 不抛异常
        self.assertTrue(len(res.warnings) > 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
