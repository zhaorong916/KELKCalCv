"""选型匹配引擎（P2）

四阶段流水线: scope(10) → constraint(20) → preference(30) → post_filter(40)

复用既有能力, 不重复造轮子:
  - Cv 反算: app.calc.engine.calculate_case
  - 曲线解析(stroke_mode / eqcv / FL / Kc / Fd / xT): app.api.valve_types._get_curves_by_selection_impl
  - 系数结构: app.calc.cv_core.ValveCoeffs / FactorCurves / FactorCurve

设计要点:
  1. 规则条件为「受限 JSON 字典比较」, 禁止 eval/exec; 未知键告警且视为不匹配。
  2. `opening` 语义 = 曲线图中的 %Stk（行程百分比）; 由 phi = Cv_required / rated_cv
     按 stroke_mode 反解得到（移植前端 Calculation.vue::evalEqcv 全部分支）。
  3. 角行程(BT/BV)按 valve_cv_stk 中的 flow_char/seat_type 行自动切换候选 Cv。

MVP 简化（已在 P2 计划中记录, 由 P3/P4 精细化）:
  - cv_required 只用中性系数(FL=0.9/xT=0.72)算 1 次, 各候选复用, 再按候选曲线反解开度;
    这样避免逐候选跑整套引擎; 候选级 FL/xT 差异对流态判定的影响留待 P4 打通。
  - 介质物性: 优先 special_req.fluid_id → fluid_name 查 fluids 表; 查不到时用通用兜底,
    并在 warnings 中提示（P3 接入项目介质后消除）。
"""
from __future__ import annotations

import json
import math
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import (
    ValveType,
    ValveCvStk,
    SelectionRule,
    BodyPtRating,
    AllowablePressureDrop,
)
from app.schemas import SelectionInput, CandidateOut, SelectionResultOut

# ---------------------------------------------------------------------------
# 条件表达式白名单与算子
# ---------------------------------------------------------------------------
# 数值型
_NUMERIC_KEYS = {
    "temp", "temp_min", "temp_max", "p1", "p1_max", "dp", "dp_max",
    "dp_ratio", "dp_ratio_max", "cv_required", "cv_min", "cv_max",
    "pipe_size", "pipe_size_min", "pipe_size_max", "opening", "rangeability",
    "rated_cv", "rangeability_required",
}
# 字符串/枚举型
_ENUM_KEYS = {
    "media", "flow_regime", "leakage_class", "valve_action",
    "series_category", "series_product_line",
}
# 布尔型
_BOOL_KEYS = {"nace", "fire_safe", "copper_free", "low_temp", "high_temp"}

CONDITION_WHITELIST = _NUMERIC_KEYS | _ENUM_KEYS | _BOOL_KEYS

# 支持的算子: _eq/_ne(布尔·枚举·数值)  _min/_max(含端点)  _gt/_lt(严格)  _required  _or(候选集合)
OPS = {"_eq", "_ne", "_min", "_max", "_gt", "_lt", "_required", "_or"}

CATEGORY_PRIORITY = {"scope": 10, "constraint": 20, "preference": 30, "post_filter": 40}


class _ParsedRule:
    """规则解析视图: 把 ORM 行中的 JSON 字符串字段解析为字典, 便于匹配。"""

    __slots__ = ("rule_code", "category", "target_series", "condition_expr",
                 "condition_op", "action", "action_payload", "is_active")

    def __init__(self, row):
        self.rule_code = row.rule_code
        self.category = row.category
        self.target_series = row.target_series
        self.condition_expr = _loads(row.condition_expr)
        self.condition_op = row.condition_op or "and"
        self.action = row.action
        self.action_payload = _loads(row.action_payload)
        self.is_active = bool(row.is_active)


def _loads(val):
    if val is None or isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except (TypeError, ValueError):
        return None


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _num(v: Any) -> Optional[float]:
    try:
        if v is None or isinstance(v, bool):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 条件求值器（受限 JSON, 无 eval/exec）
