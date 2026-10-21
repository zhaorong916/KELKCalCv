"""选型匹配引擎单元测试（P2 任务 2.5）

覆盖：
  - match_condition 六类分支（数值/枚举/布尔/_or/_required/and-or）+ 未知键 + 非字典
  - _cv_ratio_to_stk 按 stroke_mode 各分支（linear/ln_eqn/exp_formula/
    poly_cv_div100/poly_phi100_div100/poly_div60/eq_index）
  - 四阶段：scope 排除 / constraint 排除 / preference 空化 boost /
    post_filter 开度窗口 penalty / 规则软删(is_active=False 不生效) /
    角行程(BT)按 flow_char 生成多候选

运行: cd backend && python -m unittest tests.test_selector
"""
import json
import math
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.calc.selector import (
    ValveSelector, match_condition, _cv_ratio_to_stk, _ParsedRule,
)
from app.models import (
    ValveType, ValveCvStk, SelectionRule,
    AllowablePressureDrop, BodyPtRating,
)
from app.schemas import SelectionInput


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeQuery:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def all(self):
        return list(self._rows)


class FakeDB:
    """按 model 返回内存行的最小 DB 替身。"""

    def __init__(self, series=(), rules=(), cv_rows=(), allow=(), body_pt=(), fluids=None):
        self._map = {
            ValveType: series,
            SelectionRule: rules,
            ValveCvStk: cv_rows,
            AllowablePressureDrop: allow,
            BodyPtRating: body_pt,
        }
        self.fluids = fluids or {}

    def query(self, model):
        return _FakeQuery(self._map.get(model, []))

    def get(self, model, pk):
        return self.fluids.get(pk)


_CAT_PRIO = {"scope": 10, "constraint": 20, "preference": 30, "post_filter": 40}


def rule_row(code, category, target="*", expr=None, op="and",
             action="exclude", payload=None, active=True):
    return SimpleNamespace(
        rule_code=code,
        category=category,
        target_series=target,
        condition_expr=json.dumps(expr) if expr is not None else None,
        condition_op=op,
        action=action,
        action_payload=json.dumps(payload) if payload is not None else None,
        priority=_CAT_PRIO[category],
        is_active=active,
    )


def series(code, category="globe", product_line="GC系列套筒调节阀",
           name=None, active=True):
    return SimpleNamespace(
        series_code=code, series_name=name or code,
        valve_category=category, product_line=product_line, is_active=active,
    )


def cv_row(series_code, dn_label="40A", trim_label="40", flow_char="EQ%",
           trim_type="Standard", seat_type="Metal", pressure_rating=None,
           rated_cv=100.0, cv_min=10.0, stroke_value=40.0):
    return SimpleNamespace(
        series_code=series_code, dn_label=dn_label, trim_label=trim_label,
        flow_char=flow_char, trim_type=trim_type, seat_type=seat_type,
        pressure_rating=pressure_rating, rated_cv=rated_cv, cv_min=cv_min,
        stroke_value=stroke_value,
    )


def _fake_curves_linear(db, series_code, pressure_rating, dn_label, trim_label,
                        trim_type, flow_char, seat_type):
    return {
        "stroke_mode": "linear",
        "stroke_info": {"fstk": 50, "divisor": 60, "opening_angle": None},
        "eqcv": {"a0": 0, "divisor": 60},
        "fd_mode": None,
    }


class _TestSelector(ValveSelector):
    """固定 cv_required / flow_regime，避免依赖介质物性与整套引擎。"""

    def __init__(self, db, cv_required=None, flow_regime=""):
        super().__init__(db)
        self._cv_required = cv_required
        self._flow_regime = flow_regime

    def _calc_cv_required(self, inp, special, warnings):
        return self._cv_required


def _input(**kw):
    base = dict(project_id=1, valve_id=1, media="liquid")
    base.update(kw)
    return SelectionInput(**base)


