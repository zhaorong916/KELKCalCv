"""测试 adapter 解析功能"""
import sys
from pathlib import Path

# 添加 backend 到 path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.data_adapters import get_adapter, list_registered_series


def test_adapter(series_code: str):
    """测试单个 adapter"""
    print(f"\n{'='*60}")
    print(f"Testing {series_code}")
    print('='*60)

    try:
        adapter = get_adapter(series_code)

        # 测试 parse_rated_cv
        cv_rows = adapter.parse_rated_cv()
        print(f"parse_rated_cv: {len(cv_rows)} rows")
        if cv_rows:
            print(f"  Sample row: {cv_rows[0]}")
            # 统计 flow_char 分布
            from collections import Counter
            fc_dist = Counter(r['flow_char'] for r in cv_rows)
            print(f"  Flow char distribution: {dict(fc_dist)}")

        # 测试 parse_allowable_dp
        dp_rows = adapter.parse_allowable_dp()
        print(f"parse_allowable_dp: {len(dp_rows)} rows")
        if dp_rows:
            print(f"  Sample row: {dp_rows[0]}")

        # 测试 parse_body_pt
        pt_rows = adapter.parse_body_pt()
        print(f"parse_body_pt: {len(pt_rows)} rows")
        if pt_rows:
            print(f"  Sample row: {pt_rows[0]}")

        return True
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("Registered series:", list_registered_series())

    results = {}
    for series in ["GC120", "GC210", "GC320", "GV120", "BT210", "BV210", "GA510",
                   "GV110", "GV130", "BT110", "BT310", "BV130", "GZ810"]:
        results[series] = test_adapter(series)

    print(f"\n{'='*60}")
    print("Summary")
    print('='*60)
    for series, success in results.items():
        status = "PASS" if success else "FAIL"
        print(f"  {series}: {status}")


if __name__ == "__main__":
    main()
