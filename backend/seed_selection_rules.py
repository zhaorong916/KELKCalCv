"""选型规则库 seed 脚本（P2 任务 2.1）

读取 docs/selection_rules_v1.json → 校验 → 落库 selection_rules。

用法:
    python seed_selection_rules.py            # dry-run: 仅校验 + 计数（默认）
    python seed_selection_rules.py --commit   # 实际写入/更新

幂等策略（P2 决策, 已同步至 P2 实施计划）:
    selection_rules.rule_code 上有 UNIQUE 约束, 无法同时保留"旧版软删 + 新版插入"
    两条同 code 记录。因此 P2 采用 **按 rule_code 原地 upsert**（存在则整体更新字段）；
    规则版本化（软删 + 版本表）留待 P5 规则管理 UI 阶段, 届时如需历史版本再调整表结构。

安全: 不使用全表 DELETE; 仅按 rule_code 定向操作。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from app.core.database import SessionLocal
from app.models import SelectionRule
from app.schemas import SelectionRuleBase
from app.calc.selector import CONDITION_WHITELIST, CATEGORY_PRIORITY

DATA_FILE = Path(__file__).resolve().parent.parent / "docs" / "selection_rules_v2.json"

# 条件表达式允许的算子（与 selector.OPS 一致）
ALLOWED_OPS = {"_eq", "_ne", "_min", "_max", "_gt", "_lt", "_required", "_or"}
LOGIC_OPS = {"$and", "$or"}


def _validate_condition(expr, rule_code: str) -> list[str]:
    errs: list[str] = []
    if expr is None:
        return errs
    if not isinstance(expr, dict):
        return [f"{rule_code}: condition_expr 必须为字典或 null"]
    for key, cond in expr.items():
        if key in LOGIC_OPS:
            if not isinstance(cond, list):
                errs.append(f"{rule_code}: 逻辑算子 {key} 的值必须是数组")
                continue
            for i, sub in enumerate(cond):
                errs.extend(_validate_condition(sub, f"{rule_code}[{key}[{i}]]"))
            continue
        if key not in CONDITION_WHITELIST:
            errs.append(f"{rule_code}: 未知条件键 '{key}'")
            continue
        if isinstance(cond, dict):
            bad = [k for k in cond if k not in ALLOWED_OPS]
            if bad:
                errs.append(f"{rule_code}: 条件键 '{key}' 含未知算子 {bad}")
    return errs


def load_rules(path: Path = DATA_FILE) -> tuple[list[dict], list[str]]:
    """读取 + 校验规则清单, 返回 (规则列表, 错误列表)。"""
    if not path.exists():
        return [], [f"规则数据文件不存在: {path}"]
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return [], ["规则数据根节点必须为数组"]

    errors: list[str] = []
    seen: set[str] = set()
    rules: list[dict] = []
    for i, item in enumerate(raw):
        try:
            rule = SelectionRuleBase(**item).model_dump()
        except Exception as e:
            errors.append(f"[{i}] 校验失败: {e}")
            continue
        code = rule["rule_code"]
        if code in seen:
            errors.append(f"{code}: rule_code 重复")
            continue
        seen.add(code)
        # category → priority 一致性
        expect = CATEGORY_PRIORITY.get(rule["category"])
        if expect is not None and rule["priority"] != expect:
            errors.append(f"{code}: priority 应为 {expect}（category={rule['category']}），实为 {rule['priority']}")
        errors.extend(_validate_condition(rule.get("condition_expr"), code))
        rules.append(rule)
    return rules, errors


def _same(row, rule: dict) -> bool:
    """判断库中现有版本与待写入规则内容是否一致。"""
    return (
        row.rule_name == rule["rule_name"]
        and row.category == rule["category"]
        and row.target_series == rule["target_series"]
        and _loads(row.condition_expr) == rule.get("condition_expr")
        and row.condition_op == rule["condition_op"]
        and row.action == rule["action"]
        and _loads(row.action_payload) == rule.get("action_payload")
        and row.priority == rule["priority"]
        and row.source_ref == rule.get("source_ref")
        and bool(row.is_active) == bool(rule["is_active"])
    )


def _loads(val):
    if val is None or isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except (TypeError, ValueError):
        return None


def _new_row(rule: dict, version: int, prev_id) -> SelectionRule:
    return SelectionRule(
        rule_code=rule["rule_code"],
        version=version,
        prev_rule_id=prev_id,
        rule_name=rule["rule_name"],
        category=rule["category"],
        target_series=rule["target_series"],
        condition_expr=json.dumps(rule.get("condition_expr"), ensure_ascii=False)
        if rule.get("condition_expr") is not None else None,
        condition_op=rule["condition_op"],
        action=rule["action"],
        action_payload=json.dumps(rule.get("action_payload"), ensure_ascii=False)
        if rule.get("action_payload") is not None else None,
        priority=rule["priority"],
        source_ref=rule.get("source_ref"),
        is_active=rule["is_active"],
    )


def upsert(db, rules: list[dict], retire_missing: bool = False) -> dict:
    """版本化 upsert: 内容变化时旧版停用并插入 version+1。

    返回计数 {inserted, unchanged, versioned, retired, resurrected}。
    """
    stat = {"inserted": 0, "unchanged": 0, "versioned": 0, "retired": 0}
    codes = [r["rule_code"] for r in rules]
    rows = db.query(SelectionRule).filter(SelectionRule.rule_code.in_(codes)).all() if codes else []
    by_code: dict[str, list] = {}
    for r in rows:
        by_code.setdefault(r.rule_code, []).append(r)

    for rule in rules:
        code = rule["rule_code"]
        versions = sorted(by_code.get(code, []), key=lambda x: x.version or 1)
        active = [r for r in versions if r.is_active]
        max_ver = max((r.version or 1) for r in versions) if versions else 0
        if active and len(active) == 1 and _same(active[0], rule):
            stat["unchanged"] += 1
            continue
        if active:
            prev_id = active[0].id
            for r in active:
                r.is_active = False
            version = max_ver + 1
            stat["versioned"] += 1
        else:
            prev_id = versions[-1].id if versions else None
            version = max_ver + 1 if versions else 1
            stat["inserted"] += 1
        db.add(_new_row(rule, version, prev_id))
        db.flush()

    if retire_missing:
        for r in db.query(SelectionRule).filter(SelectionRule.is_active == True).all():  # noqa: E712
            if r.rule_code not in set(codes):
                r.is_active = False
                stat["retired"] += 1
    return stat


def main() -> int:
    ap = argparse.ArgumentParser(description="选型规则库 seed（默认 dry-run）")
    ap.add_argument("--commit", action="store_true", help="实际写入数据库")
    ap.add_argument("--retire-missing", action="store_true",
                    help="把库中启用、但清单里已不存在的规则置为停用（不删除）")
    ap.add_argument("--file", type=Path, default=DATA_FILE, help="规则 JSON 路径")
    args = ap.parse_args()

    rules, errors = load_rules(args.file)
    if errors:
        print("=== 校验失败 ===")
        for e in errors:
            print("  -", e)
        return 1

    by_cat = Counter(r["category"] for r in rules)
    print(f"=== 规则清单校验通过: 共 {len(rules)} 条 ===")
    for cat, prio in sorted(CATEGORY_PRIORITY.items(), key=lambda kv: kv[1]):
        print(f"  {cat:12s} (priority={prio}): {by_cat.get(cat, 0)}")

    if not args.commit:
        print("\n[dry-run] 未写入数据库。加 --commit 执行落库。")
        return 0

    with SessionLocal() as db:
        stat = upsert(db, rules, retire_missing=args.retire_missing)
        db.commit()
        total = db.query(SelectionRule).filter(SelectionRule.is_active == True).count()  # noqa: E712
    print(f"\n[commit] 新增 {stat['inserted']} 条, 新版本 {stat['versioned']} 条, "
          f"未变 {stat['unchanged']} 条, 停用 {stat['retired']} 条; 库中启用规则合计 {total} 条。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