# ---------------------------------------------------------------------------
# match_condition
# ---------------------------------------------------------------------------
class TestMatchCondition(unittest.TestCase):
    def test_none_and_empty(self):
        self.assertTrue(match_condition(None, {}))
        self.assertTrue(match_condition({}, {}))

    def test_numeric_range(self):
        expr = {"rated_cv": {"_min": 10, "_max": 100}}
        self.assertTrue(match_condition(expr, {"rated_cv": 50}))
        self.assertFalse(match_condition(expr, {"rated_cv": 5}))
        self.assertFalse(match_condition(expr, {"rated_cv": 500}))

    def test_strict_gt_lt(self):
        self.assertTrue(match_condition({"temp_max": {"_gt": 230}}, {"temp_max": 250}))
        self.assertFalse(match_condition({"temp_max": {"_gt": 230}}, {"temp_max": 230}))
        self.assertTrue(match_condition({"temp": {"_lt": -45}}, {"temp": -60}))

    def test_required(self):
        self.assertTrue(match_condition({"cv_required": {"_required": False}}, {"cv_required": None}))
        self.assertFalse(match_condition({"cv_required": {"_required": False}}, {"cv_required": 5}))
        self.assertTrue(match_condition({"cv_min": {"_required": True}}, {"cv_min": 1.0}))

    def test_enum_eq_and_shorthand(self):
        self.assertTrue(match_condition({"series_category": {"_eq": "globe"}}, {"series_category": "globe"}))
        self.assertTrue(match_condition({"media": "liquid"}, {"media": "liquid"}))
        self.assertFalse(match_condition({"media": "liquid"}, {"media": "gas"}))

    def test_ne(self):
        expr = {"series_product_line": {"_ne": "GC系列套筒调节阀"}}
        self.assertTrue(match_condition(expr, {"series_product_line": "BT系列蝶阀"}))
        self.assertFalse(match_condition(expr, {"series_product_line": "GC系列套筒调节阀"}))

    def test_bool(self):
        self.assertTrue(match_condition({"nace": {"_eq": True}}, {"nace": True}))
        self.assertFalse(match_condition({"nace": {"_eq": True}}, {"nace": False}))

    def test_or_candidates(self):
        expr = {"flow_regime": {"_or": ["空化", "闪蒸"]}}
        self.assertTrue(match_condition(expr, {"flow_regime": "空化"}))
        self.assertFalse(match_condition(expr, {"flow_regime": "层流"}))
        self.assertFalse(match_condition(expr, {"flow_regime": None}))

    def test_multi_key_and_or(self):
        expr = {"media": "liquid", "temp_max": {"_gt": 100}}
        self.assertTrue(match_condition(expr, {"media": "liquid", "temp_max": 150}))
        self.assertFalse(match_condition(expr, {"media": "liquid", "temp_max": 50}))
        self.assertTrue(match_condition(expr, {"media": "gas", "temp_max": 150}, op="or"))

    def test_unknown_key_mismatch_and_warn(self):
        warnings = []
        self.assertFalse(match_condition({"bogus": {"_eq": 1}}, {"bogus": 1}, warnings=warnings))
        self.assertTrue(any("未知键" in w for w in warnings))

    def test_unknown_op_mismatch(self):
        warnings = []
        self.assertFalse(match_condition({"rated_cv": {"_between": 1}}, {"rated_cv": 1}, warnings=warnings))
        self.assertTrue(any("未知算子" in w for w in warnings))

    def test_non_dict_mismatch(self):
        warnings = []
        self.assertFalse(match_condition("not-a-dict", {}, warnings=warnings))
        self.assertTrue(warnings)

    def test_missing_value_under_compare_is_false_no_warn(self):
        warnings = []
        self.assertFalse(match_condition({"rated_cv": {"_max": 100}}, {}, warnings=warnings))
        self.assertEqual(warnings, [])


