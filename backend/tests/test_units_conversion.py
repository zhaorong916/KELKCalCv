"""单位换算回归测试: 标况/标准气体体积流量 → 工况 m³/h"""
import unittest

from app.calc.units import convert_process_case


class TestGasStandardFlowConversion(unittest.TestCase):
    """标况体积流量按 P1/T1 折算到工况体积流量时不应重复计入参考温度"""

    def test_nm3_h_20c_at_reference_is_unchanged(self):
        """101.325 kPaA / 20℃ 时, Nm³/h(20℃) 与工况 m³/h 数值相同"""
        out = convert_process_case({
            "flow_unit": "vol", "flow_vol": 1000.0, "flow_vol_unit": "Nm3_h_20",
            "p1": 101.325, "p1_unit": "kPaA", "t1": 20.0, "t1_unit": "C",
        })
        self.assertAlmostEqual(out["flow_vol"], 1000.0, delta=2.0)

    def test_nm3_h_0c_at_reference_is_unchanged(self):
        """101.325 kPaA / 0℃ 时, Nm³/h(0℃) 与工况 m³/h 数值相同"""
        out = convert_process_case({
            "flow_unit": "vol", "flow_vol": 1000.0, "flow_vol_unit": "Nm3_h",
            "p1": 101.325, "p1_unit": "kPaA", "t1": 0.0, "t1_unit": "C",
        })
        self.assertAlmostEqual(out["flow_vol"], 1000.0, delta=0.5)

    def test_scfm_at_reference_is_unchanged(self):
        """60℉/1atm 下 1 SCFM = 1.699 工况 m³/h"""
        out = convert_process_case({
            "flow_unit": "vol", "flow_vol": 1.0, "flow_vol_unit": "SCFM",
            "p1": 101.325, "p1_unit": "kPaA", "t1": 15.5556, "t1_unit": "C",
        })
        self.assertAlmostEqual(out["flow_vol"], 1.699, delta=0.02)


if __name__ == "__main__":
    unittest.main()
