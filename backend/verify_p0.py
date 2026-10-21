"""P0 基础设施验收脚本

验证:
1. 4 张新表是否已创建
2. valve_cv_stk 是否包含 cv_min 列
3. ORM/Schema 能否正常导入编译
"""
from app.core.database import engine
from sqlalchemy import text


def verify_tables():
    expected = ['selection_rules', 'body_pt_ratings', 'allowable_pressure_drops', 'selection_records']
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT name FROM sys.tables WHERE name IN (:a, :b, :c, :d)"
        ), {"a": expected[0], "b": expected[1], "c": expected[2], "d": expected[3]})
        found = [r[0] for r in result.fetchall()]
    missing = set(expected) - set(found)
    if missing:
        print(f"[FAIL] Missing tables: {missing}")
        return False
    print(f"[PASS] All 4 new tables exist: {found}")
    return True


def verify_cv_min():
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) FROM sys.columns WHERE object_id = OBJECT_ID('valve_cv_stk') AND name = 'cv_min'"
        ))
        exists = result.scalar() > 0
    if exists:
        print("[PASS] cv_min column exists in valve_cv_stk")
        return True
    print("[FAIL] cv_min column missing in valve_cv_stk")
    return False


def verify_orm():
    try:
        from app.models import SelectionRule, BodyPtRating, AllowablePressureDrop, SelectionRecord
        print("[PASS] ORM models import OK")
        return True
    except Exception as e:
        print(f"[FAIL] ORM import error: {e}")
        return False


def verify_schemas():
    try:
        from app.schemas import (
            SelectionRuleOut, SelectionInput, CandidateOut,
            SelectionResultOut, SelectionRecordOut
        )
        print("[PASS] Schemas import OK")
        return True
    except Exception as e:
        print(f"[FAIL] Schema import error: {e}")
        return False


if __name__ == "__main__":
    results = [
        verify_orm(),
        verify_schemas(),
        verify_tables(),
        verify_cv_min(),
    ]
    if all(results):
        print("\n=== P0 验收通过 ===")
    else:
        print("\n=== P0 验收失败 ===")
        exit(1)