# ---------------------------------------------------------------------------
# _cv_ratio_to_stk
# ---------------------------------------------------------------------------
class TestCvRatioToStk(unittest.TestCase):
    def test_bounds(self):
        self.assertEqual(_cv_ratio_to_stk(0.0, "linear", None, 100, None), 0.0)
        self.assertEqual(_cv_ratio_to_stk(1.0, "linear", None, 100, None), 1.0)
        self.assertEqual(_cv_ratio_to_stk(-0.5, "linear", None, 100, None), 0.0)
        self.assertIsNone(_cv_ratio_to_stk(None, "linear", None, 100, None))

    def test_linear(self):
        self.assertAlmostEqual(_cv_ratio_to_stk(0.5, "linear", None, 100, None), 0.5)

    def test_ln_eqn(self):
        got = _cv_ratio_to_stk(0.5, "ln_eqn", None, 100, 50)
        self.assertAlmostEqual(got, 1 + math.log(0.5) / math.log(50))

    def test_exp_formula(self):
        eqcv = {"a0": math.log(0.5), "divisor": 1}
        self.assertAlmostEqual(_cv_ratio_to_stk(0.5, "exp_formula", eqcv, 100, None), 0.5)

    def test_poly_cv_div100(self):
        eqcv = {"a1": 1.0}
        self.assertAlmostEqual(_cv_ratio_to_stk(0.5, "poly_cv_div100", eqcv, 100, None), 0.5)

    def test_poly_phi100_div100(self):
        eqcv = {"a1": 1.0}
        self.assertAlmostEqual(_cv_ratio_to_stk(0.5, "poly_phi100_div100", eqcv, 100, None), 0.5)

    def test_poly_div60(self):
        eqcv = {"a1": 1.0, "divisor": 100}
        self.assertAlmostEqual(_cv_ratio_to_stk(0.5, "poly_div60", eqcv, 100, None), 0.5)

    def test_poly_cv_div_angle(self):
        eqcv = {"a1": 1.0, "divisor": 100}
        self.assertAlmostEqual(_cv_ratio_to_stk(0.5, "poly_cv_div_angle", eqcv, 100, None), 0.5)

    def test_eq_index(self):
        eqcv = {"a1": 1.0}
        self.assertAlmostEqual(_cv_ratio_to_stk(0.5, "eq_index", eqcv, 100, None), 0.5)

    def test_default_mode_falls_back_to_eq_index(self):
        eqcv = {"a1": 1.0}
        self.assertAlmostEqual(_cv_ratio_to_stk(0.5, "", eqcv, 100, None), 0.5)


# ---------------------------------------------------------------------------
# _ParsedRule (JSON 字符串 → dict)
# ---------------------------------------------------------------------------
class TestParsedRule(unittest.TestCase):
    def test_parses_json_strings(self):
        row = rule_row("R-X", "scope", expr={"media": "liquid"},
                       action="exclude", payload={"score": 3})
        pr = _ParsedRule(row)
        self.assertEqual(pr.condition_expr, {"media": "liquid"})
        self.assertEqual(pr.action_payload, {"score": 3})

    def test_none_stays_none(self):
        pr = _ParsedRule(rule_row("R-Y", "scope", expr=None))
        self.assertIsNone(pr.condition_expr)


# ---------------------------------------------------------------------------
# 四阶段
# ---------------------------------------------------------------------------
class TestScopeStage(unittest.TestCase):
    def test_exclude_by_category(self):
        fdb = FakeDB(
            series=[series("GC120", "globe"), series("BT110", "butterfly", "BT系列蝶阀")],
            rules=[rule_row("R-SCOPE-GLOBAL-001", "scope",
                            expr={"series_category": {"_eq": "butterfly"}}, action="exclude")],
        )
        sel = _TestSelector(fdb)
        warns = []
        surv = sel._stage_scope(_input(), {}, warns)
        self.assertEqual([v.series_code for v in surv], ["GC120"])

    def test_require_keeps_only_match(self):
        fdb = FakeDB(
            series=[series("GC120", "globe"), series("BV210", "ball", "BV系列球阀")],
            rules=[rule_row("R-SCOPE-GLOBAL-002", "scope",
                            expr={"series_category": {"_eq": "ball"}}, action="require")],
        )
        surv = _TestSelector(fdb)._stage_scope(_input(), {}, [])
        self.assertEqual([v.series_code for v in surv], ["BV210"])

    def test_soft_deleted_rule_not_applied(self):
        fdb = FakeDB(
            series=[series("GC120", "globe"), series("BT110", "butterfly", "BT系列蝶阀")],
            rules=[rule_row("R-SCOPE-GLOBAL-003", "scope",
                            expr={"series_category": {"_ne": "butterfly"}},
                            action="exclude", active=False)],
        )
        surv = _TestSelector(fdb)._stage_scope(_input(), {}, [])
        self.assertEqual(sorted(v.series_code for v in surv), ["BT110", "GC120"])

    def test_target_series_scoped_rule(self):
        """target_series 仅对指定系列生效。"""
        fdb = FakeDB(
            series=[series("GC120", "globe"), series("GC210", "globe", "GC系列套筒调节阀")],
            rules=[rule_row("R-SCOPE-GC120-001", "scope", target="GC120",
                            expr={"media": "liquid"}, action="exclude")],
        )
        surv = _TestSelector(fdb)._stage_scope(_input(media="liquid"), {}, [])
        self.assertEqual([v.series_code for v in surv], ["GC210"])


