"""选型 API 多工况输入的介质覆盖回归测试

覆盖缺陷: 多工况选型中, 每个工况可各自选择介质; 但 _case_input 曾原样继承
主工况 special_req 中的 fluid_id, 使 _build_fluid 优先命中主工况介质,
非主工况的 fluid_name 被忽略, 该工况会按错误介质物性反算 Cv。

运行: cd backend && python -m unittest tests.test_selection_api
"""
import unittest
from types import SimpleNamespace

from app.api.selection import _case_input
from app.calc.selector import ValveSelector
from app.schemas import SelectionCaseIn, SelectionInput


def _payload(**kw):
    base = dict(
        project_id=1,
        valve_id=1,
        media="liquid",
        fluid_name="水",
        special_req={"fluid_id": 1, "nace": True},
    )
    base.update(kw)
    return SelectionInput(**base)


class _FluidQuery:
    def __init__(self, row):
        self._row = row

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._row


class _FluidDB:
    def __init__(self, by_id, by_name):
        self._by_id = by_id
        self._by_name = by_name

    def get(self, model, pk):
        return self._by_id.get(pk)

    def query(self, model):
        return _FluidQuery(self._by_name)


class TestCaseFluidOverride(unittest.TestCase):
    def test_case_with_different_fluid_drops_main_fluid_id(self):
        sub = _case_input(
            _payload(),
            SelectionCaseIn(case_no=2, media="gas", fluid_name="空气"),
        )
        self.assertEqual(sub.fluid_name, "空气")
        self.assertNotIn("fluid_id", sub.special_req or {})
        self.assertTrue((sub.special_req or {}).get("nace"))

    def test_case_with_same_fluid_keeps_main_fluid_id(self):
        sub = _case_input(
            _payload(),
            SelectionCaseIn(case_no=2, fluid_name="水"),
        )
        self.assertEqual((sub.special_req or {}).get("fluid_id"), 1)

    def test_build_fluid_uses_case_fluid_after_override(self):
        """清掉 fluid_id 后, _build_fluid 应按本工况 fluid_name 查库。"""
        water = SimpleNamespace(
            fluid_name="水", is_water=True, default_state="liquid",
            density_liquid=1000.0, density_gas=None, molecular_weight=None,
            cp_cv_ratio=None, critical_pressure=None, vapor_pressure=None,
            viscosity=1.0,
        )
        air = SimpleNamespace(
            fluid_name="空气", is_water=False, default_state="gas",
            density_liquid=None, density_gas=1.2, molecular_weight=29.0,
            cp_cv_ratio=1.4, critical_pressure=3.77, vapor_pressure=None,
            viscosity=0.018,
        )
        db = _FluidDB(by_id={1: water}, by_name=air)
        sub = _case_input(
            _payload(),
            SelectionCaseIn(case_no=2, media="gas", fluid_name="空气"),
        )
        fluid = ValveSelector(db)._build_fluid(sub, sub.special_req or {}, [])
        self.assertEqual(fluid["fluid_name"], "空气")
        self.assertEqual(fluid["default_state"], "gas")


if __name__ == "__main__":
    unittest.main()
