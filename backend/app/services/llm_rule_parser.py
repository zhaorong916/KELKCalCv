"""大模型辅助解析：自然语言 → 选型规则（只产出候选，不写库）

约束与 app/calc/selector.py 的条件白名单保持一致，模型输出必须通过本模块校验，
校验不通过直接报错，绝不把模型臆造的键写入规则库。
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple

from app.calc.selector import (
    CONDITION_WHITELIST,
    OPS,
    LOGIC_OPS,
    _BOOL_KEYS,
    _ENUM_KEYS,
    _NUMERIC_KEYS,
    CATEGORY_PRIORITY,
)
from app.core.config import settings

ALLOWED_CATEGORIES = {"scope", "constraint", "preference", "post_filter"}
ALLOWED_ACTIONS = {"exclude", "require", "boost", "set_field", "flag", "penalty"}

SYSTEM_PROMPT = """你是调节阀选型规则编译器。把中文规则描述编译成 JSON 规则对象。

【条件键（只能使用这些，不得自创）】
数值型（单位固定，必须填数字）：
  temp_min / temp_max / temp（设计温度，℃）
  p1 / p1_max（阀前压力，kPa 绝压）
  dp / dp_max（压差，kPa）
  dp_ratio / dp_ratio_max（压差比）
  cv_required、cv_min、cv_max、rated_cv（Cv 值）
  pipe_size / pipe_size_min / pipe_size_max（公称通径，mm）
  opening（开度，%）、rangeability / rangeability_required（可调比）
枚举型（填字符串，_or 时填字符串数组）：
  media：liquid / gas / steam / twophase
  flow_regime：空化 / 闪蒸 / 阻塞流 / 正常
  leakage_class：IV / V / VI
  valve_action：FC / FO
  series_category、series_product_line
布尔型（填 true / false）：nace、fire_safe、copper_free、low_temp、high_temp

【算子（写在条件键下的子对象里）】
_eq 等于、_ne 不等于、_lt 小于（严格）、_gt 大于（严格）、
_min 不低于（含等号 ≥）、_max 不高于（含等号 ≤）、_required（要求存在/缺省）、
_or 取值集合

【动作 action】
exclude 排除候选、require 硬性要求、boost 加分（action_payload={"score":n}）、
penalty 扣分（{"score":n}）、set_field 回填字段（{"field":"字段名"}）、flag 标记（{"flag":"标记名"}）

【类别 category】
scope：温度/口径这类适用范围边界
constraint：压力、泄漏等级、介质等硬约束
preference：工况偏好加分
post_filter：字段回填、标记

【硬性规则】
1 数值统一换算：MPa→kPa 乘 1000，bar→kPa 乘 100；温度 ℃；通径 mm。
2 低于/小于用 _lt；不低于/至少用 _min；高于/大于用 _gt；不高于/最多用 _max；区间拆成 *_min 的 _min 与 *_max 的 _max。
3 同一物理量按比较方向选键：下限类写 *_min，上限类写 *_max。
4 描述无法可靠解析时返回 {"error":"原因"}，不要猜、不要编造键。
5 只输出一个 JSON 对象，不要输出解释文字或代码块标记。