# ---------------------------------------------------------------------------
def match_condition(expr: Any, ctx: dict, op: str = "and",
                    warnings: Optional[list] = None) -> bool:
    """判断上下文 ctx 是否满足条件表达式 expr。

    expr 形如 ``{"key": {"_min": 25, "_max": 300}}`` 或简写 ``{"key": value}``（等价 _eq）。
    多键之间按 op（and / or）组合；单键内部多算子视为 and。

    未知键 → 追加 warning 并返回 False（视为不匹配）；缺失值（ctx 无该键或为 None）
    在比较型算子下返回 False，不产生告警。
    """
    if expr is None:
        return True
    if not isinstance(expr, dict):
        if warnings is not None:
            warnings.append(f"条件表达式格式非法(应为字典): {expr!r}")
        return False
    if not expr:
        return True

    results = []
    for key, cond in expr.items():
        if key not in CONDITION_WHITELIST:
            if warnings is not None:
                warnings.append(f"规则条件含未知键 '{key}'，该规则视为不匹配")
            return False

        if isinstance(cond, dict):
            bad = [k for k in cond.keys() if k not in OPS]
            if bad:
                if warnings is not None:
                    warnings.append(f"规则条件键 '{key}' 含未知算子 {bad}，该规则视为不匹配")
                return False
            op_conds = cond
        else:
            op_conds = {"_eq": cond}

        ctx_val = ctx.get(key)
        key_results = [_eval_op(ctx_val, o, v) for o, v in op_conds.items()]
        results.append(all(key_results))

    return all(results) if (op or "and").lower() == "and" else any(results)


def _eval_op(ctx_val: Any, op: str, val: Any) -> bool:
    if op == "_required":
        want = bool(val)
        has = ctx_val not in (None, "", [], {}, ())
        return has == want
    if op == "_or":
        if ctx_val is None:
            return False
        candidates = val if isinstance(val, (list, tuple, set)) else [val]
        return ctx_val in candidates
    if op == "_eq":
        if val is None:
            return ctx_val is None
        if isinstance(val, bool):
            return bool(ctx_val) is val if ctx_val is not None else False
        n_c, n_v = _num(ctx_val), _num(val)
        if n_c is not None and n_v is not None:
            return math.isclose(n_c, n_v, rel_tol=1e-9, abs_tol=1e-9)
        return str(ctx_val) == str(val)
    if op == "_ne":
        return not _eval_op(ctx_val, "_eq", val)
    n_c, n_v = _num(ctx_val), _num(val)
    if n_c is None or n_v is None:
        return False
    if op == "_min":
        return n_c >= n_v
    if op == "_max":
        return n_c <= n_v
    if op == "_gt":
        return n_c > n_v
    if op == "_lt":
        return n_c < n_v
    return False


# ---------------------------------------------------------------------------
# stroke_mode → %Stk 反解（移植前端 Calculation.vue::evalEqcv）
# ---------------------------------------------------------------------------
def _cv_ratio_to_stk(phi: Optional[float], stroke_mode: str, eqcv: Optional[dict],
                     rated_cv: Optional[float], fstk: Optional[float],
                     divisor: Optional[float] = None) -> Optional[float]:
    """phi(Cv/Cv_rated) → %Stk(0~1)。与前端 evalEqcv 逐分支对齐。"""
    if phi is None:
        return None
    phi = _clamp01(float(phi))
    if phi <= 0:
        return 0.0
    if phi >= 1:
        return 1.0

    c = eqcv or {}
    a = [float(c.get(f"a{i}") or 0.0) for i in range(7)]
    cv_val = phi * (rated_cv or 0.0)
    mode = stroke_mode or "linear"

    if mode == "linear":
        return phi

    if mode == "ln_eqn":
        f = fstk or 50.0
        if f <= 1.0:
            f = 50.0
        return _clamp01(1.0 + math.log(phi) / math.log(f))

    if mode == "exp_formula":
        ln_cv = math.log(max(cv_val, 1e-9))
        denom = cv_val + a[2]
        frac = (a[1] / denom) if denom != 0 else 0.0
        arg = a[4] * ln_cv + a[3] * cv_val + frac + a[0]
        arg = max(-700.0, min(700.0, arg))
        d = divisor or c.get("divisor") or 60.0
        return _clamp01(math.exp(arg) / d)

    if mode == "poly_cv_div100":
        stk = a[4] * cv_val ** 4 + a[3] * cv_val ** 3 + a[2] * cv_val ** 2 + a[1] * cv_val + a[0]
        return _clamp01(stk / 100.0)

    if mode == "poly_phi100_div100":
        x = phi * 100.0
        stk = (a[5] * x ** 5 + a[4] * x ** 4 + a[3] * x ** 3
               + a[2] * x ** 2 + a[1] * x + a[0])
        return _clamp01(stk / 100.0)

    if mode in ("poly_cv_div_angle", "poly_div60"):
        d = divisor or c.get("divisor") or 60.0
        stk = (a[5] * cv_val ** 5 + a[4] * cv_val ** 4 + a[3] * cv_val ** 3
               + a[2] * cv_val ** 2 + a[1] * cv_val + a[0])
        return _clamp01(stk / d)

    # eq_index / 默认: 霍纳公式 (A6..A0 × phi)
    stk = ((a[6] * phi + a[5]) * phi + a[4]) * phi + a[3]
    stk = (stk * phi + a[2]) * phi + a[1]
    stk = stk * phi + a[0]
    return _clamp01(stk)