class TestConstraintStage(unittest.TestCase):
    def _run(self, cv_rows, rules, cv_required=50.0):
        fdb = FakeDB(series=[series("GC120", "globe")], rules=rules, cv_rows=cv_rows)
        sel = _TestSelector(fdb, cv_required=cv_required)
        with patch("app.calc.selector._load_curves", _fake_curves_linear):
            return sel._stage_constraint(_input(), {}, [series("GC120", "globe")], [])

    def test_exclude_by_rated_cv(self):
        rows = [cv_row("GC120", dn_label="40A", rated_cv=100.0),
                cv_row("GC120", dn_label="50A", rated_cv=20.0)]
        # rated_cv ≥ 50 视为过大 → 排除；仅保留 rated_cv=20 的 50A
        rules = [rule_row("R-CON-GC120-001", "constraint", target="GC120",
                          expr={"rated_cv": {"_min": 50}}, action="exclude")]
        cands = self._run(rows, rules)
        self.assertEqual([c["dn_label"] for c in cands], ["50A"])

    def test_opening_is_stk_percent(self):
        """linear 模式下 opening = phi×100 (cv_required/rated_cv)。"""
        rows = [cv_row("GC120", dn_label="40A", rated_cv=100.0)]
        cands = self._run(rows, [], cv_required=50.0)
        self.assertAlmostEqual(cands[0]["opening"], 50.0)

    def test_rangeability_and_ctx(self):
        rows = [cv_row("GC120", dn_label="40A", rated_cv=100.0, cv_min=10.0)]
        cands = self._run(rows, [])
        self.assertAlmostEqual(cands[0]["rangeability"], 10.0)
        self.assertIn("ctx", cands[0])

    def test_rangeability_required_hard_check(self):
        rows = [cv_row("GC120", dn_label="40A", rated_cv=100.0, cv_min=50.0)]
        inp = _input(rangeability_required=10.0)
        fdb = FakeDB(series=[series("GC120", "globe")], rules=[], cv_rows=rows)
        sel = _TestSelector(fdb, cv_required=50.0)
        with patch("app.calc.selector._load_curves", _fake_curves_linear):
            cands = sel._stage_constraint(inp, {}, [series("GC120", "globe")], [])
        self.assertEqual(cands, [])

    def test_require_multi_operator_window(self):
        """require 条件同键多算子（_min 与 _max）按 AND 组合：只保留窗口内候选。"""
        rules = [rule_row("R-CON-GC120-002", "constraint", target="GC120",
                          expr={"rangeability": {"_min": 50, "_max": 200}}, action="require")]
        rows_in = [cv_row("GC120", dn_label="40A", rated_cv=100.0, cv_min=1.0)]   # R=100 在窗口内
        cands = self._run(rows_in, rules)
        self.assertAlmostEqual(cands[0]["rangeability"], 100.0)
        # R=10 低于下限 → 被剔除
        rows_out = [cv_row("GC120", dn_label="40A", rated_cv=100.0, cv_min=10.0)]
        self.assertEqual(self._run(rows_out, rules), [])


class TestPreferenceStage(unittest.TestCase):
    def test_cavitation_boost(self):
        rows = [cv_row("GC210", dn_label="40A", rated_cv=100.0)]
        rules = [rule_row("R-PREF-GC210-001", "preference", target="GC210",
                          expr={"flow_regime": {"_or": ["空化", "闪蒸"]}},
                          action="boost", payload={"score": 10})]
        fdb = FakeDB(series=[series("GC210", "globe")], rules=rules, cv_rows=rows)
        sel = _TestSelector(fdb, cv_required=50.0, flow_regime="空化")
        with patch("app.calc.selector._load_curves", _fake_curves_linear):
            cands = sel._stage_constraint(_input(), {}, [series("GC210", "globe")], [])
        sel._stage_preference(_input(), {}, cands, [])
        self.assertEqual(cands[0]["score"], 10)
        self.assertIn("R-PREF-GC210-001", cands[0]["applied_rules"])

    def test_no_boost_when_not_matching(self):
        rows = [cv_row("GC210", dn_label="40A", rated_cv=100.0)]
        rules = [rule_row("R-PREF-GC210-002", "preference", target="GC210",
                          expr={"flow_regime": {"_or": ["空化", "闪蒸"]}},
                          action="boost", payload={"score": 10})]
        fdb = FakeDB(series=[series("GC210", "globe")], rules=rules, cv_rows=rows)
        sel = _TestSelector(fdb, cv_required=50.0, flow_regime="层流")
        with patch("app.calc.selector._load_curves", _fake_curves_linear):
            cands = sel._stage_constraint(_input(), {}, [series("GC210", "globe")], [])
        sel._stage_preference(_input(), {}, cands, [])
        self.assertEqual(cands[0]["score"], 0)