【输出结构】
{"rule_name":"一句话名称","category":"scope|constraint|preference|post_filter",
 "target_series":"BT110|*","condition_expr":{"键":{"算子":值}},
 "condition_op":"and|or","action":"exclude|require|boost|penalty|set_field|flag",
 "action_payload":{},"notes":"可选说明"}"""

FEW_SHOT = [
    ("BT110 在设计温度低于 -5℃ 时排除",
     '{"rule_name":"BT110 低温下限 -5℃","category":"scope","target_series":"BT110",'
     '"condition_expr":{"temp_min":{"_lt":-5}},"condition_op":"and","action":"exclude",'
     '"action_payload":{}}'),
    ("空化或闪蒸时 GC210 加 30 分",
     '{"rule_name":"空化/闪蒸偏好 GC210","category":"preference","target_series":"GC210",'
     '"condition_expr":{"flow_regime":{"_or":["空化","闪蒸"]}},"condition_op":"and",'
     '"action":"boost","action_payload":{"score":30}}'),
    ("阀前压力超过 1.6MPa 时 BT110 不适用",
     '{"rule_name":"BT110 阀前压力上限 1.6MPa","category":"constraint","target_series":"BT110",'
     '"condition_expr":{"p1_max":{"_gt":1600}},"condition_op":"and","action":"exclude",'
     '"action_payload":{}}'),
]


class LlmUnavailable(RuntimeError):
    """大模型未配置或调用失败"""


class ModelRefused(ValueError):
    """模型明确表示该描述无法编译为规则"""


def is_configured() -> bool:
    return bool((settings.LLM_API_KEY or "").strip())


def _chat(messages: List[Dict[str, str]]) -> str:
    url = settings.LLM_API_BASE.rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": settings.LLM_MODEL,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 600,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.LLM_API_KEY.strip()}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.LLM_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:200]
        except Exception:  # pragma: no cover
            pass
        raise LlmUnavailable(f"大模型接口返回 {exc.code}：{detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise LlmUnavailable(f"无法连接大模型接口（{settings.LLM_API_BASE}）：{exc.reason}") from exc
    except TimeoutError as exc:
        raise LlmUnavailable(f"大模型接口超时（{settings.LLM_TIMEOUT}s）") from exc

    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmUnavailable("大模型返回结构不符合 OpenAI 兼容格式") from exc


def _extract_json(text: str) -> Dict[str, Any]:
    """容忍 ```json 代码块/前后说明文字，提取第一个 JSON 对象"""
    raw = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.I)
    if fenced:
        raw = fenced.group(1).strip()
    if not raw.startswith("{"):
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型输出不是合法 JSON（{exc.msg}）") from exc


def _as_number(key: str, value: Any, warnings: List[str]) -> float | int:
    if isinstance(value, bool):
        raise ValueError(f"条件键 {key} 需要数值，模型给出布尔值")
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            num = float(value.strip())
        except ValueError as exc:
            raise ValueError(f"条件键 {key} 需要数值，模型给出「{value}」") from exc
        warnings.append(f"条件键 {key} 的数值以字符串返回，已按 {num} 处理")
        return int(num) if num.is_integer() else num
    raise ValueError(f"条件键 {key} 需要数值，模型给出 {type(value).__name__}")


def _check_value(key: str, value: Any, warnings: List[str]) -> Any:
    if key in _NUMERIC_KEYS:
        return _as_number(key, value, warnings)
    if key in _BOOL_KEYS:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            warnings.append(f"条件键 {key} 的布尔值以字符串返回，已转换")
            return value.strip().lower() == "true"
        raise ValueError(f"条件键 {key} 需要布尔值，模型给出「{value}」")
    if key in _ENUM_KEYS:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            return [v.strip() for v in value]
        raise ValueError(f"条件键 {key} 需要字符串或字符串数组，模型给出 {type(value).__name__}")
    raise ValueError(f"条件键 {key} 不在白名单")


def _validate_expr(expr: Any, warnings: List[str]) -> Dict[str, Any]:
    """递归校验条件表达式：支持 $and/$or 嵌套与普通条件键。"""
    if not isinstance(expr, dict):
        raise ValueError("条件表达式必须是 JSON 对象")

    # 逻辑算子：$and / $or，值为子表达式数组
    if len(expr) == 1:
        only_key = next(iter(expr))
        if only_key in LOGIC_OPS:
            sub = expr[only_key]
            if not isinstance(sub, list) or not sub:
                raise ValueError(f"{only_key} 需要非空数组")
            return {only_key: [_validate_expr(s, warnings) for s in sub]}

    clean: Dict[str, Any] = {}
    for key, cond in expr.items():
        if key not in CONDITION_WHITELIST:
            raise ValueError(f"条件键 {key} 不在允许清单内")
        if isinstance(cond, dict):
            ops: Dict[str, Any] = {}
            for op, val in cond.items():
                if op not in OPS:
                    raise ValueError(f"条件键 {key} 使用了未知算子 {op}")
                if op == "_required":
                    if not isinstance(val, bool):
                        raise ValueError(f"{key}._required 需要布尔值")
                    ops[op] = val
                elif op == "_or":
                    if not isinstance(val, list) or not val:
                        raise ValueError(f"{key}._or 需要非空数组")
                    ops[op] = [_check_value(key, v, warnings) for v in val]
                else:
                    ops[op] = _check_value(key, val, warnings)
            clean[key] = ops
        else:
            clean[key] = {"_eq": _check_value(key, cond, warnings)}
    return clean


def _validate(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    if not isinstance(payload, dict):
        raise ValueError("模型输出不是 JSON 对象")

    expr = payload.get("condition_expr") or {}
    if not isinstance(expr, dict):
        raise ValueError("condition_expr 必须是 JSON 对象")
    clean_expr = _validate_expr(expr, warnings)

    action = payload.get("action")
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"action「{action}」不在允许清单内")

    category = payload.get("category")
    if category not in ALLOWED_CATEGORIES:
        category = {"exclude": "constraint", "require": "constraint",
                    "boost": "preference", "penalty": "preference",
                    "flag": "post_filter", "set_field": "post_filter"}.get(action, "constraint")
        warnings.append(f"category 缺失或非法，已按动作推断为 {category}")

    action_payload = payload.get("action_payload")
    if action_payload is None:
        action_payload = {}
    if not isinstance(action_payload, dict):
        raise ValueError("action_payload 必须是 JSON 对象")
    if action in {"boost", "penalty"}:
        if not action_payload.get("score"):
            warnings.append("加减分动作缺少 score，请在动作参数中补充")
        elif not isinstance(action_payload.get("score"), (int, float)):
            raise ValueError("加分/扣分的 score 必须是数字")
    if action == "set_field" and not action_payload.get("field"):
        warnings.append("set_field 缺少 field，请在动作参数中补充字段名")
    if action == "flag" and not action_payload.get("flag"):
        warnings.append("flag 缺少标记名，请在动作参数中补充")

    series = str(payload.get("target_series") or "*").strip() or "*"
    if not re.fullmatch(r"[A-Za-z0-9_*.\-]{1,32}", series):
        warnings.append(f"目标系列「{series}」格式异常，已改为全局 *")
        series = "*"
    else:
        series = series.upper() if series != "*" else series

    condition_op = (payload.get("condition_op") or "and").lower()
    if condition_op not in {"and", "or"}:
        warnings.append(f"condition_op「{condition_op}」非法，已按 and 处理")
        condition_op = "and"

    rule_name = str(payload.get("rule_name") or "").strip()[:128]
    if not rule_name:
        rule_name = f"{series} 规则"

    note = payload.get("notes")
    if isinstance(note, str) and note.strip():
        warnings.append(note.strip())

    rule = {
        "rule_code": "",  # 由后端自动生成，模型不参与编号
        "rule_name": rule_name,
        "category": category,
        "target_series": series,
        "condition_expr": clean_expr,
        "condition_op": condition_op,
        "action": action,
        "action_payload": action_payload,
        "priority": CATEGORY_PRIORITY.get(category, 10),
        "is_active": True,
    }
    return rule, warnings


def parse(text: str) -> Tuple[Dict[str, Any], List[str]]:
    """调用大模型解析；返回 (规则, 警告)。未配置/调用失败抛 LlmUnavailable，输出不合规抛 ValueError"""
    if not is_configured():
        raise LlmUnavailable("后端未配置大模型：请在 backend/.env 设置 LLM_API_KEY")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for desc, out in FEW_SHOT:
        messages.append({"role": "user", "content": desc})
        messages.append({"role": "assistant", "content": out})
    messages.append({"role": "user", "content": text.strip()})

    payload = _extract_json(_chat(messages))
    if payload.get("error"):
        raise ModelRefused(str(payload["error"]))
    return _validate(payload)