# ---------------------------------------------------------------------------
# 候选分组与曲线加载
# ---------------------------------------------------------------------------
def _series_candidate_rows(db: Session, series_code: str) -> list:
    """按 (dn_label, trim_label, flow_char, trim_type, seat_type, pressure_rating)
    分组, 每组取行程最小的代表行（角行程 60°/90° 等由 flow_char 天然分组）。"""
    rows = db.query(ValveCvStk).filter(
        ValveCvStk.series_code == series_code,
        ValveCvStk.rated_cv.isnot(None),
    ).all()
    groups: dict = {}
    for r in rows:
        key = (r.dn_label, r.trim_label, r.flow_char, r.trim_type, r.seat_type, r.pressure_rating)
        cur = groups.get(key)
        if cur is None or (r.stroke_value or 0) < (cur.stroke_value or 0):
            groups[key] = r
    return list(groups.values())


def _load_curves(db: Session, series_code: str, pressure_rating: str, dn_label: str,
                 trim_label: str, trim_type: str, flow_char: str, seat_type: str):
    """懒加载 valve_types 的曲线解析（避免 api ←→ calc 的导入环）。"""
    from app.api.valve_types import _get_curves_by_selection_impl
    return _get_curves_by_selection_impl(
        series_code=series_code,
        pressure_rating=pressure_rating or "",
        plug_size=0,
        nominal_dn=dn_label or "",
        nominal_trim=trim_label or "",
        trim_type=trim_type or "",
        trim_seat_type="",
        flow_direction="",
        opening_angle="",
        seat_type=seat_type or "",
        trim_characteristics=flow_char or "",
        db=db,
    )


