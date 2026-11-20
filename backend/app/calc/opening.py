"""开度反算

优先按「Cv-行程」特性曲线反解开度（曲线模式与系数来自 valve_series_curve_config，
保存在 ValveConfig.stroke_mode / eqcv / fstk 中）；无曲线时按标准流量特性公式兜底。

与前端 Calculation.vue 的 computeOpeningByCurve/evalEqcv 保持同一算法。
"""
import json
import math

STANDARD_STROKES = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 1.00]


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _clamp_pct(v: float) -> float:
    return max(0.0, min(100.0, v))


def _coef(c: dict, i: int) -> float:
    v = c.get(f"a{i}")
    return float(v) if v is not None else 0.0


def _eval_eqcv(phi: float, mode: str, c: dict, rated_cv: float, fstk: float | None) -> float:
    """phi = Cv/Cv_rated → %Stk (0~1)"""
    if phi <= 0:
        return 0.0
    if phi >= 1:
        return 1.0
    c = c or {}
    cv_val = phi * (rated_cv or 0.0)
    a0, a1, a2, a3, a4, a5, a6 = (_coef(c, i) for i in range(7))
    divisor = float(c.get("divisor") or 60)

    if mode == "linear":
        return phi
    if mode == "ln_eqn":
        f = float(fstk or 50)
        if f <= 1:
            return phi
        return _clamp01(1 + math.log(phi) / math.log(f))
    if mode == "exp_formula":
        ln_cv = math.log(max(cv_val, 1e-9))
        arg = a4 * ln_cv + a3 * cv_val + a1 / (cv_val + a2) + a0
        arg = max(-700.0, min(700.0, arg))
        return _clamp01(math.exp(arg) / divisor)
    if mode == "poly_cv_div100":
        stk = a4 * cv_val ** 4 + a3 * cv_val ** 3 + a2 * cv_val ** 2 + a1 * cv_val + a0
        return _clamp01(stk / 100)
    if mode == "poly_phi100_div100":
        x = phi * 100
        stk = a5 * x ** 5 + a4 * x ** 4 + a3 * x ** 3 + a2 * x ** 2 + a1 * x + a0
        return _clamp01(stk / 100)
    if mode in ("poly_cv_div_angle", "poly_div60"):
        stk = a5 * cv_val ** 5 + a4 * cv_val ** 4 + a3 * cv_val ** 3 + a2 * cv_val ** 2 + a1 * cv_val + a0
        return _clamp01(stk / divisor)
    # eq_index 及默认：霍纳多项式
    stk = ((a6 * phi + a5) * phi + a4) * phi + a3
    stk = (stk * phi + a2) * phi + a1
    stk = stk * phi + a0
    return _clamp01(stk)


def _stk_to_phi(stk: float, mode: str, c: dict, rated_cv: float, fstk: float | None) -> float:
    """%Stk (0~1) → phi = Cv/Cv_rated（evalEqcv 的反函数）"""
    if stk <= 0:
        return 0.0
    if stk >= 1:
        return 1.0
    if mode == "linear":
        return stk
    if mode == "ln_eqn":
        f = float(fstk or 50)
        if f <= 1:
            return stk
        return _clamp01(math.exp((stk - 1) * math.log(f)))
    # 其余模式：二分法反解（假设 stk 随 phi 单调递增）
    lo, hi = 1e-6, 1.0
    phi = 0.5
    for _ in range(100):
        phi = (lo + hi) / 2
        if _eval_eqcv(phi, mode, c, rated_cv, fstk) > stk:
            hi = phi
        else:
            lo = phi
    return phi


def compute_opening(
    cv_required: float,
    rated_cv: float,
    *,
    stroke_mode: str | None = None,
    eqcv=None,
    fstk: float | None = None,
    characteristic: str | None = None,
    rangeability: float | None = None,
) -> float:
    """所需 Cv → 开度 %（0~100）。"""
    if not cv_required or cv_required <= 0 or not rated_cv or rated_cv <= 0:
        return 0.0

    coefs = eqcv
    if isinstance(coefs, str):
        try:
            coefs = json.loads(coefs)
        except Exception:
            coefs = None
    if not isinstance(coefs, dict):
        coefs = {}

    mode = (stroke_mode or "").strip()
    if mode and (mode == "linear" or coefs):
        pts = []
        for s in STANDARD_STROKES:
            phi = _stk_to_phi(s, mode, coefs, rated_cv, fstk)
            pts.append((phi * rated_cv, s * 100))
        pts.sort()
        if pts[-1][0] <= 0:
            return 0.0
        if cv_required >= pts[-1][0]:
            return 100.0
        if cv_required <= pts[0][0]:
            return _clamp_pct(pts[0][1])
        for (cv0, stk0), (cv1, stk1) in zip(pts, pts[1:]):
            if cv0 <= cv_required <= cv1:
                if cv1 == cv0:
                    return _clamp_pct(stk0)
                return _clamp_pct(stk0 + (cv_required - cv0) / (cv1 - cv0) * (stk1 - stk0))

    # 无曲线：按标准流量特性反算
    phi = cv_required / rated_cv
    tc = (characteristic or "").upper()
    if "LINEAR" in tc or "线性" in (characteristic or ""):
        return _clamp_pct(phi * 100)
    if phi <= 0:
        return 0.0
    r = float(rangeability or 50)
    if r <= 1:
        return _clamp_pct(phi * 100)
    # 等百分比: phi = R^(stk/100 - 1)
    return _clamp_pct((math.log(phi) / math.log(r) + 1) * 100)