class TestPostFilterStage(unittest.TestCase):
    def _cands(self, rules, opening_ctx):
        rows = [cv_row("GC120", dn_label="40A", rated_cv=100.0)]
        fdb = FakeDB(series=[series("GC120", "globe")], rules=rules, cv_rows=rows)
        sel = _TestSelector(fdb, cv_required=opening_ctx)
        with patch("app.calc.selector._load_curves", _fake_curves_linear):
            cands = sel._stage_constraint(_input(), {}, [series("GC120", "globe")], [])
        sel._stage_post_filter(_input(), {}, cands, [])
        return cands

    def test_opening_window_penalty(self):
        rules = [rule_row("R-POST-GLOBAL-001", "post_filter",
                          expr={"opening": {"_lt": 20}}, action="penalty",
                          payload={"score": 5})]
        # opening = 10% → 命中 penalty
        cands = self._cands(rules, opening_ctx=10.0)
        self.assertEqual(cands[0]["score"], -5)

        # opening = 50% → 不命中
        cands2 = self._cands(rules, opening_ctx=50.0)
        self.assertEqual(cands2[0]["score"], 0)

    def test_flag_and_set_field(self):
        rules = [
            rule_row("R-POST-GLOBAL-002", "post_filter", expr={}, action="flag",
                     payload={"flag": "review"}),
            rule_row("R-POST-GLOBAL-003", "post_filter", expr={}, action="set_field",
                     payload={"field": "stroke_mode"}),
        ]
        cands = self._cands(rules, opening_ctx=50.0)
        self.assertTrue(cands[0]["flags"].get("review"))
        self.assertEqual(cands[0]["flags"].get("stroke_mode"), "linear")


class TestButterflyAngleSwitch(unittest.TestCase):
    def test_multi_flow_char_candidates(self):
        """BT 系列按 flow_char(60°/90°) 生成多个候选。"""
        rows = [
            cv_row("BT110", dn_label="80A", flow_char="60deg", trim_type="60° Open",
                   rated_cv=100.0, cv_min=25.0),
            cv_row("BT110", dn_label="80A", flow_char="90deg", trim_type="90° Open",
                   rated_cv=160.0, cv_min=40.0),
        ]
        fdb = FakeDB(series=[series("BT110", "butterfly", "BT系列蝶阀")], rules=[], cv_rows=rows)
        sel = _TestSelector(fdb, cv_required=50.0)
        with patch("app.calc.selector._load_curves", _fake_curves_linear):
            cands = sel._stage_constraint(_input(), {}, [series("BT110", "butterfly", "BT系列蝶阀")], [])
        self.assertEqual(sorted(c["flow_char"] for c in cands), ["60deg", "90deg"])


class TestSelectEntry(unittest.TestCase):
    def test_full_select_shape(self):
        rows = [cv_row("GC120", dn_label="40A", rated_cv=100.0, cv_min=10.0)]
        rules = [rule_row("R-PREF-GC120-001", "preference", target="GC120",
                          expr={"media": "liquid"}, action="boost", payload={"score": 3})]
        fdb = FakeDB(series=[series("GC120", "globe")], rules=rules, cv_rows=rows)
        sel = _TestSelector(fdb, cv_required=50.0)
        with patch("app.calc.selector._load_curves", _fake_curves_linear):
            res = sel.select(_input(media="liquid"))
        self.assertEqual(len(res.candidates), 1)
        self.assertEqual(res.candidates[0].rank, 1)
        self.assertEqual(res.candidates[0].series_code, "GC120")
        self.assertAlmostEqual(res.candidates[0].opening, 50.0)
        self.assertEqual(res.applied_rule_count, 1)


if __name__ == "__main__":
    unittest.main()
