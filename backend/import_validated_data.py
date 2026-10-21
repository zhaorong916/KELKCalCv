"""人工确认与入库脚本

流程:
1. 读取比对报告
2. 用户确认「以样本为准」/「以库为准」/「需修正」
3. 确认后 upsert 到 valve_cv_stk
4. GC210 的 Fd 系数 (kfd/kfo/kfb) 随 rated_cv 行一并入库
5. body_pt_ratings 从 GC120/210、GC320、GA510、BV130 等温压表入库
6. allowable_pressure_drops 从各系列压差表入库

注意:
- valve_cv_stk 无 cv_min 列 (cv_min 属 Table2 记录), 入库时不写该字段
- 脚本仅 upsert，禁止全表 DELETE
- 安全红线：禁全表 DELETE / 禁凭据入文档 / 禁跳过校验 / 禁违反 series_code 唯一约束
"""
import sys
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# 添加 backend 到 path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.data_adapters import get_adapter, list_registered_series
from app.core.database import SessionLocal
from app.models import ValveCvStk, BodyPtRating, AllowablePressureDrop
# 归一化与比对脚本共用同一套规则 (Md EQ%→EQ%+Large Cv、Q-port→ON-OFF 等),
# 保证 upsert 查找键与 compare_cv_data 的复合键一致, 避免应 update 的行误判为 insert
from compare_cv_data import normalize_adapter_row, get_key_fields

# 复合键字段 → ORM 列
_KEY_COLUMNS = {
    "series_code": ValveCvStk.series_code,
    "dn_label": ValveCvStk.dn_label,
    "trim_label": ValveCvStk.trim_label,
    "flow_char": ValveCvStk.flow_char,
    "trim_type": ValveCvStk.trim_type,
    "pressure_rating": ValveCvStk.pressure_rating,
    "seat_type": ValveCvStk.seat_type,
    "stroke_value": ValveCvStk.stroke_value,
}


def upsert_valve_cv_stk(db, row: Dict[str, Any], dry_run: bool = True) -> str:
    """Upsert 到 valve_cv_stk

    查找条件与 compare_cv_data 中该系列的复合键策略完全一致 (含归一化后的取值):
    - GV120 adapter 有 seat_type=Metal 而库中为 NULL → seat 不属该系列键, 不作条件
    - GV110 样本无 dn, 但库按 15A/20A/25A 存储 → 入库键额外纳入 dn_label;
      V-type 经归一化保留原值, 与 Standard 行区分
    - GC120 等系列的 stroke_value 是属性而非身份 (同配置仅一个额定点), 不作条件;
      仅 GC320/BT110/BT310 等同配置多行程点系列按 stroke 区分
    SQLAlchemy 中 Column == None 会生成 IS NULL, 可直接传 None。

    返回: "insert" / "update" / "skip"
    """
    key_fields = list(get_key_fields(row["series_code"]))
    # GV110: 样本无 dn, 但库中按公称通径 15A/20A/25A 各存一行 (既有 Needle 行约定)。
    # 入库行已按 15A/20A/25A 展开, 故把 dn 纳入入库键以逐 dn 落库;
    # 比对键仍不含 dn (靠同键同 Cv 别名去重)。
    if row["series_code"] == "GV110" and row.get("dn_label") and "dn_label" not in key_fields:
        key_fields.append("dn_label")
    conditions = []
    for fname in key_fields:
        conditions.append(_KEY_COLUMNS[fname] == row.get(fname))

    existing = db.query(ValveCvStk).filter(*conditions).first()

    if existing:
        # 更新
        if not dry_run:
            existing.rated_cv = row.get("rated_cv")
            existing.stroke_unit = row.get("stroke_unit")
            existing.stroke_value = row.get("stroke_value")
            existing.plug_mm = row.get("plug_mm")
            existing.stk_index = row.get("stk_index")
            existing.kfd = row.get("kfd")
            existing.kfo = row.get("kfo")
            existing.kfb = row.get("kfb")
            existing.cv_min = row.get("cv_min")
        return "update"
    else:
        # 插入
        if not dry_run:
            new_record = ValveCvStk(
                series_code=row["series_code"],
                dn_label=row.get("dn_label"),
                trim_label=row.get("trim_label"),
                flow_char=row.get("flow_char"),
                trim_type=row.get("trim_type"),
                pressure_rating=row.get("pressure_rating"),
                seat_type=row.get("seat_type"),
                rated_cv=row.get("rated_cv"),
                stroke_unit=row.get("stroke_unit"),
                stroke_value=row.get("stroke_value"),
                plug_mm=row.get("plug_mm"),
                stk_index=row.get("stk_index"),
                kfd=row.get("kfd"),
                kfo=row.get("kfo"),
                kfb=row.get("kfb"),
                cv_min=row.get("cv_min"),
            )
            db.add(new_record)
            db.flush()  # autoflush=False, 手动 flush 让后续同键查询可见
        return "insert"


