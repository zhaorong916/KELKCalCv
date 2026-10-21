"""比对 adapter 解析结果与 valve_cv_stk 库中数据，生成差异报告

流程:
1. 读取库中 valve_cv_stk 全部记录
2. 逐系列执行 adapter 解析，与库中记录按复合键比对
3. 差异 > 5% 的行生成差异报告
4. 差异 ≤ 5% 的行自动标记「与库一致」
5. 新系列（库中无记录）标记「全新入库」

输出:
- docs/数据比对报告/<系列>_diff.md
- docs/数据比对报告/summary.md
"""
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

# 添加 backend 到 path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.data_adapters import get_adapter, list_registered_series
from app.core.database import SessionLocal
from app.models import ValveCvStk


# 复合键字段（仅用于精确匹配）
KEY_FIELDS = ["series_code", "dn_label", "trim_label", "flow_char", "trim_type", "pressure_rating", "seat_type"]

# 匹配键策略：按系列定义使用哪些字段
# 默认使用宽松键 (series_code + dn_label + trim_label + flow_char)
# 有 pressure_rating 差异的系列需要包含 pressure_rating
# 有 trim_type 差异的系列需要包含 trim_type
SERIES_KEY_STRATEGY = {
    # 蝶阀有 60°/90° 开度和压力等级差异
    "BT210": ["series_code", "dn_label", "trim_label", "flow_char", "trim_type", "pressure_rating"],
    # BT110: 库中按 seat_type + stroke_value 区分 (Damper@90°, 15 Deg Sealed@75°, Back Seat@90°)
    "BT110": ["series_code", "dn_label", "trim_label", "flow_char", "trim_type", "seat_type", "stroke_value"],
    # BT310: 库中只有 90° 数据, adapter 60°/90° 需用 stroke_value 区分
    "BT310": ["series_code", "dn_label", "trim_label", "flow_char", "trim_type", "stroke_value"],
    # 球阀有压力等级差异
    "BV210": ["series_code", "dn_label", "trim_label", "flow_char", "trim_type", "pressure_rating"],
    "BV130": ["series_code", "dn_label", "trim_label", "flow_char"],
    # 直行程调节阀: 库中按 trim_type 区分 Standard / Large Cv (Modified),
    # adapter 的 "Md EQ%"/Full 口径归一化后必须用 trim_type 入键, 否则一对多
    "GC120": ["series_code", "dn_label", "trim_label", "flow_char", "trim_type"],
    "GC210": ["series_code", "dn_label", "trim_label", "flow_char", "trim_type"],
    # GC320: 多级降压阀, 同一 dn/trim 在不同行程点 (stroke_value) 各有一行 Cv
    "GC320": ["series_code", "dn_label", "trim_label", "flow_char", "trim_type", "stroke_value"],
    "GV120": ["series_code", "dn_label", "trim_label", "flow_char", "trim_type"],
    # GV110: 库中同一 trim 对应多个 dn (15A/20A/25A), adapter 无 dn → 键不含 dn;
    # 需 trim_type 区分 Needle(库中记 Standard) 与 V-type(库中无, 保留原值计新增)
    "GV110": ["series_code", "trim_label", "flow_char", "trim_type"],
    "GV130": ["series_code", "dn_label", "trim_label", "flow_char", "trim_type"],
    "GA510": ["series_code", "dn_label", "trim_label", "flow_char", "trim_type"],
    # GZ810: 需 trim_type 区分 Downstream/Upstream
    "GZ810": ["series_code", "dn_label", "trim_label", "flow_char", "trim_type"],
}