# ---------------------------------------------------------------------------
# 引擎
# ---------------------------------------------------------------------------
class ValveSelector:
    """四阶段选型匹配引擎。无状态（规则每次从库读取）。"""

    def __init__(self, db: Session, stages: int = 1):
        self.db = db
        self.stages = max(1, int(stages or 1))
        self._rules_by_cat: dict[str, list] = {}

    # -- 规则缓存 ----------------------------------------------------------
    def _rules(self, category: str) -> list:
        """读取并解析该类规则（condition_expr / action_payload 由 JSON 字符串解析为字典）。

        软删规则（is_active=False）不参与匹配。
        """
        if not self._rules_by_cat:
            rows = (self.db.query(SelectionRule)
                    .order_by(SelectionRule.priority, SelectionRule.rule_code).all())
            self._rules_by_cat = {}
            for r in rows:
                self._rules_by_cat.setdefault(r.category, []).append(_ParsedRule(r))
        return [r for r in self._rules_by_cat.get(category, []) if r.is_active]

    def _load_active_series(self) -> list:
        return self.db.query(ValveType).filter(ValveType.is_active == True).all()  # noqa: E712

    @staticmethod
    def _rule_applies(rule: "_ParsedRule", series_code: str) -> bool:
        return rule.target_series in ("*", series_code)

    # -- 上下文构建 --------------------------------------------------------
    def _base_ctx(self, inp: SelectionInput, special: dict) -> dict:
        temp = _num(getattr(inp, "t1", None))
        p1 = _num(getattr(inp, "p1", None))
        p2 = _num(getattr(inp, "p2", None))
        dp = _num(getattr(inp, "dp", None))
        if dp is None and p1 is not None and p2 is not None:
            dp = p1 - p2
        dp_ratio = (dp / p1) if (dp is not None and p1) else None
        return {
            "media": getattr(inp, "media", None),
            "temp": temp, "temp_min": temp, "temp_max": temp,
            "p1": p1, "p1_max": p1,
            "dp": dp, "dp_max": dp,
            "dp_ratio": dp_ratio, "dp_ratio_max": dp_ratio,
            "cv_required": _num(getattr(inp, "cv_required", None)),
            "leakage_class": getattr(inp, "leakage_class", None),
            "pipe_size": _num(getattr(inp, "pipe_size", None)),
            "pipe_size_min": _num(getattr(inp, "pipe_size", None)),
            "pipe_size_max": _num(getattr(inp, "pipe_size", None)),
            "valve_action": getattr(inp, "valve_action", None) or "modulating",
            "rangeability_required": _num(getattr(inp, "rangeability_required", None)),
            "nace": bool(special.get("nace")),
            "fire_safe": bool(special.get("fire_safe")),
            "copper_free": bool(special.get("copper_free")),
            "low_temp": bool(special.get("low_temp")) or (temp is not None and temp < -45),
            "high_temp": bool(special.get("high_temp")) or (temp is not None and temp > 230),
        }

    @staticmethod
    def _series_ctx(vt: ValveType) -> dict:
        return {
            "series_category": vt.valve_category,
            "series_product_line": vt.product_line,
        }

    # -- 阶段 1: scope -----------------------------------------------------
    def _stage_scope(self, inp, special, warnings) -> list:
        ctx = self._base_ctx(inp, special)
        rules = self._rules("scope")
        survivors = []
        for vt in self._load_active_series():
            sc = vt.series_code
            s_ctx = dict(ctx)
            s_ctx.update(self._series_ctx(vt))
            ok = True
            for rule in rules:
                if not self._rule_applies(rule, sc):
                    continue
                matched = match_condition(rule.condition_expr, s_ctx, rule.condition_op, warnings)
                if rule.action == "exclude" and matched:
                    ok = False
                    break
                if rule.action == "require" and not matched:
                    ok = False
                    break
            if ok:
                survivors.append(vt)
        return survivors

    # -- 阶段 2: constraint + Cv 评估 --------------------------------------
    def _stage_constraint(self, inp, special, survivors, warnings) -> list:
        base_ctx = self._base_ctx(inp, special)
        cv_required = self._calc_cv_required(inp, special, warnings)
        flow_regime = getattr(self, "_flow_regime", "") or ""
        base_ctx["flow_regime"] = flow_regime or None
        if cv_required is not None:
            base_ctx["cv_required"] = cv_required

        constraint_rules = self._rules("constraint")
        out = []
        for vt in survivors:
            sc = vt.series_code
            for row in _series_candidate_rows(self.db, sc):
                cand = self._build_candidate(row)
                ctx = dict(base_ctx)
                ctx.update(self._series_ctx(vt))
                ctx["rated_cv"] = cand["rated_cv"]
                ctx["cv_min"] = cand["cv_min"]

                # 曲线解析（缺失时跳过该候选）
                try:
                    curves = _load_curves(
                        self.db, sc, cand["pressure_rating"], cand["dn_label"],
                        cand["trim_label"], cand["trim_type"], cand["flow_char"],
                        cand["seat_type"],
                    )
                except Exception as e:  # HTTPException(404) / 无曲线配置
                    warnings.append(f"{sc} {cand['dn_label']}/{cand['trim_label']} 曲线解析失败: {e}")
                    continue

                # 开度 (%Stk) 与可调比
                info = curves.get("stroke_info") or {}
                divisor = info.get("divisor") or (curves.get("stroke_info") or {}).get("opening_angle")
                opening = None
                if cv_required and cand["rated_cv"]:
                    phi = cv_required / cand["rated_cv"]
                    stk = _cv_ratio_to_stk(
                        phi, curves.get("stroke_mode"), curves.get("eqcv"),
                        cand["rated_cv"], info.get("fstk"), divisor,
                    )
                    opening = None if stk is None else round(stk * 100.0, 2)
                ctx["opening"] = opening

                rangeability = None
                if cand["cv_min"]:
                    rangeability = round(cand["rated_cv"] / cand["cv_min"], 2) if cand["rated_cv"] else None
                else:
                    warnings.append(f"{sc} {cand['dn_label']}/{cand['trim_label']} 缺少 cv_min，可调比未知")
                ctx["rangeability"] = rangeability

                # 可调比硬校核（跨字段比较, 交由引擎而非规则表达式）
                req_ra = _num(getattr(inp, "rangeability_required", None))
                if req_ra and rangeability is not None and rangeability < req_ra:
                    warnings.append(
                        f"{sc} {cand['dn_label']}/{cand['trim_label']} 可调比 {rangeability} < 要求 {req_ra}"
                    )
                    continue

                # 阀体材质温压校核（special_req 提供材质+等级时才校核）
                pc = special.get("pressure_class")
                mg = special.get("body_material")
                if pc and mg:
                    allow = self.body_pt_allow(pc, mg, ctx.get("temp_max"))
                    p1_mpa = (ctx.get("p1_max") or 0.0) / 1000.0
                    if allow is not None and p1_mpa > allow:
                        warnings.append(
                            f"{sc} {cand['dn_label']}/{cand['trim_label']} 阀前压力 {p1_mpa:.3f} MPa "
                            f"超过 {mg}/{pc} 在 {ctx.get('temp_max')}℃ 下允许值 {allow:.3f} MPa"
                        )
                        continue

                ok = True
                for rule in constraint_rules:
                    if not self._rule_applies(rule, sc):
                        continue
                    matched = match_condition(rule.condition_expr, ctx, rule.condition_op, warnings)
                    if rule.action == "exclude" and matched:
                        ok = False
                        break
                    if rule.action == "require" and not matched:
                        ok = False
                        break
                if not ok:
                    continue

                # 最大允许压差（数据仅覆盖部分系列, 超限先告警不硬剔）
                self._check_allowable_dp(sc, ctx.get("dp"), warnings)

                cand["opening"] = opening
                cand["rangeability"] = rangeability
                cand["stroke_mode"] = curves.get("stroke_mode")
                cand["fd_mode"] = curves.get("fd_mode")
                cand["flow_regime"] = flow_regime or None
                cand["series_name"] = vt.series_name
                cand["series_category"] = vt.valve_category
                cand["ctx"] = ctx
                out.append(cand)
        return out

    @staticmethod
    def _build_candidate(row: ValveCvStk) -> dict:
        return {
            "series_code": row.series_code,
            "dn_label": row.dn_label,
            "trim_label": row.trim_label,
            "flow_char": row.flow_char,
            "trim_type": row.trim_type,
            "seat_type": row.seat_type,
            "pressure_rating": row.pressure_rating,
            "rated_cv": row.rated_cv,
            "cv_min": row.cv_min,
            "stroke_value": row.stroke_value,
            "score": 0,
            "applied_rules": [],
            "flags": {},
        }

    # -- 阶段 3: preference（加权） ----------------------------------------
    def _stage_preference(self, inp, special, candidates, warnings) -> None:
        rules = self._rules("preference")
        for cand in candidates:
            ctx = cand["ctx"]
            score = 0
            applied = []
            for rule in rules:
                if not self._rule_applies(rule, cand["series_code"]):
                    continue
                if not match_condition(rule.condition_expr, ctx, rule.condition_op, warnings):
                    continue
                payload = rule.action_payload or {}
                pts = int(payload.get("score", 0) or 0)
                if rule.action == "boost":
                    score += abs(pts)
                elif rule.action == "penalty":
                    score -= abs(pts)
                else:
                    continue
                applied.append(rule.rule_code)
            cand["score"] = score
            cand["applied_rules"] = applied

    # -- 阶段 4: post_filter（补字段 / 开度窗口扣分） -----------------------
    def _stage_post_filter(self, inp, special, candidates, warnings) -> None:
        rules = self._rules("post_filter")
        for cand in candidates:
            ctx = cand["ctx"]
            for rule in rules:
                if not self._rule_applies(rule, cand["series_code"]):
                    continue
                if not match_condition(rule.condition_expr, ctx, rule.condition_op, warnings):
                    continue
                payload = rule.action_payload or {}
                if rule.action == "penalty":
                    cand["score"] -= abs(int(payload.get("score", 0) or 0))
                elif rule.action == "flag":
                    flag = payload.get("flag")
                    if flag:
                        cand["flags"][flag] = True
                elif rule.action == "set_field":
                    field = payload.get("field")
                    if field == "fd_mode" and cand.get("fd_mode"):
                        cand["flags"]["fd_mode"] = cand["fd_mode"]
                    elif field == "flow_regime" and cand.get("flow_regime"):
                        cand["flags"]["flow_regime"] = cand["flow_regime"]
                    elif field == "stroke_mode" and cand.get("stroke_mode"):
                        cand["flags"]["stroke_mode"] = cand["stroke_mode"]
                cand["applied_rules"] = list(dict.fromkeys(cand["applied_rules"] + [rule.rule_code]))
            if cand["flow_regime"]:
                cand["flags"].setdefault("flow_regime", cand["flow_regime"])
            if cand["stroke_mode"]:
                cand["flags"].setdefault("stroke_mode", cand["stroke_mode"])
            if not cand["cv_min"]:
                cand["flags"]["no_cv_min"] = True

    # -- Cv 反算（每输入一次） ---------------------------------------------
    def _calc_cv_required(self, inp, special, warnings) -> Optional[float]:
        from app.calc.cv_core import ValveCoeffs
        from app.calc.engine import calculate_case

        # 多工况复用同一 selector 实例时, 必须在每次反算前重置流态,
        # 避免上一工况的 flow_regime 在本次反算异常时泄漏到当前工况。
        self._flow_regime = ""

        fluid = self._build_fluid(inp, special, warnings)
        p1 = _num(inp.p1)
        p2 = _num(inp.p2)
        dp = _num(inp.dp)
        t1 = _num(inp.t1) or 20.0
        if p1 is None and dp is not None and p2 is not None:
            p1 = p2 + dp
        if p2 is None and p1 is not None and dp is not None:
            p2 = p1 - dp
        if p1 is None or p2 is None:
            warnings.append("缺少阀前/阀后压力，无法反算 Cv（仅保留候选）")
            return None

        flow_unit, mass_flow, vol_flow = self._parse_flow(inp)
        try:
            cr = calculate_case(
                case_no=1, case_name="selection", fluid=fluid,
                valve_coeffs=ValveCoeffs(rated_cv=0.0, stages=self.stages),
                p1=p1, p2=p2, t1=t1,
                mass_flow=mass_flow, vol_flow=vol_flow, flow_unit=flow_unit,
                pipe_diameter=_num(inp.pipe_size) or 0.0, pipe_wall=0.0, distance=1.0,
            )
        except Exception as e:
            warnings.append(f"Cv 反算异常: {e}")
            return None
        self._flow_regime = getattr(cr.cv, "flow_regime", "") if cr.cv else ""
        if cr.cv is None:
            warnings.append(f"Cv 反算失败: {cr.message}")
            return None
        warnings.extend([w for w in (cr.cv.warnings or []) if w not in warnings])
        return cr.cv.cv_required

    @staticmethod
    def _parse_flow(inp) -> tuple:
        q = _num(getattr(inp, "flow_rate", None)) or 0.0
        unit = (getattr(inp, "flow_rate_unit", None) or "").lower()
        if any(t in unit for t in ("m3", "nm3", "m³", "l/h", "l/min")):
            return "vol", 0.0, q
        return "mass", q, 0.0

    def _build_fluid(self, inp, special, warnings) -> dict:
        from app.models import Fluid
        fluid = None
        fid = special.get("fluid_id")
        if fid:
            fluid = self.db.get(Fluid, int(fid))
        if fluid is None and getattr(inp, "fluid_name", None) is not None:
            fluid = self.db.query(Fluid).filter(Fluid.fluid_name == inp.fluid_name).first()
        if fluid is None:
            warnings.append("未匹配到介质物性，采用通用兜底（P3 接入项目介质后消除）")
            return {
                "fluid_name": getattr(inp, "fluid_name", None) or "未知介质",
                "is_water": False, "default_state": None,
                "density_liquid": None, "density_gas": None,
                "molecular_weight": None, "cp_cv_ratio": None,
                "critical_pressure": None, "vapor_pressure": None, "viscosity": None,
            }
        return {
            "fluid_name": fluid.fluid_name, "is_water": fluid.is_water,
            "default_state": fluid.default_state,
            "density_liquid": fluid.density_liquid, "density_gas": fluid.density_gas,
            "molecular_weight": fluid.molecular_weight, "cp_cv_ratio": fluid.cp_cv_ratio,
            "critical_pressure": fluid.critical_pressure, "vapor_pressure": fluid.vapor_pressure,
            "viscosity": fluid.viscosity,
        }

    # -- 允许压差校核 -------------------------------------------------------
    def _check_allowable_dp(self, series_code: str, dp_kpa: Optional[float], warnings) -> None:
        if dp_kpa is None:
            return
        rows = self.db.query(AllowablePressureDrop).filter(
            AllowablePressureDrop.series_code == series_code
        ).all()
        if not rows:
            warnings.append(f"{series_code} 缺少最大允许压差数据，未校核")
            return
        max_dp_mpa = max((r.max_dp_mpa or 0.0) for r in rows)
        if dp_kpa / 1000.0 > max_dp_mpa:
            warnings.append(
                f"{series_code} 压差 {dp_kpa/1000.0:.3f} MPa 超过允许压差上限 {max_dp_mpa:.3f} MPa"
            )

    # -- 体材质温压校核（线性插值, source_series 透明） ---------------------
    def body_pt_allow(self, pressure_class: str, material_grade: str,
                      temp_c: Optional[float]) -> Optional[float]:
        if not pressure_class or not material_grade or temp_c is None:
            return None
        rows = self.db.query(BodyPtRating).filter(
            BodyPtRating.pressure_class == pressure_class,
            BodyPtRating.material_grade == material_grade,
        ).order_by(BodyPtRating.temp_c).all()
        if not rows:
            return None
        pts = [(r.temp_c, r.pressure_mpa_g) for r in rows]
        if temp_c <= pts[0][0]:
            return pts[0][1]
        if temp_c >= pts[-1][0]:
            return pts[-1][1]
        for (t_a, p_a), (t_b, p_b) in zip(pts, pts[1:]):
            if t_a <= temp_c <= t_b:
                if t_b == t_a:
                    return p_a
                k = (temp_c - t_a) / (t_b - t_a)
                return p_a + k * (p_b - p_a)
        return None

    # -- 主入口 -------------------------------------------------------------
    def select(self, inp: SelectionInput) -> SelectionResultOut:
        warnings: list[str] = []
        special = dict(getattr(inp, "special_req", None) or {})

        survivors = self._stage_scope(inp, special, warnings)
        candidates = self._stage_constraint(inp, special, survivors, warnings)
        self._stage_preference(inp, special, candidates, warnings)
        self._stage_post_filter(inp, special, candidates, warnings)

        # 排序: score 降序 → 开度接近 60~80 窗口 → rated_cv 升序
        def _sort_key(c):
            op = c["opening"] if c["opening"] is not None else 999.0
            return (-c["score"], abs(op - 70.0), c["rated_cv"] or 0.0)

        candidates.sort(key=_sort_key)

        out = []
        for i, c in enumerate(candidates, start=1):
            out.append(CandidateOut(
                rank=i,
                series_code=c["series_code"],
                series_name=c["series_name"],
                dn_label=c["dn_label"],
                trim_label=c["trim_label"],
                flow_char=c["flow_char"],
                rated_cv=c["rated_cv"],
                cv_min=c["cv_min"],
                opening=c["opening"],
                rangeability=c["rangeability"],
                score=c["score"],
                applied_rules=c["applied_rules"],
                flags=c["flags"] or None,
            ))

        applied = set()
        for c in candidates:
            applied.update(c["applied_rules"])
        return SelectionResultOut(
            candidates=out,
            applied_rule_count=len(applied),
            warnings=list(dict.fromkeys(warnings)),
        )