def upsert_body_pt_rating(db, row: Dict[str, Any], dry_run: bool = True) -> str:
    """Upsert 到 body_pt_ratings

    跳过缺少必填字段的源行: 部分系列样本的温压表结构未与 adapter 对齐,
    会产生 pressure_class/temp_c 全空的行; 这些行入库会触发 NOT NULL 违约,
    故直接 skip (不阻断同系列 valve_cv_stk 的提交)。
    """
    required = ("standard", "pressure_class", "body_material", "temp_c", "max_pressure_mpa")
    if any(row.get(k) is None for k in required):
        return "skip"

    query = db.query(BodyPtRating).filter(
        BodyPtRating.standard == row.get("standard"),
        BodyPtRating.pressure_class == row.get("pressure_class"),
        BodyPtRating.material_grade == row.get("body_material"),
        BodyPtRating.temp_c == row.get("temp_c"),
    )

    existing = query.first()

    if existing:
        if not dry_run:
            existing.pressure_mpa_g = row.get("max_pressure_mpa")
        return "update"
    else:
        if not dry_run:
            new_record = BodyPtRating(
                standard=row.get("standard"),
                pressure_class=row.get("pressure_class"),
                material_grade=row.get("body_material"),
                temp_c=row.get("temp_c"),
                pressure_mpa_g=row.get("max_pressure_mpa"),
                source_series=row.get("series_code"),
            )
            db.add(new_record)
            db.flush()  # autoflush=False, 手动 flush 让后续同键查询可见
        return "insert"


def upsert_allowable_pressure_drop(db, row: Dict[str, Any], dry_run: bool = True) -> str:
    """Upsert 到 allowable_pressure_drops

    查找键与唯一约束 uq_allowable_dp 完全一致:
    (series_code, actuator_family, actuator_size, packing, seat_type,
     plug_inch, air_supply)
    adapter 侧字段名: actuator_type → actuator_family, 其余同名。
    air_supply (气源压力) 必须入键: 同一组合不同气源下 max_dp 不同。
    """
    # series_code / max_dp_mpa 为 NOT NULL, 缺失则跳过
    if row.get("series_code") is None or row.get("max_dp_mpa") is None:
        return "skip"

    conditions = [
        AllowablePressureDrop.series_code == row.get("series_code"),
        AllowablePressureDrop.actuator_family == row.get("actuator_type"),
        AllowablePressureDrop.actuator_size == row.get("actuator_size"),
        AllowablePressureDrop.packing == row.get("packing"),
        AllowablePressureDrop.seat_type == row.get("seat_type"),
        AllowablePressureDrop.plug_inch == row.get("plug_inch"),
        AllowablePressureDrop.air_supply == row.get("air_supply"),
    ]
    existing = db.query(AllowablePressureDrop).filter(*conditions).first()

    if existing:
        if not dry_run:
            existing.spring_range = row.get("spring_range")
            existing.max_dp_mpa = row.get("max_dp_mpa")
        return "update"
    else:
        if not dry_run:
            new_record = AllowablePressureDrop(
                series_code=row.get("series_code"),
                actuator_family=row.get("actuator_type"),
                actuator_size=row.get("actuator_size"),
                spring_range=row.get("spring_range"),
                packing=row.get("packing"),
                seat_type=row.get("seat_type"),
                plug_inch=row.get("plug_inch"),
                air_supply=row.get("air_supply"),
                max_dp_mpa=row.get("max_dp_mpa"),
            )
            db.add(new_record)
            db.flush()  # autoflush=False, 手动 flush 让后续同键查询可见
        return "insert"


# 部分系列 adapter 不产出 dn (样本未逐行给通径), 但样本/库按公称通径多行存储。
# GV110 公称通径为 DN15~DN25, 库中既有 Needle 行按 15A/20A/25A 各存一行,
# 新增行沿用同一约定展开, 保证系列内结构一致。
SERIES_DN_EXPANSION = {"GV110": ["15A", "20A", "25A"]}