# trim_type 标准化映射：将 adapter 的 trim_type 映射到库中的 trim_type
# 用于处理命名不一致的情况
TRIM_TYPE_NORMALIZE = {
    # BT210: 库中 "Standard" 实际是 90° 开度
    "BT210": {
        "90° Open": "Standard",
        "60° Open": "60°",
    },
    # BT110: 库中 trim_type 全为 "Standard", 密封形式在 seat_type 字段
    "BT110": {
        "Damper": "Standard",
        "15 Deg Sealed": "Standard",
    },
    # BV130: 库中 trim_type 为 "ON-OFF"
    "BV130": {
        "Full Bore": "ON-OFF",
    },
    # GC120/GC210: adapter 用 Full 标记全口径内件, 库中统一记为 "Standard";
    # "Md EQ%" 行的 trim_type 在归一化尾部按 flow_char 联动改写为
    # Large Cv (GC120) / Modified (GC210)
    "GC120": {
        "Full": "Standard",
    },
    "GC210": {
        "Full": "Standard",
    },
    # GV120: P-port 为标准内件 → Standard; Q-port 为快开内件 → ON-OFF;
    # "Md EQ%" 行联动改写为 EQ% + Large Cv
    "GV120": {
        "P-port": "Standard",
        "Q-port": "ON-OFF",
    },
    # GA510: 标准内件全称 High Performance P-port → Standard; Q-port → ON-OFF
    "GA510": {
        "High Performance P-port": "Standard",
        "Q-port": "ON-OFF",
    },
    # GV130: P-port High EQ 为标准内件 → Standard; Large Cv 名称对齐; Q-port → ON-OFF
    "GV130": {
        "P-port High EQ": "Standard",
        "P-port Large Cv": "Large Cv",
        "Q-port": "ON-OFF",
    },
    # GV110: Needle 为库中标准内件 → Standard; V-type 库中无数据, 保留原值计入新增
    "GV110": {
        "Needle": "Standard",
    },
    # GZ810: 库中 trim_type 全为 "Standard" (仅 Downstream 数据);
    # Upstream 保留原值, 使其计入"新增"
    "GZ810": {
        "Downstream": "Standard",
    },
}

# flow_char 标准化映射：将 adapter 的 flow_char 映射到库中的 flow_char
FLOW_CHAR_NORMALIZE = {
    # BT110/BT310: adapter 用开度作 flow_char, 库中为 "Inherent Character"
    "BT110": {"60°": "Inherent Character", "90°": "Inherent Character"},
    "BT310": {"60°": "Inherent Character", "90°": "Inherent Character"},
    # BV130: 库中为 "ON-OFF"
    "BV130": {"Inherent Character": "ON-OFF"},
    # GC120/GC210/GV120: adapter 的 "Md EQ%"(修正等百分比) 在库中以
    # flow_char="EQ%" + 特殊 trim_type 存储 (见 MODIFIED_FLOW_TRIM_TYPE)
    "GC120": {"Md EQ%": "EQ%"},
    "GC210": {"Md EQ%": "EQ%"},
    "GV120": {"Md EQ%": "EQ%"},
    # GV110/GZ810: 库中为 "Linear"
    "GV110": {"EQ%": "Linear"},
    "GZ810": {"EQ%": "Linear"},
}

# "Md EQ%" 行的 flow_char 归一化为 EQ% 后, trim_type 联动改写为库中取值
MODIFIED_FLOW_TRIM_TYPE = {
    "GC120": "Large Cv",
    "GC210": "Modified",
    "GV120": "Large Cv",
}

# dn_label 标准化映射 (None 值的处理)
DN_LABEL_NORMALIZE = {
    # GZ810: adapter 无 dn, 库中全为 15A
    "GZ810": {None: "15A"},
}

# GZ800 系列共用同一 adapter 与同一套库命名约定, GZ820~GZ860 沿用 GZ810 规则
for _gz_code in ("GZ820", "GZ830", "GZ840", "GZ850", "GZ860"):
    SERIES_KEY_STRATEGY[_gz_code] = SERIES_KEY_STRATEGY["GZ810"]
    TRIM_TYPE_NORMALIZE[_gz_code] = {"Downstream": "Standard"}
    FLOW_CHAR_NORMALIZE[_gz_code] = {"EQ%": "Linear"}
    DN_LABEL_NORMALIZE[_gz_code] = {None: "15A"}


