"""体积流量单位换算回归测试

覆盖 convert_process_case 对液体/气体体积流量的单位类别判定：
前端液体体积流量同样以 flow_unit="vol" 提交，不能据此判定为气体，
否则 GPM/L_min/m3_s 等液体单位会被当作内部单位 m³/h 原值使用。
"""
import math
import unittest

from app.calc.units import convert_process_case


class TestLiquidVolumetricFlow(unittest.TestCase):
    """液体体积流量：各种单位都应换算到 m³/h"""

    def _run(self, value, unit):
        raw = {
            "flow_vol": value,
            "flow_vol_unit": unit,
            "flow_unit": "vol",  # 与前端液体体积流量一致
            "p1": 500.0, "p1_unit": "kPaA",
            "t1": 20.0, "t1_unit": "C",
        }
        return convert_process_case(raw)

    def test_m3_h_unchanged(self):
        out = self._run(10.0, "m3_h")
        self.assertAlmostEqual(out["flow_vol"], 10.0)

    def test_gpm_to_m3_h(self):
        out = self._run(100.0, "GPM")
        self.assertAlmostEqual(out["flow_vol"], 100.0 * 0.22712470704)

    def test_l_min_to_m3_h(self):
        out = self._run(60.0, "L_min")
        self.assertAlmostEqual(out["flow_vol"], 3.6)

    def test_m3_s_to_m3_h(self):
        out = self._run(1.0, "m3_s")
        self.assertAlmostEqual(out["flow_vol"], 3600.0)

    def test_bpd_to_m3_h(self):
        out = self._run(1000.0, "BPD")
        self.assertAlmostEqual(out["flow_vol"], 1000.0 * 0.006624470622)

    def test_no_standard_gas_correction_for_liquid(self):
        """液体流量不做 P1/T1 标况修正"""
        out = self._run(100.0, "GPM")
        self.assertAlmostEqual(out["flow_vol"], 100.0 * 0.22712470704)


class TestGasVolumetricFlow(unittest.TestCase):
    """气体标准体积流量：换算后按 P1/T1 修正到工况 m³/h"""

    def _run(self, value, unit, p1=200.0, t1=20.0):
        raw = {
            "flow_vol": value,
            "flow_vol_unit": unit,
            "flow_unit": "vol",
            "p1": p1, "p1_unit": "kPaA",
            "t1": t1, "t1_unit": "C",
        }
        return convert_process_case(raw)

    def test_nm3_h_corrected_to_operating(self):
        out = self._run(100.0, "Nm3_h")
        expected = 100.0 * (101.325 / 200.0) * (293.15 / 273.15)
        self.assertTrue(math.isclose(out["flow_vol"], expected, rel_tol=1e-9))

    def test_actual_m3_h_not_corrected(self):
        """气体工况体积流量(m3_h)已是工况值，不做标况修正"""
        out = self._run(100.0, "m3_h")
        self.assertAlmostEqual(out["flow_vol"], 100.0)


class TestUnitFieldCleanup(unittest.TestCase):
    def test_unit_fields_removed_flow_unit_kept(self):
        raw = {
            "flow_vol": 50.0, "flow_vol_unit": "GPM", "flow_unit": "vol",
            "p1": 300.0, "p1_unit": "barG", "t1": 20.0, "t1_unit": "C",
        }
        out = convert_process_case(raw)
        self.assertNotIn("flow_vol_unit", out)
        self.assertNotIn("p1_unit", out)
        self.assertEqual(out["flow_unit"], "vol")
        # barG → kPa(abs)：300×100 + 101.325
        self.assertAlmostEqual(out["p1"], 300.0 * 100.0 + 101.325)


if __name__ == "__main__":
    unittest.main()