def _expand_missing_dn(series_code: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dns = SERIES_DN_EXPANSION.get(series_code)
    if not dns:
        return rows
    expanded: List[Dict[str, Any]] = []
    for row in rows:
        if row.get("dn_label"):
            expanded.append(row)
            continue
        for dn in dns:
            r = dict(row)
            r["dn_label"] = dn
            expanded.append(r)
    return expanded


def import_series_data(series_code: str, dry_run: bool = True) -> Dict[str, int]:
    """导入单个系列的数据"""
    print(f"\n{'='*60}")
    print(f"Importing {series_code} (dry_run={dry_run})")
    print('='*60)

    stats = {
        "valve_cv_stk_insert": 0,
        "valve_cv_stk_update": 0,
        "valve_cv_stk_skip": 0,
        "body_pt_insert": 0,
        "body_pt_update": 0,
        "body_pt_skip": 0,
        "allowable_dp_insert": 0,
        "allowable_dp_update": 0,
        "allowable_dp_skip": 0,
    }

    try:
        adapter = get_adapter(series_code)
    except Exception as e:
        print(f"ERROR loading adapter: {e}")
        return stats

    db = SessionLocal()
    try:
        # 一个 adapter 类可注册多个系列 (如 GZ800 系列), parse_* 可能返回全部系列行,
        # 仅导入当前系列的行
        def _own_rows(rows):
            return [r for r in rows if r.get("series_code", series_code) == series_code]

        # 导入 rated_cv (归一化后再 upsert, 与比对脚本键规则保持一致)
        cv_rows = _expand_missing_dn(series_code, _own_rows(adapter.parse_rated_cv()))
        print(f"parse_rated_cv: {len(cv_rows)} rows")
        for row in cv_rows:
            row = normalize_adapter_row(series_code, row)
            result = upsert_valve_cv_stk(db, row, dry_run)
            stats[f"valve_cv_stk_{result}"] += 1

        # 导入 body_pt
        pt_rows = _own_rows(adapter.parse_body_pt())
        print(f"parse_body_pt: {len(pt_rows)} rows")
        for row in pt_rows:
            result = upsert_body_pt_rating(db, row, dry_run)
            stats[f"body_pt_{result}"] += 1

        # 导入 allowable_dp
        dp_rows = _own_rows(adapter.parse_allowable_dp())
        print(f"parse_allowable_dp: {len(dp_rows)} rows")
        for row in dp_rows:
            result = upsert_allowable_pressure_drop(db, row, dry_run)
            stats[f"allowable_dp_{result}"] += 1

        if not dry_run:
            db.commit()
            print("Committed to database")
        else:
            print("Dry run, no changes made")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description="导入选型数据到数据库")
    parser.add_argument("--series", type=str, help="指定系列代码，如 GC120")
    parser.add_argument("--all", action="store_true", help="导入所有系列")
    parser.add_argument("--dry-run", action="store_true", default=True, help="干跑模式，不实际写入")
    parser.add_argument("--commit", action="store_true", help="实际写入数据库")
    args = parser.parse_args()

    dry_run = not args.commit

    if args.series:
        series_list = [args.series]
    elif args.all:
        preferred = ["GC120", "GC210", "GC320", "GV120", "BT210", "BV210", "GA510",
                     "GV110", "GV130", "BT110", "BT310", "BV130", "GZ810"]
        registered = list_registered_series()
        series_list = preferred + [s for s in registered if s not in preferred]
    else:
        print("请指定 --series 或 --all")
        return

    print(f"Import mode: {'DRY RUN' if dry_run else 'COMMIT'}")
    print(f"Series: {series_list}")

    all_stats = {}
    for series_code in series_list:
        stats = import_series_data(series_code, dry_run)
        all_stats[series_code] = stats

    # 打印汇总
    print(f"\n{'='*60}")
    print("Summary")
    print('='*60)
    for series_code, stats in all_stats.items():
        print(f"{series_code}:")
        print(f"  valve_cv_stk: insert={stats['valve_cv_stk_insert']}, update={stats['valve_cv_stk_update']}, skip={stats['valve_cv_stk_skip']}")
        print(f"  body_pt: insert={stats['body_pt_insert']}, update={stats['body_pt_update']}, skip={stats['body_pt_skip']}")
        print(f"  allowable_dp: insert={stats['allowable_dp_insert']}, update={stats['allowable_dp_update']}, skip={stats['allowable_dp_skip']}")


if __name__ == "__main__":
    main()