def normalize_adapter_row(series_code: str, row: Dict[str, Any]) -> Dict[str, Any]:
    """标准化 adapter 行, 使其与库中命名约定一致

    比对 (compare_cv_data) 与入库 (import_validated_data) 共用同一套归一化,
    保证 upsert 匹配键与比对键一致。

    包含:
    - trim_type / flow_char / dn_label 字段级映射
    - GC120/GC210/GV120: adapter "Md EQ%" 行在库中以 EQ% + Large Cv/Modified 存储,
      flow_char 归一化后联动改写 trim_type
    - BT110 特殊处理: 15 Deg Sealed 的 90° 开度 Cv 与库中 75° 为同一数据点
      (15° 密封蝶阀最大开度 75°), stroke_value 90 → 75
    """
    r = dict(row)

    # 记录归一化前的 flow_char, 供 Md EQ% 联动改写使用
    original_flow_char = r.get("flow_char")

    if r.get("trim_type") is not None:
        r["trim_type"] = TRIM_TYPE_NORMALIZE.get(series_code, {}).get(r["trim_type"], r["trim_type"])

    if r.get("flow_char") is not None:
        r["flow_char"] = FLOW_CHAR_NORMALIZE.get(series_code, {}).get(r["flow_char"], r["flow_char"])

    # Md EQ% → EQ% + 库中对应 trim_type (须在字段级映射之后执行)
    if original_flow_char == "Md EQ%" and series_code in MODIFIED_FLOW_TRIM_TYPE:
        r["trim_type"] = MODIFIED_FLOW_TRIM_TYPE[series_code]

    dn_map = DN_LABEL_NORMALIZE.get(series_code, {})
    if r.get("dn_label") in dn_map:
        r["dn_label"] = dn_map[r.get("dn_label")]

    # BT110: 15 Deg Sealed 90° → 库中 75°
    if series_code == "BT110" and r.get("seat_type") == "15 Deg Sealed" and r.get("stroke_value") == 90.0:
        r["stroke_value"] = 75.0

    # GV110: adapter 按阀规格给 trim_label (1A), plug_mm=1.6 的内件在库中记为 1.6A
    if series_code == "GV110" and r.get("trim_label") == "1A" and r.get("plug_mm") == 1.6:
        r["trim_label"] = "1.6A"

    return r


def get_key_fields(series_code: str) -> List[str]:
    """获取指定系列的匹配键字段"""
    return SERIES_KEY_STRATEGY.get(series_code, ["series_code", "dn_label", "trim_label", "flow_char"])


def normalize_trim_type(series_code: str, trim_type: str) -> str:
    """标准化 trim_type"""
    mapping = TRIM_TYPE_NORMALIZE.get(series_code, {})
    return mapping.get(trim_type, trim_type)


def make_key(row: Dict[str, Any], fields: List[str] = None) -> str:
    """生成复合键"""
    if fields is None:
        fields = KEY_FIELDS
    parts = []
    for field in fields:
        val = row.get(field)
        parts.append(str(val) if val is not None else "")
    return "|".join(parts)


def load_db_data() -> Dict[str, List[Dict[str, Any]]]:
    """从数据库加载 valve_cv_stk 数据"""
    db = SessionLocal()
    try:
        records = db.query(ValveCvStk).all()
        # 按 series_code 分组
        by_series = defaultdict(list)
        for r in records:
            row = {
                "id": r.id,
                "series_code": r.series_code,
                "dn_label": r.dn_label,
                "trim_label": r.trim_label,
                "flow_char": r.flow_char,
                "trim_type": r.trim_type,
                "pressure_rating": r.pressure_rating,
                "seat_type": r.seat_type,
                "rated_cv": r.rated_cv,
                "stroke_unit": r.stroke_unit,
                "stroke_value": r.stroke_value,
                "plug_mm": r.plug_mm,
                "cv_min": getattr(r, "cv_min", None),
                "stk_index": r.stk_index,
                "kfd": r.kfd,
                "kfo": r.kfo,
                "kfb": r.kfb,
            }
            by_series[r.series_code].append(row)
        return dict(by_series)
    finally:
        db.close()


def compare_rows(adapter_row: Dict[str, Any], db_row: Dict[str, Any]) -> Tuple[str, float, str]:
    """比对两行数据，返回 (状态, 差异百分比, 说明)

    状态:
    - match: 一致 (差异 ≤ 5%)
    - diff: 差异 (差异 > 5%)
    - missing_in_db: 库中无记录 (新增)
    - missing_in_adapter: adapter 无记录 (库中多余)
    """
    # 比对 rated_cv
    adapter_cv = adapter_row.get("rated_cv")
    db_cv = db_row.get("rated_cv")

    if adapter_cv is None and db_cv is None:
        return "match", 0.0, "both cv null"

    if adapter_cv is None:
        return "diff", 100.0, f"adapter cv null, db cv={db_cv}"

    if db_cv is None:
        return "diff", 100.0, f"adapter cv={adapter_cv}, db cv null"

    # 计算差异百分比
    diff_pct = abs(adapter_cv - db_cv) / max(abs(db_cv), 0.001) * 100

    if diff_pct > 5:
        return "diff", diff_pct, f"cv diff {diff_pct:.1f}%: adapter={adapter_cv}, db={db_cv}"
    else:
        return "match", diff_pct, f"cv diff {diff_pct:.1f}%"


def compare_series(series_code: str, db_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """比对单个系列，返回比对结果"""
    print(f"\n{'='*60}")
    print(f"Comparing {series_code}")
    print('='*60)

    # 加载 adapter 数据
    try:
        adapter = get_adapter(series_code)
        # 一个 adapter 类可注册多个系列 (如 GZ810/820/.../860 共用),
        # parse_rated_cv 可能返回全部系列的行, 这里只保留当前系列
        adapter_rows = [r for r in adapter.parse_rated_cv()
                        if r.get("series_code") == series_code]
    except Exception as e:
        print(f"ERROR loading adapter: {e}")
        return {"error": str(e)}

    # 加载库中数据
    db_rows = db_data.get(series_code, [])

    print(f"Adapter rows: {len(adapter_rows)}")
    print(f"DB rows: {len(db_rows)}")

    # 获取该系列的匹配键字段
    key_fields = get_key_fields(series_code)

    # 建立索引（使用基于系列的匹配键策略）
    # 对 adapter 数据进行字段标准化 (trim_type/flow_char/dn_label/stroke_value)
    # 正确复合键下不应再出现同键多行; 若出现说明键仍不完整, 记录到 key_warnings
    adapter_index = {}
    key_warnings = []
    for r in adapter_rows:
        r_normalized = normalize_adapter_row(series_code, r)
        key = make_key(r_normalized, key_fields)
        if key not in adapter_index:
            adapter_index[key] = r_normalized
        else:
            existing = adapter_index[key]
            if existing.get("rated_cv") == r_normalized.get("rated_cv"):
                # 同键同 Cv: 良性别名重复 (如 GV110 多个 dn 共享同一 trim 行), 保留首个即可
                continue
            key_warnings.append(
                f"adapter 复合键重复(键可能不完整): {key} | cv={existing.get('rated_cv')} "
                f"与 cv={r_normalized.get('rated_cv')}"
            )
            # 兜底: 用 rated_cv 附加区分, 保证两行都参与比对
            key_with_cv = f"{key}|cv={r_normalized.get('rated_cv')}"
            adapter_index[key_with_cv] = r_normalized

    db_index = {}
    for r in db_rows:
        key = make_key(r, key_fields)
        if key not in db_index:
            db_index[key] = r
        else:
            existing = db_index[key]
            if existing.get("rated_cv") == r.get("rated_cv"):
                # 同键同 Cv: 良性别名重复 (如 GV110 键不含 dn, 15A/20A/25A 折叠为同一行)
                continue
            key_warnings.append(
                f"库中复合键重复(键可能不完整): {key} | cv={existing.get('rated_cv')} "
                f"与 cv={r.get('rated_cv')}"
            )
            key_with_cv = f"{key}|cv={r.get('rated_cv')}"
            db_index[key_with_cv] = r

    print(f"Unique adapter keys: {len(adapter_index)}")
    print(f"Unique DB keys: {len(db_index)}")
    if key_warnings:
        print(f"WARNING: {len(key_warnings)} 个复合键冲突, 请检查键策略是否完整")
        for w in key_warnings:
            print(f"  - {w}")

    # 比对结果
    results = {
        "series_code": series_code,
        "adapter_count": len(adapter_rows),
        "db_count": len(db_rows),
        "key_fields": key_fields,
        "key_warnings": key_warnings,
        "match": [],  # 一致
        "diff": [],   # 差异 > 5%
        "new": [],    # 库中无记录 (新增)
        "removed": [],  # adapter 无记录 (库中多余)
    }

    # 检查 adapter 中的行
    for key, adapter_row in adapter_index.items():
        if key in db_index:
            db_row = db_index[key]
            status, diff_pct, note = compare_rows(adapter_row, db_row)
            result = {
                "key": key,
                "adapter_row": adapter_row,
                "db_row": db_row,
                "status": status,
                "diff_pct": diff_pct,
                "note": note,
            }
            if status == "match":
                results["match"].append(result)
            else:
                results["diff"].append(result)
        else:
            results["new"].append({
                "key": key,
                "adapter_row": adapter_row,
                "status": "new",
                "note": "库中无记录",
            })

    # 检查库中多余的行
    for key, db_row in db_index.items():
        if key not in adapter_index:
            results["removed"].append({
                "key": key,
                "db_row": db_row,
                "status": "removed",
                "note": "adapter 无记录",
            })

    print(f"Match: {len(results['match'])}")
    print(f"Diff: {len(results['diff'])}")
    print(f"New: {len(results['new'])}")
    print(f"Removed: {len(results['removed'])}")

    return results


# 报告章节标题前缀 (用于沿用上版报告中的人工批注 ——...)
SECTION_PREFIXES = {
    "diff": "## 差异行 (>5%)",
    "new": "## 新增行 (库中无记录)",
    "removed": "## 库中多余行 (adapter 无记录)",
}


def load_previous_notes(report_path: Path) -> Dict[str, str]:
    """读取上版报告章节标题中 "——" 之后的人工批注

    重新生成报告会覆盖文件, 这里先把人工结论 (如 ——入库 / ——保留) 提取出来,
    由 generate_report 追加到对应章节标题后, 标注来源为「上版人工标注」。
    """
    import re
    notes: Dict[str, str] = {}
    if not report_path.exists():
        return notes
    text = report_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.startswith("## "):
            continue
        title = line[3:].strip()
        for key, prefix in SECTION_PREFIXES.items():
            # prefix 含 "## " 前缀, title 已去掉该前缀
            if title.startswith(prefix[3:]):
                m = re.search(r"——\s*(.+?)\s*$", title)
                if m:
                    note = m.group(1).replace("（上版人工标注）", "").strip()
                    # 去掉 markdown 转义符 (如 trim\_type)
                    note = note.replace("\\", "")
                    notes[key] = note
    return notes


def generate_report(results: Dict[str, Any], output_dir: Path):
    """生成差异报告"""
    series_code = results["series_code"]
    report_path = output_dir / f"{series_code}_diff.md"

    # 提取上版人工批注, 重新生成时沿用
    previous_notes = load_previous_notes(report_path)

    def section_title(key: str, prefix: str) -> str:
        note = previous_notes.get(key)
        if note:
            return f"{prefix}——{note}（上版人工标注）\n\n"
        return f"{prefix}\n\n"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# {series_code} 数据比对报告\n\n")
        f.write(f"生成时间: {__import__('datetime').datetime.now()}\n\n")

        f.write("## 统计\n\n")
        f.write(f"- Adapter 行数: {results['adapter_count']}\n")
        f.write(f"- 库中行数: {results['db_count']}\n")
        f.write(f"- 复合键字段: {', '.join(results.get('key_fields', []))}\n")
        f.write(f"- 一致: {len(results['match'])}\n")
        f.write(f"- 差异 (>5%): {len(results['diff'])}\n")
        f.write(f"- 新增: {len(results['new'])}\n")
        f.write(f"- 库中多余: {len(results['removed'])}\n\n")

        if results.get("key_warnings"):
            f.write("## 复合键冲突告警 (同一复合键出现多行, 说明键仍不完整)\n\n")
            for w in results["key_warnings"]:
                f.write(f"- {w}\n")
            f.write("\n")

        if results["diff"]:
            f.write(section_title("diff", SECTION_PREFIXES["diff"]))
            f.write("| 复合键 | Adapter Cv | 库中 Cv | 差异% | 说明 |\n")
            f.write("|---|---|---|---|---|\n")
            for r in results["diff"]:
                f.write(f"| {r['key']} | {r['adapter_row'].get('rated_cv')} | {r['db_row'].get('rated_cv')} | {r['diff_pct']:.1f}% | {r['note']} |\n")
            f.write("\n")

        if results["new"]:
            f.write(section_title("new", SECTION_PREFIXES["new"]))
            f.write("| 复合键 | Adapter Cv | 说明 |\n")
            f.write("|---|---|---|\n")
            for r in results["new"]:
                f.write(f"| {r['key']} | {r['adapter_row'].get('rated_cv')} | {r['note']} |\n")
            f.write("\n")

        if results["removed"]:
            f.write(section_title("removed", SECTION_PREFIXES["removed"]))
            f.write("| 复合键 | 库中 Cv | 说明 |\n")
            f.write("|---|---|---|\n")
            for r in results["removed"]:
                f.write(f"| {r['key']} | {r['db_row'].get('rated_cv')} | {r['note']} |\n")
            f.write("\n")

    print(f"Report saved: {report_path}")


def generate_summary(all_results: List[Dict[str, Any]], output_dir: Path):
    """生成汇总报告"""
    summary_path = output_dir / "summary.md"

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# 数据比对汇总报告\n\n")
        f.write(f"生成时间: {__import__('datetime').datetime.now()}\n\n")

        f.write("## 总体统计\n\n")
        f.write("| 系列 | Adapter 行数 | 库中行数 | 一致 | 差异 | 新增 | 库中多余 | 键冲突 |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")

        total_match = 0
        total_diff = 0
        total_new = 0
        total_removed = 0
        total_warnings = 0

        for r in all_results:
            if "error" in r:
                f.write(f"| {r.get('series_code', 'ERROR')} | - | - | - | - | - | ERROR | - |\n")
                continue
            n_warn = len(r.get("key_warnings", []))
            f.write(f"| {r['series_code']} | {r['adapter_count']} | {r['db_count']} | {len(r['match'])} | {len(r['diff'])} | {len(r['new'])} | {len(r['removed'])} | {n_warn} |\n")
            total_match += len(r['match'])
            total_diff += len(r['diff'])
            total_new += len(r['new'])
            total_removed += len(r['removed'])
            total_warnings += n_warn

        f.write(f"| **合计** | - | - | **{total_match}** | **{total_diff}** | **{total_new}** | **{total_removed}** | **{total_warnings}** |\n\n")

    print(f"Summary saved: {summary_path}")


def main():
    # 输出目录
    output_dir = Path(__file__).parent.parent / "docs" / "数据比对报告"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 加载库中数据
    print("Loading database data...")
    db_data = load_db_data()
    print(f"Loaded {sum(len(v) for v in db_data.values())} rows from {len(db_data)} series")

    # 逐系列比对: 固定主顺序, 并自动纳入注册表中新增的系列 (如 GZ820~GZ860)
    preferred = ["GC120", "GC210", "GC320", "GV120", "BT210", "BV210", "GA510",
                 "GV110", "GV130", "BT110", "BT310", "BV130", "GZ810"]
    registered = list_registered_series()
    series_list = preferred + [s for s in registered if s not in preferred]

    all_results = []
    for series_code in series_list:
        try:
            results = compare_series(series_code, db_data)
            if "error" not in results:
                generate_report(results, output_dir)
            all_results.append(results)
        except Exception as e:
            print(f"ERROR comparing {series_code}: {e}")
            import traceback
            traceback.print_exc()
            all_results.append({"series_code": series_code, "error": str(e)})

    # 生成汇总报告
    generate_summary(all_results, output_dir)

    print("\n" + "="*60)
    print("Comparison complete!")
    print("="*60)


if __name__ == "__main__":
    main()
