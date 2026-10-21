"""KELK 阀门产品系列字典接口"""
import json
import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import ValveType, ValveFactorCurve, ValveTrimSize, ValvePlugIndexMap, ValveSeriesCurveConfig, ValveFilterConfig, ValveCvStk, NominalSizeRef
from app.schemas import ValveTypeOut, ValveCvStkOut

router = APIRouter(prefix="/valve-types", tags=["阀门产品系列"])

# 系列曲线别名: 缺少 ValveSeriesCurveConfig / ValvePlugIndexMap 数据的系列,
# 使用对应的源系列数据 (ValveCvStk 各自独立, 不走别名)
SERIES_CURVE_ALIAS = {
    'BC120': 'BC110',   # BC120 (法兰式) 使用 BC110 (对夹式) 的曲线映射
    'BE110': 'BE120',   # BE110 (对夹式) 使用 BE120 (法兰式) 的曲线映射
    'GV130': 'GV120',   # GV130 (平衡型) 使用 GV120 的曲线映射
}


def _resolve_curve_alias(series_code: str) -> str:
    """返回该系列曲线映射数据所在的源系列 code (无别名时原样返回)"""
    return SERIES_CURVE_ALIAS.get(series_code, series_code)


def _get_cfg(series_code: str, pressure_rating: str, db: Session):
    """按 series_code + pressure_rating 查 ValveSeriesCurveConfig。
    优先精确匹配 (series + rating)，找不到则取该系列任意一条配置
    (细化型号如 GC120H 只有一条 pressure_rating 固定的配置)。
    支持别名: 缺少配置的系列自动回退到别名系列 (如 BC120→BC110)。"""
    src = _resolve_curve_alias(series_code)
    cfg = None
    for sc in (series_code, src):
        if pressure_rating:
            cfg = db.query(ValveSeriesCurveConfig).filter(
                ValveSeriesCurveConfig.series_code == sc,
                ValveSeriesCurveConfig.pressure_rating == pressure_rating
            ).first()
        if not cfg:
            cfg = db.query(ValveSeriesCurveConfig).filter(
                ValveSeriesCurveConfig.series_code == sc,
                ValveSeriesCurveConfig.pressure_rating.is_(None)
            ).first()
        if not cfg:
            cfg = db.query(ValveSeriesCurveConfig).filter(
                ValveSeriesCurveConfig.series_code == sc
            ).first()
        if cfg:
            break
    return cfg


# 蝶阀/球阀系列: 用 dn_mm 作尺寸匹配 (无 plug_mm)
_DN_MATCH_SERIES = ('BT110', 'BT120', 'BT210', 'BC110', 'BC120', 'BE110', 'BE120')


def _mm_to_jis_a(dn_mm, db: Session):
    """将 dn_mm 数值转为 JIS A 标签 (如 40 → '40A')，优先查 NominalSizeRef 表"""
    if not dn_mm:
        return None
    ns = db.query(NominalSizeRef).filter(NominalSizeRef.dn_mm == float(dn_mm)).first()
    if ns and ns.jis_a:
        return ns.jis_a
    # 兜底: 直接拼 "XA"
    try:
        return f"{int(round(float(dn_mm)))}A"
    except (ValueError, TypeError):
        return None


def _inch_to_jis_a(nps_in: str, db: Session):
    """将英制公称尺寸 (如 '1 1/2') 转为 JIS A 标签 (如 '40A')，查 NominalSizeRef 表"""
    if not nps_in:
        return None
    ns = db.query(NominalSizeRef).filter(NominalSizeRef.nps_in == str(nps_in).strip()).first()
    if ns and ns.jis_a:
        return ns.jis_a
    # 兜底: 尝试用小数匹配
    try:
        parts = str(nps_in).split()
        total = 0.0
        for p in parts:
            if '/' in p:
                num, den = p.split('/')
                total += float(num) / float(den)
            else:
                total += float(p)
        ns2 = db.query(NominalSizeRef).filter(NominalSizeRef.nps_in_decimal == total).first()
        if ns2 and ns2.jis_a:
            return ns2.jis_a
    except (ValueError, TypeError):
        pass
    return None


def _map_trim_seat_to_cvstk_trim_type(trim_seat_type: str):
    """将 curves-by-selection 的 trim_seat_type 映射到 valve_cv_stk.trim_type
    
    例如: 'Standard P-port' → 'Standard', 'Large Cv P-port' → 'Large Cv', 'On/Off Q-port' → 'ON-OFF'
          '40% Red' → '40% Red' (BE120), '60% Red' → '60% Red' (BE120), 'Full' → 'Full' (BE120)
    """
    if not trim_seat_type:
        return None
    tts = trim_seat_type.strip()
    # BE120 / BC110 / BC120: Bore Type 直接存为 trim_type
    if tts in ('40% Red', '60% Red', 'Full', 'Standard'):
        return tts
    tts_lower = tts.lower()
    if 'large' in tts_lower:
        return 'Large Cv'
    if 'on/off' in tts_lower or 'on-off' in tts_lower or 'q-port' in tts_lower:
        return 'ON-OFF'
    if 'standard' in tts_lower or 'p-port' in tts_lower:
        return 'Standard'
    return None


def _parse_nominal_dn(val: str, db: Session):
    """解析 nominal_dn 参数，返回 (dn_label, dn_mm)

    支持格式:
      - "40A" → ("40A", None)  — 已为 JIS A，mm 需从 NominalSizeRef 查
      - "40"  → ("40A", 40.0)
      - "" / None / "0" → (None, None)
    """
    if not val or val in ('0', 'None', 'null'):
        return None, None
    val = str(val).strip()
    # 已经是 JIS A 格式 (如 "40A")
    if val.endswith('A') and len(val) > 1:
        # 尝试从 NominalSizeRef 查 mm
        ns = db.query(NominalSizeRef).filter(NominalSizeRef.jis_a == val).first()
        dn_mm = float(ns.dn_mm) if ns and ns.dn_mm else None
        return val, dn_mm
    # 尝试当数值解析
    try:
        mm = float(val)
        jis_a = _mm_to_jis_a(mm, db)
        return jis_a, mm
    except (ValueError, TypeError):
        return val, None


def _parse_nominal_trim(val: str, db: Session):
    """解析 nominal_trim 参数，返回 trim_label

    支持格式:
      - "25A" → "25A"
      - "1 1/2" → 经 NominalSizeRef 转 JIS A
      - "" / None → None
    """
    if not val:
        return None
    val = str(val).strip()
    # 已经是 JIS A 格式
    if val.endswith('A') and len(val) > 1:
        return val
    # 尝试当 inch 格式解析
    return _inch_to_jis_a(val, db)


def _query_cv_stk_rated_cv(
    series_code: str,
    pressure_rating: str,
    plug_size: float,
    nominal_dn: str,
    nominal_trim: str,
    trim_type: str,
    trim_seat_type: str,
    db: Session,
    seat_type: str = "",
    trim_characteristics: str = "",
    opening_angle_val: int = None,
):
    """从 valve_cv_stk 表查询 rated_cv 和 stroke_value

    返回 (rated_cv, stroke_value, stroke_unit) 或 (None, None, None)

    约束条件映射:
      - dn_label: 从 nominal_dn (支持 "40A" 或 "40") 或 plug_size (DN 型系列) 推导
      - plug_mm: 直接用 plug_size 数值匹配 (有 plug_mm 字段的行)
      - trim_label: 用 nominal_trim (支持 "25A" 或 "1 1/2") 推导; 兜底从 plug_size (mm) 转 "XA"
      - flow_char: trim_characteristics 参数 (EQ%/Linear), 或 trim_type 为 ON-OFF 时
      - trim_type: trim_seat_type/trim_type 经映射 (Standard/Large Cv/ON-OFF)
      - pressure_rating: 精确匹配优先，None 兜底
      - stroke_value: opening_angle_val 过滤 (BT 系列 60/75/90 度对应不同 stroke_value)
    """
    mapped_tt = _map_trim_seat_to_cvstk_trim_type(trim_seat_type)
    # GV120 等系列: trim_type 直接来自前端 (如 "Large Cv"), 与 valve_cv_stk.trim_type 一致
    if not mapped_tt and trim_type:
        mapped_tt = _map_trim_seat_to_cvstk_trim_type(trim_type) or trim_type
    # flow_char 优先用 trim_characteristics (EQ%/Linear), ON-OFF 时用 trim_type
    if mapped_tt == 'ON-OFF':
        flow_char_val = 'ON-OFF'
    elif trim_characteristics:
        flow_char_val = trim_characteristics
    else:
        flow_char_val = trim_type

    # dn_label — 优先用 nominal_dn 解析，兜底从 plug_size 推导
    dn_label = None
    if nominal_dn:
        dn_label, _ = _parse_nominal_dn(nominal_dn, db)
    elif plug_size and (series_code.startswith(_DN_MATCH_SERIES)):
        dn_label = _mm_to_jis_a(plug_size, db)

    # trim_label — 优先用 nominal_trim 解析 (支持 "25A" 或 "1 1/2")
    trim_label = None
    if nominal_trim:
        trim_label = _parse_nominal_trim(nominal_trim, db)
    if not trim_label and plug_size:
        try:
            trim_label = f"{int(round(float(plug_size)))}A"
        except (ValueError, TypeError):
            pass

    # BT 系列: opening_angle → stroke_value (60→60, 75→75, 90→90)
    stroke_value_val = float(opening_angle_val) if opening_angle_val else None

    def _apply_stroke_filter(q):
        """统一在 query 上加 stroke_value 过滤 (如果有 opening_angle)"""
        if stroke_value_val is not None:
            # 精确匹配 OR 无 stroke_value 的行 (兼容其他系列)
            q = q.filter(
                (ValveCvStk.stroke_value == stroke_value_val) |
                (ValveCvStk.stroke_value.is_(None))
            )
        return q

    def _build_query():
        q = db.query(ValveCvStk).filter(ValveCvStk.series_code == series_code)
        if dn_label:
            q = q.filter(ValveCvStk.dn_label == dn_label)
        if seat_type:
            q = q.filter(ValveCvStk.seat_type == seat_type)
        if flow_char_val and flow_char_val in ('EQ%', 'Linear', 'ON-OFF'):
            q = q.filter(
                (ValveCvStk.flow_char == flow_char_val) |
                (ValveCvStk.flow_char.is_(None))
            )
        if mapped_tt:
            q = q.filter(ValveCvStk.trim_type == mapped_tt)
        return q

    # ========== 查询策略 (严格按精确性从高到低) ==========
    # 关键 insight: 对于 GV120 Large Cv / GC120 等系列，额定 Cv 只由阀芯尺寸 (plug_mm) 决定，
    # 与口径 (dn_label) 无关 (DN 和 Trim 是 1:1 绑定的)。
    # Standard 系列允许缩径 (同一 DN 配多种阀芯), 但同一 plug_mm 在不同 DN 下 Cv 相同。
    # 所以 plug_mm + trim_type 的组合优先级应该高于 dn_label！

    # 策略 0: plug_mm + trim_type + flow_char
    if plug_size and mapped_tt:
        q0 = db.query(ValveCvStk).filter(
            ValveCvStk.series_code == series_code,
            ValveCvStk.plug_mm == float(plug_size),
            ValveCvStk.trim_type == mapped_tt,
        )
        if flow_char_val and flow_char_val in ('EQ%', 'Linear', 'ON-OFF'):
            q0 = q0.filter(
                (ValveCvStk.flow_char == flow_char_val) |
                (ValveCvStk.flow_char.is_(None))
            )
        q0 = _apply_stroke_filter(q0)
        row = q0.first()
        if row:
            return row.rated_cv, row.stroke_value, row.stroke_unit

    # 策略 1: plug_mm + trim_type
    if plug_size and mapped_tt:
        q1 = db.query(ValveCvStk).filter(
            ValveCvStk.series_code == series_code,
            ValveCvStk.plug_mm == float(plug_size),
            ValveCvStk.trim_type == mapped_tt,
        )
        q1 = _apply_stroke_filter(q1)
        row = q1.first()
        if row:
            return row.rated_cv, row.stroke_value, row.stroke_unit

    # 策略 2: dn_label + trim_type + plug_size
    if dn_label and mapped_tt and plug_size:
        q2 = db.query(ValveCvStk).filter(
            ValveCvStk.series_code == series_code,
            ValveCvStk.dn_label == dn_label,
            ValveCvStk.trim_type == mapped_tt,
            ValveCvStk.plug_mm == float(plug_size),
        )
        q2 = _apply_stroke_filter(q2)
        row = q2.first()
        if row:
            return row.rated_cv, row.stroke_value, row.stroke_unit

    # 策略 3: DN 型系列兜底 — 无 plug_mm 的系列 (BE120/BC110/BT 等)
    if dn_label and (seat_type or mapped_tt):
        q3 = db.query(ValveCvStk).filter(
            ValveCvStk.series_code == series_code,
            ValveCvStk.dn_label == dn_label,
        )
        if seat_type:
            q3 = q3.filter(ValveCvStk.seat_type == seat_type)
        if mapped_tt:
            q3 = q3.filter(ValveCvStk.trim_type == mapped_tt)
        q3 = _apply_stroke_filter(q3)
        row = q3.first()
        if row:
            return row.rated_cv, row.stroke_value, row.stroke_unit

    # 策略 4: trim_label + plug_size + trim_type
    if trim_label and plug_size and mapped_tt:
        q4 = db.query(ValveCvStk).filter(
            ValveCvStk.series_code == series_code,
            ValveCvStk.trim_label == trim_label,
            ValveCvStk.plug_mm == float(plug_size),
            ValveCvStk.trim_type == mapped_tt,
        )
        q4 = _apply_stroke_filter(q4)
        row = q4.first()
        if row:
            return row.rated_cv, row.stroke_value, row.stroke_unit

    # 策略 5: trim_label + trim_type
    if trim_label and mapped_tt:
        q5 = db.query(ValveCvStk).filter(
            ValveCvStk.series_code == series_code,
            ValveCvStk.trim_label == trim_label,
            ValveCvStk.trim_type == mapped_tt,
        )
        q5 = _apply_stroke_filter(q5)
        row = q5.first()
        if row:
            return row.rated_cv, row.stroke_value, row.stroke_unit

    # 策略 6: dn_label + trim_label (DN 型系列兜底: BC110/BC120/BE110/BE120 等)
    # 这些系列 plug_mm=None 且 trim_type 可能是 'Full' 而非前端传的 'Standard'
    if dn_label and trim_label:
        q6 = db.query(ValveCvStk).filter(
            ValveCvStk.series_code == series_code,
            ValveCvStk.dn_label == dn_label,
            ValveCvStk.trim_label == trim_label,
        )
        if flow_char_val and flow_char_val in ('EQ%', 'Linear', 'ON-OFF'):
            q6 = q6.filter(
                (ValveCvStk.flow_char == flow_char_val) |
                (ValveCvStk.flow_char.is_(None))
            )
        row = q6.first()
        if row:
            return row.rated_cv, row.stroke_value, row.stroke_unit

    return None, None, None


# KELK 产品系列种子数据
SEED_VALVE_TYPES = [
    # Globe Valves — 套筒/柱塞调节阀
    {"series_code": "GC120", "series_name": "套筒导向型单座调节阀", "valve_category": "globe", "product_line": "调节阀",
     "description": "压力平衡阀芯，大容量动态稳定性优良，适合苛刻工况。DN25~DN500", "sort_order": 1},
    {"series_code": "GC210", "series_name": "多孔式套筒导向型单座调节阀", "valve_category": "globe", "product_line": "调节阀",
     "description": "多孔式套筒内件，降低出口流速防止空化气蚀，有效降低噪音。DN25~DN500", "sort_order": 2},
    {"series_code": "GC320", "series_name": "多级降压式套筒导向型调节阀", "valve_category": "globe", "product_line": "调节阀",
     "description": "多级降压结构，适用于高压差工况，防止空化和闪蒸。", "sort_order": 3},
    {"series_code": "GV130", "series_name": "顶部导向型单座调节阀（平衡型）", "valve_category": "globe", "product_line": "调节阀",
     "description": "顶部导向结构，平衡型阀芯，适用于一般工况调节。", "sort_order": 4},
    {"series_code": "GA510", "series_name": "低温铝角阀", "valve_category": "globe", "product_line": "调节阀",
     "description": "深冷场合使用，最低-196°C，适用于液氮、液氧、液空等液化气体。DN20~DN200", "sort_order": 5},
    # Ball Valves — 球阀
    {"series_code": "BC110", "series_name": "V型调节球阀（对夹式）", "valve_category": "ball", "product_line": "球阀",
     "description": "V型切口球板，具有剪切功能，适用于含纤维质、浆料类流体。DN25~DN300", "sort_order": 10},
    {"series_code": "BC120", "series_name": "V型调节球阀（法兰式）", "valve_category": "ball", "product_line": "球阀",
     "description": "V型切口球板，法兰连接，适用于含纤维质、浆料类流体。DN25~DN300", "sort_order": 11},
    {"series_code": "BV110", "series_name": "软密封直通球阀", "valve_category": "ball", "product_line": "球阀",
     "description": "软密封球阀，适用于一般介质开关及调节。DN15~DN300", "sort_order": 12},
    {"series_code": "BV210", "series_name": "金属硬密封球阀", "valve_category": "ball", "product_line": "球阀",
     "description": "金属硬密封，耐高温高压，最高538°C，适用于高温蒸汽等工况。DN15~DN600", "sort_order": 13},
    {"series_code": "BV420", "series_name": "耐酸球阀", "valve_category": "ball", "product_line": "球阀",
     "description": "耐腐蚀球阀，适用于强腐蚀性化学介质。", "sort_order": 14},
    # Butterfly Valves — 蝶阀
    {"series_code": "BT110", "series_name": "低负载轻型蝶阀", "valve_category": "butterfly", "product_line": "蝶阀",
     "description": "钢板焊接结构，重量轻，适用于低压空气或气体流量压力控制。", "sort_order": 20},
    {"series_code": "BT210", "series_name": "高性能双偏心蝶阀", "valve_category": "butterfly", "product_line": "蝶阀",
     "description": "双偏心结构，高性能密封，适用于一般工业工况调节。", "sort_order": 21},
    {"series_code": "BT310", "series_name": "低负载三偏心蝶阀", "valve_category": "butterfly", "product_line": "蝶阀",
     "description": "三偏心硬密封结构，越关越紧，适用于高温、高压工况。", "sort_order": 22},
]


def seed_valve_types(db):
    """启动时若表为空则注入 KELK 产品系列种子数据"""
    if db.query(ValveType).count() == 0:
        for item in SEED_VALVE_TYPES:
            db.add(ValveType(**item))
        db.commit()


def seed_valve_filter_config(db: Session):
    """启动时对 valve_cv_stk 有数据的系列插入/更新 ValveFilterConfig 行 (upsert by series_code+filter_key)

    筛选器标签统一中文，选项按系列特性定制。
    """
    import json as _json

    # 从 valve_cv_stk 检测有数据的系列
    cvstk_series = [r[0] for r in db.query(ValveCvStk.series_code).distinct().all()]

    # 通用筛选器模板 (默认 GV/GC 系列)
    # 统一排序: 阀门口径 → 阀芯尺寸 → 阀内件形式 → 流量特性 → 压力等级 → 流向 → 阀座形式
    BASE_CONFIGS = [
        # (filter_key, display_label, filter_order, is_enabled, option_source, hardcoded_options, default_value, dependent_on, value_field)
        ("nominal_dn",           "阀门口径",    10, True,  "cascade",  None, None, None,                            "dn_label"),
        ("nominal_trim",         "阀芯尺寸",    20, True,  "cascade",  None, None, "nominal_dn",                    "trim_label"),
        ("trim_type",            "阀内件形式",  30, True,  "data",     None, None, None,                            "trim_type"),
        ("trim_characteristics", "流量特性",    40, True,  "data",     None, None, None,                            "flow_char"),
        ("pressure_rating",      "压力等级",    50, True,  "cascade",  None, None, None,                            "pressure_rating"),
        ("flow_direction",       "流向",        60, True,  "hardcoded", _json.dumps(["FTC", "FTO"]), "FTC", None, None),
    ]

    # 蝶阀 BT 系列配置 (开启角度移到最后，非联筛选条件)
    BT_CONFIGS = [
        ("nominal_dn",           "阀门口径",    10, True,  "cascade",  None, None, None,          "dn_label"),
        ("nominal_trim",         "阀芯尺寸",    20, True,  "cascade",  None, None, "nominal_dn",  "trim_label"),
        ("trim_type",            "阀内件形式",  30, True,  "data",     None, None, None,          "trim_type"),
        ("trim_characteristics", "流量特性",    40, True,  "data",     None, None, None,          "flow_char"),
        ("pressure_rating",      "压力等级",    50, True,  "cascade",  None, None, None,          "pressure_rating"),
        ("seat_type",            "阀座形式",    70, True,  "data",     None, None, None,          "seat_type"),
        ("opening_angle",         "开启角度",    75, True,  "stroke",   None, None, None,          None),
    ]

    # 球阀 BE/BC 系列配置 (含阀座形式)
    BALL_CONFIGS = [
        ("nominal_dn",           "阀门口径",    10, True,  "cascade",  None, None, None, "dn_label"),
        ("trim_type",            "阀内件形式",  30, True,  "data",     None, None, None, "trim_type"),
        ("trim_characteristics", "流量特性",    40, True,  "data",     None, None, None, "flow_char"),
        ("pressure_rating",      "压力等级",    50, True,  "cascade",  None, None, None, "pressure_rating"),
        ("seat_type",            "阀座形式",    70, True,  "data",     None, None, None, "seat_type"),
    ]

    # 其他系列 (BV/GA/GT/GZ) 配置 — 也需要 nominal_trim, 否则 GA/GZ 系列无法唯一确定行
    OTHER_CONFIGS = [
        ("nominal_dn",           "阀门口径",    10, True,  "cascade",  None, None, None,          "dn_label"),
        ("nominal_trim",         "阀芯尺寸",    20, True,  "cascade",  None, None, "nominal_dn",  "trim_label"),
        ("trim_type",            "阀内件形式",  30, True,  "data",     None, None, None,          "trim_type"),
        ("trim_characteristics", "流量特性",    40, True,  "data",     None, None, None,          "flow_char"),
        ("pressure_rating",      "压力等级",    50, True,  "cascade",  None, None, None,          "pressure_rating"),
    ]

    # 各系列特定覆盖 (只覆盖 is_enabled/hardcoded_options/default_value 三个字段)
    # 一个 series_code 的所有 override 项在同一个 list 里
    SERIES_SPECIFIC = {
        # BT120/BT210/BT210D: seat_type 无数据, 禁用
        "BT120": [("seat_type", False, None, None)],
        "BT210": [("seat_type", False, None, None)],
        "BT210D": [("seat_type", False, None, None)],
        # GV120: flow_direction 默认 FTO (与 Excel 一致)
        "GV120": [("flow_direction", None, None, "FTO")],
        # GV120 细化型号: pressure_rating 隐藏, flow_direction 默认 FTO
        "GV120H": [("pressure_rating", False, None, None), ("flow_direction", None, None, "FTO")],
        "GV120HH": [("pressure_rating", False, None, None), ("flow_direction", None, None, "FTO")],
        # GC120/GC210 细化型号: pressure_rating 隐藏
        "GC120H": [("pressure_rating", False, None, None)],
        "GC120HH": [("pressure_rating", False, None, None)],
        "GC210H": [("pressure_rating", False, None, None)],
        "GC210HH": [("pressure_rating", False, None, None)],
    }

    # 系列前缀 → 配置模板
    PREFIX_TO_TEMPLATE = {
        "bt1": BT_CONFIGS, "bt2": BT_CONFIGS,
        "bt3": OTHER_CONFIGS, "bt4": OTHER_CONFIGS,
        "be": BALL_CONFIGS, "bc": BALL_CONFIGS,
        "bv": OTHER_CONFIGS, "ga": OTHER_CONFIGS,
        "gt": OTHER_CONFIGS, "gz": OTHER_CONFIGS,
    }

    def get_templates(sc):
        for prefix, cfg in PREFIX_TO_TEMPLATE.items():
            if sc.lower().startswith(prefix):
                return cfg
        return BASE_CONFIGS

    for sc in cvstk_series:
        # 先删除该系列所有旧配置 (防止残留)
        db.query(ValveFilterConfig).filter(ValveFilterConfig.series_code == sc).delete()

        configs = get_templates(sc)
        vt = db.query(ValveType).filter(ValveType.series_code == sc).first()

        # 应用系列特定覆盖
        sc_overrides = {}
        if sc in SERIES_SPECIFIC:
            for fk, ov_enabled, ov_opts, ov_default in SERIES_SPECIFIC[sc]:
                sc_overrides[fk] = (ov_enabled, ov_opts, ov_default)

        # BT 系列: seat_type 从 valve_type.trim_option_types 取
        seat_type_options = None
        if configs == BT_CONFIGS and vt and vt.trim_option_types:
            opts = [t.strip() for t in vt.trim_option_types.split(',') if t.strip()]
            seat_type_options = _json.dumps([{'code': t, 'label': t} for t in opts])

        for fk, label, order, enabled, source, hardcoded, default, dep_on, val_field in configs:
            # 应用覆盖
            if fk in sc_overrides:
                ov_enabled, ov_opts, ov_default = sc_overrides[fk]
                if ov_enabled is not None: enabled = ov_enabled
                if ov_opts is not None: hardcoded = ov_opts
                if ov_default is not None: default = ov_default

            # BT seat_type 特殊处理
            if fk == 'seat_type' and seat_type_options:
                hardcoded = seat_type_options

            existing = db.query(ValveFilterConfig).filter(
                ValveFilterConfig.series_code == sc,
                ValveFilterConfig.filter_key == fk,
            ).first()
            if existing:
                existing.display_label = label
                existing.filter_order = order
                existing.is_enabled = enabled
                existing.option_source = source
                existing.hardcoded_options = hardcoded
                existing.default_value = default
                existing.dependent_on = dep_on
                existing.value_field = val_field
            else:
                db.add(ValveFilterConfig(
                    series_code=sc, filter_key=fk, display_label=label,
                    filter_order=order, is_enabled=enabled, option_source=source,
                    hardcoded_options=hardcoded, default_value=default,
                    dependent_on=dep_on, value_field=val_field,
                ))
    db.commit()


@router.get("", response_model=list[ValveTypeOut])
def list_valve_types(db: Session = Depends(get_db)):
    """获取所有启用的阀门产品系列（按排序值）"""
    return db.query(ValveType).filter(ValveType.is_active == True).order_by(ValveType.sort_order).all()


@router.get("/{series_code}", response_model=ValveTypeOut)
def get_valve_type(series_code: str, db: Session = Depends(get_db)):
    """按 series_code 查询单个阀门系列详情（含扩展字段）"""
    vt = db.query(ValveType).filter(ValveType.series_code == series_code).first()
    if not vt:
        raise HTTPException(status_code=404, detail=f"阀门系列 {series_code} 不存在")
    return vt


@router.get("/{series_code}/factor-curves")
def get_factor_curves(series_code: str, db: Session = Depends(get_db)):
    """按 series_code 查询默认系数曲线 (eqcv / fl / kc / fd)
    
    从 valve_series_curve_config 读取正确的 FL/Kc/Fd 索引，
    stroke_mode 决定 Stroke Curve 方式。
    """
    cfg = _get_cfg(series_code, "", db)
    if not cfg:
        # 回退: 旧逻辑用 valve_types.eq_index
        vt = db.query(ValveType).filter(ValveType.series_code == series_code).first()
        if not vt:
            raise HTTPException(status_code=404, detail=f"阀门系列 {series_code} 不存在")
        if not vt.eq_index:
            return []
        cols = [c for c in ValveFactorCurve.__table__.columns
                if c.name not in ("created_at", "updated_at")]
        col_names = [c.name for c in cols]
        rows = db.query(*cols).filter(
            ValveFactorCurve.eq_index == vt.eq_index
        ).order_by(ValveFactorCurve.factor_type).all()
        return [dict(zip(col_names, r)) for r in rows]
    
    cols = [c for c in ValveFactorCurve.__table__.columns
            if c.name not in ("created_at", "updated_at")]
    col_names = [c.name for c in cols]
    
    def fetch(factor_type, idx):
        if idx is None:
            return None
        row = db.query(*cols).filter(
            ValveFactorCurve.factor_type == factor_type,
            ValveFactorCurve.eq_index == int(idx)
        ).first()
        return dict(zip(col_names, row)) if row else None
    
    fl = fetch('fl', cfg.fl_eq_index)
    kc = fetch('kc', cfg.kc_eq_index)
    fd = fetch('fd', cfg.fd_eq_index) if cfg.fd_mode == 'table' else None
    
    eqcv = None
    if cfg.stroke_mode == 'eq_index' and cfg.stroke_eq_index:
        eqcv = fetch('eqcv', cfg.stroke_eq_index)
    
    return {
        "series_code": series_code,
        "stroke_mode": cfg.stroke_mode,
        "fl": fl, "kc": kc, "fd": fd, "eqcv": eqcv,
        "fl_eq_index": cfg.fl_eq_index,
        "kc_eq_index": cfg.kc_eq_index,
        "fd_eq_index": cfg.fd_eq_index,
        "fd_mode": cfg.fd_mode,
        "stroke_fstk": cfg.stroke_fstk,
        "stroke_divisor": cfg.stroke_divisor,
    }


def _curve_dict(curve):
    """将 ValveFactorCurve ORM 对象转为 dict"""
    if curve is None:
        return None
    cols = [c for c in ValveFactorCurve.__table__.columns
            if c.name not in ("created_at", "updated_at")]
    return {c.name: getattr(curve, c.name) for c in cols}


@router.get("/{series_code}/curve-options")
def get_curve_options(series_code: str, db: Session = Depends(get_db)):
    return _get_curve_options_impl(series_code, db)


@router.get("/{part1}/{part2}/curve-options")
def get_curve_options_slash(part1: str, part2: str, db: Session = Depends(get_db)):
    """处理含斜杠的系列代码，如 GV310/320 → part1=GV310, part2=320"""
    series_code = f"{part1}/{part2}"
    return _get_curve_options_impl(series_code, db)


def _get_curve_options_impl(series_code: str, db: Session):
    """获取该系列可选的曲线筛选配置（支持 GV120 完整级联）
    
    GV120 级联逻辑:
      Trim Type → Pressure Rating → Nominal Valve Size → Plug Size
    同时返回:
      - Table1: DN 级别行程 + Plug Size 范围
      - Table2: Plug 级别 cv_min / cv_eq / stk_index
      - Flow Direction 选项 (FTC / FTO)
    """
    vt = db.query(ValveType).filter(ValveType.series_code == series_code).first()
    if not vt:
        raise HTTPException(status_code=404, detail=f"阀门系列 {series_code} 不存在")

    cfg = _get_cfg(series_code, "", db)

    # ========== 通用压力等级 ==========
    pim_src = _resolve_curve_alias(series_code)
    pim_asme_rows = db.query(ValvePlugIndexMap.asme_class).filter(
        ValvePlugIndexMap.series_code.in_([series_code, pim_src]),
        ValvePlugIndexMap.asme_class != 'all',
    ).distinct().order_by(ValvePlugIndexMap.asme_class).all()
    cvstk_pres_rows = db.query(ValveCvStk.pressure_rating).filter(
        ValveCvStk.series_code == series_code,
        ValveCvStk.pressure_rating.isnot(None),
    ).distinct().order_by(ValveCvStk.pressure_rating).all()

    pressure_ratings = []
    for r in pim_asme_rows:
        if r[0] and r[0] not in pressure_ratings:
            pressure_ratings.append(r[0])
    for r in cvstk_pres_rows:
        if r[0] and r[0] not in pressure_ratings:
            pressure_ratings.append(r[0])
    if not pressure_ratings:
        pressure_ratings = ['all']

    # ========== 通用 Trim Type (EQ%/Linear) ==========
    trim_types = ["EQ%", "Linear"]
    if vt.trim_option_types:
        raw = [t.strip() for t in vt.trim_option_types.split(',')]
        if raw:
            trim_types = raw

    # ========== Trim/Seat Type (来自 valve_cv_stk.trim_type) ==========
    trim_seat_types = []
    tst_rows = db.query(ValveCvStk.trim_type).filter(
        ValveCvStk.series_code == series_code,
        ValveCvStk.trim_type.isnot(None),
    ).distinct().order_by(ValveCvStk.trim_type).all()
    trim_seat_types = [r[0] for r in tst_rows if r[0]]

    # ========== Flow Direction ==========
    flow_directions = []
    if series_code in ('GV110', 'GV120', 'GV410', 'GC120', 'GC210'):
        flow_directions = [
            {"code": "FTC", "label": "Flow-to-Close (正向流, 关闭方向)"},
            {"code": "FTO", "label": "Flow-to-Open (反向流, 开启方向)"},
        ]

    # ========== GV120 级联: Trim Type → Pressure Rating → DN → Plug Size 范围 ==========
    cascade = {}
    table1 = []  # DN 级别
    table2 = []  # Plug 级别

    if trim_seat_types:
        for tst in trim_seat_types:
            # 该 Trim Type 可用的压力等级
            # Table1 记录用 dn_mm.isnot(None) 过滤 (废弃 plug_min_mm)
            tst_pressures_rows = db.query(ValveTrimSize.asme_class).filter(
                ValveTrimSize.series_code == series_code,
                ValveTrimSize.trim_type == tst,
                ValveTrimSize.asme_class.isnot(None),
                ValveTrimSize.dn_mm.isnot(None),  # Table1 记录 (废弃 plug_min_mm)
            ).distinct().order_by(ValveTrimSize.asme_class).all()
            tst_pressures = [r[0] for r in tst_pressures_rows if r[0]]

            # 每个压力等级下的 DN + 行程 (Table1, 不再返回 plug_min_mm/plug_max_mm)
            p_dn_ranges = {}
            for pres in tst_pressures:
                dn_rows = db.query(ValveTrimSize).filter(
                    ValveTrimSize.series_code == series_code,
                    ValveTrimSize.trim_type == tst,
                    ValveTrimSize.asme_class == pres,
                    ValveTrimSize.dn_mm.isnot(None),
                ).order_by(ValveTrimSize.dn_mm).all()

                dn_ranges = []
                for ts in dn_rows:
                    dn_ranges.append({
                        "dn_label": ts.dn_inch,
                        "dn_mm": ts.dn_mm,
                        "stroke_mm": ts.stroke_mm,
                    })
                    table1.append({
                        "trim_type": tst,
                        "pressure_rating": pres,
                        "dn_label": ts.dn_inch,
                        "dn_mm": ts.dn_mm,
                        "stroke_mm": ts.stroke_mm,
                    })
                p_dn_ranges[pres] = dn_ranges

            cascade[tst] = {
                "pressure_ratings": tst_pressures,
                "dn_ranges_by_pressure": p_dn_ranges,
            }

            # Table2: 从 valve_cv_stk 查询 (废弃从 valve_trim_sizes 查)
            # 按 plug_mm 分组合并 EQ%/Linear 的 rated_cv; stk_index 从 cv_stk 取
            # cv_min 仍从 valve_trim_sizes 查 (按 plug_mm 匹配)
            mapped_tt = _map_trim_seat_to_cvstk_trim_type(tst)
            cvstk_t2_q = db.query(ValveCvStk).filter(
                ValveCvStk.series_code == series_code,
                ValveCvStk.plug_mm.isnot(None),
            )
            if mapped_tt:
                cvstk_t2_q = cvstk_t2_q.filter(ValveCvStk.trim_type == mapped_tt)
            cvstk_t2_rows = cvstk_t2_q.all()

            # 按 plug_mm 合并 EQ%/Linear 的 rated_cv 和 stk_index
            plug_map = {}  # plug_mm -> {cv_eq, cv_linear, stk_index}
            for c in cvstk_t2_rows:
                pm = c.plug_mm
                if pm not in plug_map:
                    plug_map[pm] = {"cv_eq": None, "cv_linear": None, "stk_index": None}
                if c.flow_char == 'EQ%':
                    plug_map[pm]["cv_eq"] = c.rated_cv
                elif c.flow_char == 'Linear':
                    plug_map[pm]["cv_linear"] = c.rated_cv
                if c.stk_index is not None:
                    plug_map[pm]["stk_index"] = c.stk_index

            # cv_min 从 valve_trim_sizes 查 (按 plug_mm 匹配)
            cvmin_rows = db.query(ValveTrimSize.plug_mm, ValveTrimSize.cv_min).filter(
                ValveTrimSize.series_code == series_code,
                ValveTrimSize.trim_type == tst,
                ValveTrimSize.plug_mm.isnot(None),
                ValveTrimSize.cv_min.isnot(None),
            ).all()
            cv_min_by_plug = {r[0]: r[1] for r in cvmin_rows}

            plugs = []
            for pm in sorted(plug_map.keys()):
                entry = plug_map[pm]
                plugs.append({
                    "plug_mm": pm,
                    "cv_min": cv_min_by_plug.get(pm),
                    "cv_eq": entry["cv_eq"],
                    "cv_linear": entry["cv_linear"],
                    "stk_index": entry["stk_index"],
                })
                table2.append({
                    "trim_type": tst,
                    "plug_mm": pm,
                    "cv_min": cv_min_by_plug.get(pm),
                    "cv_eq": entry["cv_eq"],
                    "cv_linear": entry["cv_linear"],
                    "stk_index": entry["stk_index"],
                })
            cascade[tst]["plug_table"] = plugs

    # ========== 传统逻辑 (非 GV 系列用) ==========
    # BT/BC/BE 系列的 valve_cv_stk 用 dn_label 标识尺寸 (plug_mm=None)
    DN_SIZE_TRIM_SERIES = ('BT110', 'BT120', 'BT210', 'BC110', 'BC120', 'BE110', 'BE120')

    # 从 valve_cv_stk 取 plug_mm
    cvstk_plugs = db.query(ValveCvStk.plug_mm).filter(
        ValveCvStk.series_code == series_code,
        ValveCvStk.plug_mm.isnot(None),
    ).distinct().order_by(ValveCvStk.plug_mm).all()
    plugs = sorted(set([round(r[0], 1) for r in cvstk_plugs if r[0]]))

    # 从 valve_cv_stk 取 dn_label (BT/BC/BE 系列)
    if series_code in DN_SIZE_TRIM_SERIES:
        cvstk_dns = db.query(ValveCvStk.dn_label).filter(
            ValveCvStk.series_code == series_code,
            ValveCvStk.dn_label.isnot(None),
        ).distinct().order_by(ValveCvStk.dn_label).all()
        for r in cvstk_dns:
            v = r[0]
            if v not in plugs:
                plugs.append(v)
        plugs.sort()

    plug_sizes_by_pressure = {pres: list(plugs) for pres in pressure_ratings}

    all_plugs = sorted(set(p for v in plug_sizes_by_pressure.values() for p in v))

    # ========== has_curve_data ==========
    pim_src = _resolve_curve_alias(series_code)
    has_pim = db.query(ValvePlugIndexMap).filter(
        ValvePlugIndexMap.series_code.in_([series_code, pim_src])
    ).count() > 0
    has_curve_data = bool(cfg) and (
        has_pim 
        or cfg.stroke_mode in ('ln_eqn', 'linear')
        or cfg.stroke_eq_index is not None
    )

    default_pres = pressure_ratings[0] if pressure_ratings else ''
    default_plugs = plug_sizes_by_pressure.get(default_pres, []) if default_pres else []
    default_plug = default_plugs[0] if default_plugs else None

    # 有 valve_cv_stk 数据的系列: 推导默认 nominal_dn / nominal_trim
    default_nominal_dn = None
    default_nominal_trim = None
    if series_code.startswith('GC120') or series_code.startswith('GC210'):
        cvstk_def = db.query(ValveCvStk).filter(
            ValveCvStk.series_code == series_code,
            ValveCvStk.dn_label.isnot(None),
        ).order_by(ValveCvStk.dn_label).first()
        if cvstk_def:
            default_nominal_dn = cvstk_def.dn_label
            default_nominal_trim = cvstk_def.trim_label
            default_plug = cvstk_def.plug_mm


    # ========== 配置化筛选器 (前端按此动态渲染) ==========
    filter_configs = []
    # NOTE: 暂时不按 is_enabled 过滤, 返回所有筛选器配置以便核对 (用户要求)
    db_configs = db.query(ValveFilterConfig).filter(
        ValveFilterConfig.series_code == series_code,
    ).order_by(ValveFilterConfig.filter_order).all()

    def _get_col_val(model, col_name):
        """从指定 model 取列对象"""
        if hasattr(model, col_name):
            return getattr(model, col_name)
        return None

    for fc in db_configs:
        cfg_item = {
            "key": fc.filter_key,
            "label": fc.display_label,
            "order": fc.filter_order,
            "source": fc.option_source,
            "default": fc.default_value,
            "dependent_on": fc.dependent_on,
        }

        if fc.option_source == 'hardcoded' and fc.hardcoded_options:
            cfg_item["options"] = json.loads(fc.hardcoded_options)
        elif fc.option_source == 'stroke':
            # 从 valve_cv_stk.stroke_value + stroke_unit 提取开启角度选项 (仅角行程 °)
            rows = db.query(ValveCvStk.stroke_value, ValveCvStk.stroke_unit).filter(
                ValveCvStk.series_code == series_code,
                ValveCvStk.stroke_value.isnot(None),
                ValveCvStk.stroke_unit == "°",
            ).distinct().all()
            opts = []
            for r in rows:
                val, unit = r[0], r[1]
                if val is None:
                    continue
                code = str(int(val)) if float(val).is_integer() else str(val)
                label = f"{code}{unit or '°'}"
                opts.append({"code": code, "label": label})
            cfg_item["options"] = opts
        elif fc.option_source == 'data':
            if not fc.value_field:
                cfg_item["options"] = []
            else:
                col = _get_col_val(ValveCvStk, fc.value_field)
                if col is not None:
                    rows = db.query(col).filter(
                        ValveCvStk.series_code == series_code,
                        col.isnot(None),
                    ).distinct().order_by(col).all()
                    cfg_item["options"] = [str(r[0]) for r in rows if r[0] is not None]
        elif fc.option_source == 'cascade':
            if not fc.value_field:
                cfg_item["options"] = []
                # 有 dependent_on 也不需要查 value_field
                if fc.dependent_on:
                    cfg_item["options_by_parent"] = {}
            else:
                col = _get_col_val(ValveCvStk, fc.value_field)

            def _fmt_key_val(v):
                """格式化值，与前端 formatOpt 输出保持一致:
                整数浮点数(如15.0) -> '15', 非整数(如6.5) -> '6.5', 其他直接 str"""
                if isinstance(v, float):
                    if v == int(v):
                        return str(int(v))
                    return str(round(v, 1))
                return str(v) if v is not None else ''

            if col is not None:
                rows = db.query(col).filter(
                    ValveCvStk.series_code == series_code,
                    col.isnot(None),
                ).distinct().order_by(col).all()
                cfg_item["options"] = [_fmt_key_val(r[0]) for r in rows if r[0] is not None]

                # 多级级联: dependent_on 逗号分隔多个父级 filter_key
                # 父级 filter_key 到 valve_cv_stk 字段名的映射
                PARENT_FIELD_MAP = {
                    'trim_type': 'trim_type',
                    'pressure_rating': 'pressure_rating',
                    'nominal_dn': 'dn_label',
                    'nominal_trim': 'trim_label',
                    'seat_type': 'seat_type',
                    'flow_char': 'flow_char',
                }

                if fc.dependent_on:
                    parents = [p.strip() for p in fc.dependent_on.split(',') if p.strip()]
                    parent_fields = [PARENT_FIELD_MAP.get(p, p) for p in parents]

                    # 通用多级分组: 按所有父级字段组合分组查询 value_field
                    by_parent = {}
                    all_rows = db.query(ValveCvStk).filter(
                        ValveCvStk.series_code == series_code,
                        col.isnot(None),
                    ).all()
                    for r in all_rows:
                        key_parts = [_fmt_key_val(getattr(r, pf)) for pf in parent_fields]
                        key = '|'.join(key_parts)
                        val = getattr(r, fc.value_field)
                        if val is not None:
                            by_parent.setdefault(key, set()).add(
                                round(val, 1) if isinstance(val, float) else val
                            )
                    by_parent = {k: sorted(v) for k, v in by_parent.items()}

                    cfg_item["options_by_parent"] = by_parent

        filter_configs.append(cfg_item)

    return {
        "series_code": series_code,
        "has_curve_data": has_curve_data,
        
        # 通用下拉
        "filters": {
            "pressure_ratings": pressure_ratings,
            "plug_sizes": all_plugs,
            "plug_sizes_by_pressure": plug_sizes_by_pressure,
            "trim_types": trim_types,
            "trim_seat_types": trim_seat_types,
            "flow_directions": flow_directions,
        },
        "filter_configs": filter_configs,
        
        # GV120 级联数据
        "cascade": cascade,
        
        # Table1/Table2 完整数据
        "table1": table1,
        "table2": table2,
        
        "default_selection": {
            "pressure_rating": default_pres,
            "plug_size": default_plug,
            "nominal_dn": default_nominal_dn,
            "nominal_trim": default_nominal_trim,
            "trim_type": trim_types[0] if trim_types else 'EQ%',
            "trim_seat_type": trim_seat_types[0] if trim_seat_types else None,
            "flow_direction": next(
                (fc.default_value for fc in db_configs if fc.filter_key == 'flow_direction' and fc.default_value),
                flow_directions[0]["code"] if flow_directions else None,
            ),
        },
        "cfg": {
            "stroke_mode": cfg.stroke_mode if cfg else None,
            "stroke_fstk": cfg.stroke_fstk if cfg else None,
            "stroke_eq_index": cfg.stroke_eq_index if cfg else None,
        } if cfg else None,
    }


@router.get("/{series_code}/curves-by-selection")
def get_curves_by_selection(
    series_code: str,
    pressure_rating: str = "",
    plug_size: float = 0,
    nominal_dn: str = "",
    nominal_trim: str = "",
    trim_type: str = "",
    trim_seat_type: str = "",
    flow_direction: str = "",
    opening_angle: str = "",
    seat_type: str = "",
    trim_characteristics: str = "",
    db: Session = Depends(get_db),
):
    return _get_curves_by_selection_impl(series_code, pressure_rating, plug_size, nominal_dn, nominal_trim, trim_type, trim_seat_type, flow_direction, opening_angle, seat_type, trim_characteristics, db)


@router.get("/{part1}/{part2}/curves-by-selection")
def get_curves_by_selection_slash(
    part1: str, part2: str,
    pressure_rating: str = "",
    plug_size: float = 0,
    nominal_dn: str = "",
    nominal_trim: str = "",
    trim_type: str = "",
    trim_seat_type: str = "",
    flow_direction: str = "",
    opening_angle: str = "",
    seat_type: str = "",
    trim_characteristics: str = "",
    db: Session = Depends(get_db),
):
    """处理含斜杠的系列代码，如 BV310/320"""
    series_code = f"{part1}/{part2}"
    return _get_curves_by_selection_impl(series_code, pressure_rating, plug_size, nominal_dn, nominal_trim, trim_type, trim_seat_type, flow_direction, opening_angle, seat_type, trim_characteristics, db)

def _get_curves_by_selection_impl(
    series_code: str,
    pressure_rating: str = "",
    plug_size: float = 0,
    nominal_dn: str = "",
    nominal_trim: str = "",
    trim_type: str = "",
    trim_seat_type: str = "",
    flow_direction: str = "",
    opening_angle: str = "",
    seat_type: str = "",
    trim_characteristics: str = "",
    db: Session = Depends(get_db),
):
    """根据多维度筛选参数返回曲线配置 + xT
    
    查找逻辑（完全依据 Excel "Choices for Graphs" 区域）:
    
    1. FL / Kc / Fd 曲线索引 → valve_series_curve_config 直接读取（每个系列不同！）
    2. Stroke Curve:
       - eq_index: 查 valve_plug_index_map(series, rating, plug) → eqcv 曲线
       - ln_eqn:   返回 fstk 参数让前端用对数方程
       - linear:   %Stk = phi 直接相等
       - GC120/< 600# 特殊: 强制切换为 ln_eqn 模式
    
    xT = 0.84 * FL(phi=1.0)^2
    """
    cfg = _get_cfg(series_code, pressure_rating, db)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"系列 {series_code} 无曲线配置")

    # 别名系列: PIM 查询同时搜索原系列和别名系列 (如 BC120 → 也查 BC110)
    pim_src = _resolve_curve_alias(series_code)
    pim_series_list = [series_code, pim_src] if pim_src != series_code else [series_code]

    # ========== 由 nominal_dn + nominal_trim 推导 plug_mm ==========
    # 覆盖所有有 valve_cv_stk 数据的系列 (GC120/GC210/GV120/GV110/GV410/BC110/BE120/BT* 等)
    # 当前端漏传或传错 plug_size 时，从 dn_label + trim_label 反推 plug_mm
    derived_plug_mm = None
    if nominal_dn and nominal_trim:
        dn_label, _ = _parse_nominal_dn(nominal_dn, db)
        trim_label = _parse_nominal_trim(nominal_trim, db)
        if dn_label and trim_label:
            cs_q = db.query(ValveCvStk).filter(
                ValveCvStk.series_code == series_code,
                ValveCvStk.dn_label == dn_label,
                ValveCvStk.trim_label == trim_label,
                ValveCvStk.plug_mm.isnot(None),
            )
            # 优先匹配 EQ% (flow_char 匹配), 兜底用任意行
            if trim_characteristics:
                cs_q = cs_q.filter(ValveCvStk.flow_char == trim_characteristics)
            cs = cs_q.first()
            if not cs:
                cs = db.query(ValveCvStk).filter(
                    ValveCvStk.series_code == series_code,
                    ValveCvStk.dn_label == dn_label,
                    ValveCvStk.trim_label == trim_label,
                    ValveCvStk.plug_mm.isnot(None),
                ).first()
            if cs:
                derived_plug_mm = cs.plug_mm
            else:
                # === 兜底: valve_cv_stk 里 plug_mm=None 时, 从 trim_label 解析数值 ===
                # 例: "65A" → 65, "100A" → 100
                try:
                    trimmed = trim_label.strip().upper().replace('A', '').strip()
                    derived_plug_mm = float(trimmed)
                except (ValueError, AttributeError):
                    derived_plug_mm = None

            # 覆盖 plug_size: 当原值为 falsy (0/None) 或推导值与原值差异较大时使用推导值
            if derived_plug_mm and (not plug_size or abs(float(plug_size) - derived_plug_mm) > 1):
                plug_size = derived_plug_mm

    cols = [c for c in ValveFactorCurve.__table__.columns
            if c.name not in ("created_at", "updated_at")]
    col_names = [c.name for c in cols]
    
    def fetch(factor_type, idx):
        if idx is None:
            return None
        row = db.query(*cols).filter(
            ValveFactorCurve.factor_type == factor_type,
            ValveFactorCurve.eq_index == int(idx)
        ).first()
        return dict(zip(col_names, row)) if row else None
    
    # ========== 标准化筛选器参数 ==========
    # trim_characteristics: EQ%/Linear 流量特性 (用于 GC/GV 系列 FL/Kc/Fd 条件)
    # trim_type: 阀芯/阀内件形式 (GV120 的 Standard/Large Cv/ON-OFF)
    # seat_type: 阀座形式 (BT110 的 Damper/15 Deg Sealed/Back Seat)
    # opening_angle: 蝶阀开启角度 (60/90, 直接来自前端 opening_angle 筛选器)

    # 统一 flow_char: trim_characteristics 优先, 否则 trim_type (若为 EQ%/Linear)
    flow_char = trim_characteristics
    if not flow_char and trim_type in ('EQ%', 'Linear'):
        flow_char = trim_type

    # BT 系列: opening_angle 直接来自参数 (不再从 trim_type 提取)
    opening_angle_val = None
    if opening_angle:
        try:
            opening_angle_val = int(str(opening_angle).split()[0])  # "60 Deg" → 60
        except (ValueError, TypeError):
            pass

    # BT 系列旧兼容: 若 opening_angle 为空, 尝试从 trim_type 提取 (如 "60 Deg")
    if opening_angle_val is None and series_code in ('BT110', 'BT120', 'BT210') and trim_type:
        m = re.search(r'(\d+)', trim_type)
        if m:
            opening_angle_val = int(m.group(1))

    # 2.1 确定 FL/Kc/Fd 索引 (Excel "Choices for Graphs" 条件公式)
    fl_idx = cfg.fl_eq_index
    kc_idx = cfg.kc_eq_index
    fd_idx = cfg.fd_eq_index
    fd_mode = cfg.fd_mode

    # GC120 系列 (含 H/HH 细化型号): Fd = IF(trim_type="Linear", 1, 2)  — FL/Kc 固定为 1
    if series_code.startswith('GC120'):
        fd_idx = 1 if flow_char == 'Linear' else 2
        fd_mode = 'table'

    # GV 系列 (含 H/HH 细化型号): FL/Kc = IF(flow_direction="FTO", 1, 3), Fd = IF("FTO", "Eqn", 3)
    if series_code in ('GV110', 'GV410') or series_code.startswith('GV120'):
        if flow_direction == 'FTO':
            fl_idx = 1
            kc_idx = 1
            fd_idx = None
            fd_mode = 'eqn'
        else:
            fl_idx = 3
            kc_idx = 3
            fd_idx = 3
            fd_mode = 'table'

    # BT 系列 (BT110/BT120/BT210): FL/Kc/Fd index 取决于开启角度
    # 75 Deg / 90 Deg → index 7, 其他 (60/45) → index 6
    # 若 opening_angle 未传, 从 valve_cv_stk.stroke_value 取第一个值兜底 (角行程)
    if series_code in ('BT110', 'BT120', 'BT210'):
        if opening_angle_val is None:
            cvstk_stroke = db.query(ValveCvStk.stroke_value).filter(
                ValveCvStk.series_code == series_code,
                ValveCvStk.stroke_value.isnot(None),
                ValveCvStk.stroke_unit == "°",
            ).first()
            if cvstk_stroke and cvstk_stroke[0] is not None:
                opening_angle_val = int(cvstk_stroke[0])
        angle_idx = 7 if opening_angle_val in (75, 90) else 6
        fl_idx = angle_idx
        kc_idx = angle_idx
        fd_idx = angle_idx
        fd_mode = 'table'

    # 2.2 取曲线数据
    fl_curve = fetch('fl', fl_idx)
    kc_curve = fetch('kc', kc_idx)
    fd_curve = fetch('fd', fd_idx) if fd_mode == 'table' else None
    
    # ========== rated_cv 查找 (多策略兜底) ==========
    rated_cv = None
    cv_min = None
    cv_linear = None
    stroke_value = None  # 行程数值, 从 valve_trim_sizes 或 valve_cv_stk 获取
    stroke_unit = None   # 行程单位: mm (直行程) 或 ° (角行程)
    kfd_value = None  # GC210 等系列的 KFd 查表值
    
    # 系列 → 尺寸匹配字段映射
    # BC110/BE120 无 plug_mm，用 dn_mm；BT 系列也用 dn_mm
    DN_MATCH_SERIES = ('BT110', 'BT120', 'BT210', 'BC110', 'BC120', 'BE110', 'BE120')
    PLUG_MATCH_SERIES = ('GV110', 'GV120', 'GV410', 'GC120', 'GC210')
    
    # 标准化压力标签（Excel 不一致: "< 600#" / "to 600#" / "up to 300#" 都应该能匹配）
    def norm_pressure(p):
        if not p: return None
        p = p.strip()
        # 归一化: to 600#, < 600#, up to 600# → 统一成 trim_sizes 中的 asme_class
        # 实际数据值: GC120="< 600#", GV120="to 600#", GV410="up to 300#"
        # 先尝试精确匹配，再尝试包含匹配
        return p
    
    def _pick_cv(ts, sc, opening_angle=None):
        """根据系列类型选择正确的 Cv 字段"""
        # BT 系列: 60 Deg → cv_60deg, 90 Deg → cv_90deg
        # opening_angle 可能是字符串 "60" 或整数 60
        oa = None
        if opening_angle:
            try:
                oa = int(str(opening_angle).split()[0])
            except (ValueError, TypeError):
                pass
        if sc in ('BT110', 'BT120', 'BT210'):
            return ts.cv_60deg if oa == 60 else ts.cv_90deg
        if sc in ('BC110', 'BC120', 'BE110', 'BE120'):
            return ts.cv_metal_seat or ts.cv_soft_seat
        return ts.cv_eq or ts.cv_linear
    
    # GV120 系列: trim_type 可能来自 trim_seat_type 或 trim_type 参数
    gv_trim_type = trim_seat_type or trim_type

    # 策略 1: 精确 pressure + 尺寸 + trim_type
    if pressure_rating and plug_size:
        ts_q = db.query(ValveTrimSize).filter(ValveTrimSize.series_code == series_code)
        
        # 压力匹配: 精确或 'all' 兜底
        ts_q = ts_q.filter(
            (ValveTrimSize.asme_class == pressure_rating) |
            (ValveTrimSize.asme_class == 'all') |
            (ValveTrimSize.asme_class.is_(None))
        )
        
        # 尺寸匹配
        if series_code in DN_MATCH_SERIES:
            ts_q = ts_q.filter(ValveTrimSize.dn_mm == plug_size)
        else:
            ts_q = ts_q.filter(ValveTrimSize.plug_mm == plug_size)
            if gv_trim_type and series_code.startswith('GV120'):
                ts_q = ts_q.filter(ValveTrimSize.trim_type.like(f'%{gv_trim_type}%'))
        
        ts = ts_q.first()
        if ts:
            rated_cv = _pick_cv(ts, series_code, opening_angle)
            cv_min = ts.cv_min or cv_min
            cv_linear = ts.cv_linear or cv_linear
            stroke_value = ts.stroke_mm or stroke_value  # 补上 stroke (ValveTrimSize 恒为 mm)
            stroke_unit = stroke_unit or "mm"

    # 策略 2: GV120 系列兜底 — Table2 无 asme_class，按 trim_type + plug_mm
    if rated_cv is None and series_code.startswith('GV120') and gv_trim_type and plug_size:
        ts = db.query(ValveTrimSize).filter(
            ValveTrimSize.series_code == series_code,
            ValveTrimSize.trim_type.like(f'%{gv_trim_type}%'),
            ValveTrimSize.plug_mm == plug_size,
            ValveTrimSize.cv_eq.isnot(None),
        ).first()
        if ts:
            rated_cv = ts.cv_eq
            cv_linear = ts.cv_linear or cv_linear
            stroke_value = ts.stroke_mm or stroke_value  # 补上 stroke (ValveTrimSize 恒为 mm)
            stroke_unit = stroke_unit or "mm"
    
    # 策略 3: 只用尺寸匹配（忽略 pressure）
    if rated_cv is None and plug_size:
        ts_q = db.query(ValveTrimSize).filter(ValveTrimSize.series_code == series_code)
        if series_code in DN_MATCH_SERIES:
            ts_q = ts_q.filter(ValveTrimSize.dn_mm == plug_size)
        else:
            ts_q = ts_q.filter(ValveTrimSize.plug_mm == plug_size)
        if gv_trim_type and series_code.startswith('GV120'):
            ts_q = ts_q.filter(ValveTrimSize.trim_type.like(f'%{gv_trim_type}%'))
        ts = ts_q.first()
        if ts:
            rated_cv = _pick_cv(ts, series_code, opening_angle)
            cv_min = ts.cv_min or cv_min
            cv_linear = ts.cv_linear or cv_linear
            stroke_value = ts.stroke_mm or stroke_value  # 补上 stroke (ValveTrimSize 恒为 mm)
            stroke_unit = stroke_unit or "mm"

    # 策略 4: 通用兜底 — 只要有 plug_size 或 dn_mm 匹配
    if rated_cv is None and plug_size:
        ts = db.query(ValveTrimSize).filter(
            ValveTrimSize.series_code == series_code,
            (ValveTrimSize.plug_mm == plug_size) | (ValveTrimSize.dn_mm == plug_size),
        ).first()
        if ts:
            rated_cv = _pick_cv(ts, series_code, opening_angle)
            cv_min = ts.cv_min or cv_min
            cv_linear = ts.cv_linear or cv_linear
            stroke_value = ts.stroke_mm or stroke_value  # 补上 stroke (ValveTrimSize 恒为 mm)
            stroke_unit = stroke_unit or "mm"

    # ========== 从 valve_cv_stk 表取 rated_cv 与 stroke_value ==========
    # valve_cv_stk 是所有系列的主数据源 (BT110/BT120 的 valve_trim_sizes 为空)
    cvstk_rated, cvstk_stroke, cvstk_stroke_unit = _query_cv_stk_rated_cv(
        series_code, pressure_rating, plug_size, nominal_dn, nominal_trim,
        trim_type, trim_seat_type, db, seat_type=seat_type,
        trim_characteristics=trim_characteristics,
        opening_angle_val=opening_angle_val,
    )
    if cvstk_rated is not None:
        rated_cv = cvstk_rated
    if cvstk_stroke is not None:
        stroke_value = cvstk_stroke
        stroke_unit = cvstk_stroke_unit or stroke_unit

    # ========== 查询 seat_type (阀座形式) ==========
    seat_type_value = None
    if nominal_dn and nominal_trim:
        dn_label, _ = _parse_nominal_dn(nominal_dn, db)
        trim_label = _parse_nominal_trim(nominal_trim, db)
        if dn_label and trim_label:
            st_q = db.query(ValveCvStk.seat_type).filter(
                ValveCvStk.series_code == series_code,
                ValveCvStk.dn_label == dn_label,
                ValveCvStk.trim_label == trim_label,
                ValveCvStk.seat_type.isnot(None),
            )
            st_row = st_q.first()
            if st_row:
                seat_type_value = st_row[0]
    # 兜底: 用 plug_size 查 seat_type
    if not seat_type_value and plug_size:
        st_q2 = db.query(ValveCvStk.seat_type).filter(
            ValveCvStk.series_code == series_code,
            ValveCvStk.plug_mm == float(plug_size),
            ValveCvStk.seat_type.isnot(None),
        )
        mapped_tt2 = _map_trim_seat_to_cvstk_trim_type(trim_seat_type)
        if mapped_tt2:
            st_q2 = st_q2.filter(ValveCvStk.trim_type == mapped_tt2)
        st_row2 = st_q2.first()
        if st_row2:
            seat_type_value = st_row2[0]

    # ========== 从 valve_cv_stk 查询 kfd/kfo/kfb (改造: 不再从 valve_trim_sizes 查) ==========
    # 按 plug_mm 匹配优先; trim_label (JIS A) 兜底 (GC210 等)
    cvstk_kfd, cvstk_kfo, cvstk_kfb = None, None, None
    if plug_size:
        kfd_q = db.query(ValveCvStk).filter(
            ValveCvStk.series_code == series_code,
            ValveCvStk.plug_mm == float(plug_size),
        )
        mapped_tt = _map_trim_seat_to_cvstk_trim_type(trim_seat_type)
        if mapped_tt:
            kfd_q = kfd_q.filter(ValveCvStk.trim_type == mapped_tt)
        kfd_row = kfd_q.first()
        # 兜底: 用 trim_label 匹配 (GC210 等无 plug_mm 时通过 nominal_trim 转 JIS A)
        if not kfd_row and nominal_trim:
            trim_label_jis = _parse_nominal_trim(nominal_trim, db)
            if trim_label_jis:
                kfd_q2 = db.query(ValveCvStk).filter(
                    ValveCvStk.series_code == series_code,
                    ValveCvStk.trim_label == trim_label_jis,
                )
                if mapped_tt:
                    kfd_q2 = kfd_q2.filter(ValveCvStk.trim_type == mapped_tt)
                kfd_row = kfd_q2.first()
        if kfd_row:
            cvstk_kfd = kfd_row.kfd
            cvstk_kfo = kfd_row.kfo
            cvstk_kfb = kfd_row.kfb
    if cvstk_kfd is not None:
        kfd_value = cvstk_kfd

    # 2.3 Fd 特殊处理
    # GC210 系列: 使用 Excel 公式 Fd = (π/(4*20.8))^0.5 * KFd * ((KFo*φ)^-2 - KFb^-2)^0.25
    # 需要返回 kfo/kfb/kfd 参数, 前端按公式计算
    gc210_kfo = None
    gc210_kfb = None
    gc210_kfd = None
    if series_code.startswith('GC210') and kfd_value is not None:
        # 改造: kfo/kfb 从 valve_cv_stk 查 (已在上方查询)
        if cvstk_kfo is not None and cvstk_kfb is not None:
            gc210_kfo = cvstk_kfo
            gc210_kfb = cvstk_kfb
            gc210_kfd = kfd_value
            fd_mode = 'gc210_eqn'
            fd_curve = {
                "factor_type": "fd",
                "eq_index": None,
                "p0": 0, "p1": 0, "p2": 0, "p3": 0, "p4": 0,
                "value_min": None,
                "value_max": None,
                "kfo": gc210_kfo,
                "kfb": gc210_kfb,
                "kfd": gc210_kfd,
                "remark": f"GC210 Fd formula: KFo={gc210_kfo}, KFb={gc210_kfb}, KFd={gc210_kfd}",
            }
        else:
            # kfo/kfb 缺失, 兜底用常数 KFd
            fd_curve = {
                "factor_type": "fd",
                "eq_index": None,
                "p0": kfd_value,
                "p1": 0, "p2": 0, "p3": 0, "p4": 0,
                "value_min": kfd_value,
                "value_max": kfd_value,
                "remark": f"KFd constant = {kfd_value} (kfo/kfb missing, fallback)",
            }
            fd_mode = 'kfd'
    elif fd_mode == 'eqn' and kfd_value is not None:
        # 其他系列: eqn 模式且有 KFd 查表值时，返回常数 Fd 曲线
        fd_curve = {
            "factor_type": "fd",
            "eq_index": None,
            "p0": kfd_value,
            "p1": 0, "p2": 0, "p3": 0, "p4": 0,
            "value_min": kfd_value,
            "value_max": kfd_value,
            "remark": f"KFd constant = {kfd_value} (from plug_size lookup)",
        }
        fd_mode = 'kfd'
    
    # 3. Stroke Curve — 智能选择 stroke_mode
    effective_mode = cfg.stroke_mode
    effective_fstk = cfg.stroke_fstk

    # GV120 系列 (含 H/HH 细化型号): 根据阀内件形式动态选择 stroke_mode
    # - Large Cv P-port: poly_cv_div100 (有独立 %Stk Index 18-25)
    # - Standard P-port / On/Off Q-port: ln_eqn (无独立 %Stk Index)
    #
    # 关键: gv_trim_type = trim_seat_type or trim_type (line 1125 已定义)
    #       后端 default_selection 把 trim_type 命名混了 (trim_type 存流量特性 EQ%, 
    #       trim_seat_type 存阀内件形式 Large Cv)。所以必须用 gv_trim_type 取值!
    # GV130 使用 GV120 的曲线配置 (别名), 所以也走此逻辑
    if series_code.startswith('GV120') or series_code == 'GV130':
        if gv_trim_type and 'Large' in gv_trim_type:
            effective_mode = 'poly_cv_div100'
        elif gv_trim_type and ('Standard' in gv_trim_type or 'On' in gv_trim_type or 'Off' in gv_trim_type):
            effective_mode = 'ln_eqn'
        else:
            # 兜底: trim_type/gv_trim_type 都空或传错 (如 trim_type='EQ%')
            # 检查 cfg.stroke_mode: eq_index(旧GV120默认) / ln_eqn(GV120H/GV120HH?)
            # 再根据 plug_size 能匹配 plug_index_map → 大概率是 Large Cv
            effective_mode = cfg.stroke_mode or 'ln_eqn'
            if effective_mode == 'eq_index' and plug_size:
                try:
                    if db.query(ValvePlugIndexMap).filter(
                        ValvePlugIndexMap.series_code.in_(pim_series_list),
                        ValvePlugIndexMap.plug_mm == float(plug_size),
                    ).first():
                        effective_mode = 'poly_cv_div100'
                except Exception:
                    pass

    # === 流量特性优先级最高: Linear → %Stk = phi (直线) ===
    # Excel 公式: =IF(D107="Linear", phi, IF(Standard, ln_eqn, poly_cv_div100))
    # 放在所有系列逻辑之后, 确保不被覆盖. 适用于所有系列 (GV120/GC120/GC210 等)
    if trim_characteristics and trim_characteristics.strip().lower() == 'linear':
        effective_mode = 'linear'

    # ln_eqn 模式: Fstk 根据 plug_size 动态计算
    if effective_mode == 'ln_eqn':
        if series_code.startswith('GV120') or series_code == 'GV130':
            effective_fstk = 30.0 if (plug_size and plug_size <= 8) else 50.0
        elif series_code == 'GV410':
            effective_fstk = 20.0 if (plug_size and plug_size <= 8) else 30.0
        elif series_code.startswith('GC120') or series_code.startswith('GC210'):
            effective_fstk = 50.0
    
    eqcv_curve = None
    stk_index = None
    stroke_info = {
        "mode": effective_mode,
        "fstk": effective_fstk,
        "divisor": cfg.stroke_divisor,
        "opening_angle": opening_angle,
        "rated_cv": rated_cv,
        "cv_min": cv_min,
        "cv_linear": cv_linear,
        "stroke_value": stroke_value,
        "stroke_unit": stroke_unit,
        "seat_type": seat_type_value,
        "coeffs": {
            "a0": cfg.stroke_a0, "a1": cfg.stroke_a1, "a2": cfg.stroke_a2,
            "a3": cfg.stroke_a3, "a4": cfg.stroke_a4, "a5": cfg.stroke_a5, "a6": cfg.stroke_a6,
        },
    }
    
    # 需要 eqcv 多项式系数的模式
    if effective_mode in ('eq_index', 'poly_cv_div100', 'poly_phi100_div100', 'poly_cv_div_angle', 'exp_formula'):
        # 优先从 valve_cv_stk 取 stk_index (最新导入, 按 dn_label + stroke_value 匹配)
        if cvstk_rated is not None:
            cvstk_stk_q = db.query(ValveCvStk.stk_index).filter(
                ValveCvStk.series_code == series_code,
                ValveCvStk.dn_label == nominal_dn if nominal_dn else False,
                ValveCvStk.stroke_value == cvstk_stroke if cvstk_stroke else False,
                ValveCvStk.rated_cv == cvstk_rated,
                ValveCvStk.stk_index.isnot(None),
            )
            if pressure_rating:
                cvstk_stk_q = cvstk_stk_q.filter(
                    (ValveCvStk.pressure_rating == pressure_rating) |
                    (ValveCvStk.pressure_rating.is_(None))
                )
            cvstk_stk_row = cvstk_stk_q.first()
            if cvstk_stk_row:
                stk_index = cvstk_stk_row.stk_index

        # 兜底: PIM 表 (valve_plug_index_map)
        if stk_index is None and plug_size:
            # 先尝试 pressure_rating 精确匹配 (含 asme_class='all' 兜底)
            map_q = db.query(ValvePlugIndexMap).filter(
                ValvePlugIndexMap.series_code.in_(pim_series_list),
                ValvePlugIndexMap.plug_mm == plug_size,
            )
            if pressure_rating:
                map_q = map_q.filter(
                    (ValvePlugIndexMap.asme_class == pressure_rating) | (ValvePlugIndexMap.asme_class == 'all'),
                )
            map_row = map_q.first()
            if not map_row:
                # 兜底: 只用 plug_size 匹配 (忽略 asme_class)
                map_row = db.query(ValvePlugIndexMap).filter(
                    ValvePlugIndexMap.series_code.in_(pim_series_list),
                    ValvePlugIndexMap.plug_mm == plug_size,
                ).first()
            if not map_row:
                # === 最近邻匹配兜底 ===
                all_pim = db.query(ValvePlugIndexMap).filter(
                    ValvePlugIndexMap.series_code.in_(pim_series_list),
                ).all()
                if all_pim:
                    nearest = min(all_pim, key=lambda r: abs(float(r.plug_mm) - float(plug_size)))
                    if abs(float(nearest.plug_mm) - float(plug_size)) <= 25:
                        map_row = nearest
            if map_row:
                stk_index = map_row.stk_index
        
        # 没查到用默认
        if stk_index is None and cfg.stroke_eq_index:
            stk_index = cfg.stroke_eq_index
        
        if stk_index:
            eqcv_curve = fetch('eqcv', stk_index)

    
    # 5. xT = 0.84 * FL(phi=1.0)^2
    #    FL(phi=1) = P4+P3+P2+P1+P0 (多项式求和)
    #    常数曲线（系数全 0）用 value_max 作为 FL
    def _eval_const(curve):
        """计算曲线在 phi=1.0 的值，处理常数曲线"""
        if not curve:
            return None
        p = [curve.get(f'p{i}', 0) or 0 for i in range(5)]
        val = sum(p)
        vmax = curve.get('value_max')
        if val == 0 and vmax:
            val = vmax
        return val
    
    fl_rated = _eval_const(fl_curve)
    xt_calculated = round(0.84 * fl_rated ** 2, 6) if fl_rated else None
    
    return {
        "series_code": series_code,
        "pressure_rating": pressure_rating,
        "plug_size": plug_size,
        "derived_plug_mm": derived_plug_mm,
        "trim_type": trim_type,
        
        # Stroke Curve
        "stroke_mode": effective_mode,
        "stroke_info": stroke_info,
        "stroke_value": stroke_value,
        "stroke_unit": stroke_unit,
        "seat_type": seat_type_value,
        "stk_index": stk_index,
        "eqcv": eqcv_curve,
        
        # FL / Kc / Fd
        "fl": fl_curve,
        "kc": kc_curve,
        "fd": fd_curve,
        "fd_mode": fd_mode,
        
        # xT
        "fl_rated": fl_rated,
        "xt_calculated": xt_calculated,
        "xt_formula": "xT = 0.84 × FL² (FL at phi=1.0)",
        
        # 调试信息
        "debug": {
            "fl_eq_index": cfg.fl_eq_index,
            "kc_eq_index": cfg.kc_eq_index,
            "fd_eq_index": cfg.fd_eq_index,
            "cfg_remark": cfg.remark,
        }
    }


@router.get("/{series_code}/trim-sizes")
def get_trim_sizes(series_code: str, db: Session = Depends(get_db)):
    """按 series_code 查询 Trim/Cv 额定容量表

    直接返回 valve_cv_stk 表的原始数据，不做合并、拆分或跨表查询。
    表头按数据库列顺序返回。
    """
    vt = db.query(ValveType).filter(ValveType.series_code == series_code).first()
    if not vt:
        raise HTTPException(status_code=404, detail=f"阀门系列 {series_code} 不存在")

    # ---- 直接查 valve_cv_stk 原始数据 ----
    cvstk_rows = db.query(ValveCvStk).filter(
        ValveCvStk.series_code == series_code
    ).all()

    # 按 valve_cv_stk 列顺序构建行 (不含 id, series_code, created_at, updated_at)
    result = []
    for c in cvstk_rows:
        row = {
            "dn_label": c.dn_label,
            "trim_label": c.trim_label,
            "flow_char": c.flow_char,
            "trim_type": c.trim_type,
            "pressure_rating": c.pressure_rating,
            "seat_type": c.seat_type,
            "rated_cv": c.rated_cv,
            "stroke_value": c.stroke_value,
            "stroke_unit": c.stroke_unit,
            "plug_mm": c.plug_mm,
            "stk_index": c.stk_index,
            "kfd": c.kfd,
            "kfo": c.kfo,
            "kfb": c.kfb,
        }
        result.append(row)

    # 排序: 按 dn_label 数值, 再按 trim_label 数值
    def _sort_key(r):
        def _num(lbl):
            if not lbl:
                return 0.0
            try:
                return float(str(lbl).rstrip('A').strip())
            except (ValueError, TypeError):
                return 0.0
        return (_num(r.get("dn_label")), _num(r.get("trim_label")))
    result.sort(key=_sort_key)
    return result


# ---------------------------------------------------------------------------
# 阀门额定Cv与行程查询 (valve_cv_stk 表)
# 通过约束条件 (阀门型号 + 阀门通径 + 阀芯尺寸 + 可选约束) 查询 rated_cv 和 stroke
# ---------------------------------------------------------------------------
@router.get("/{series_code}/cv-stk", summary="按约束条件查询额定Cv和行程")
def get_cv_stk(
    series_code: str,
    dn_label: str = "",
    trim_label: str = "",
    flow_char: str = "",
    trim_type: str = "",
    pressure_rating: str = "",
    seat_type: str = "",
    db: Session = Depends(get_db),
):
    """通过约束条件查询 valve_cv_stk 表获取额定Cv和行程"""
    q = db.query(ValveCvStk).filter(ValveCvStk.series_code == series_code)
    if dn_label:
        q = q.filter(ValveCvStk.dn_label == dn_label)
    if trim_label:
        q = q.filter(ValveCvStk.trim_label == trim_label)
    if flow_char:
        q = q.filter(ValveCvStk.flow_char == flow_char)
    if trim_type:
        q = q.filter(ValveCvStk.trim_type == trim_type)
    if pressure_rating:
        q = q.filter(ValveCvStk.pressure_rating == pressure_rating)
    if seat_type:
        q = q.filter(ValveCvStk.seat_type == seat_type)

    rows = q.all()
    return {
        "total": len(rows),
        "items": [
            {
                "id": r.id,
                "series_code": r.series_code,
                "dn_label": r.dn_label,
                "trim_label": r.trim_label,
                "flow_char": r.flow_char,
                "trim_type": r.trim_type,
                "pressure_rating": r.pressure_rating,
                "seat_type": r.seat_type,
                "rated_cv": r.rated_cv,
                "stroke_value": r.stroke_value,
                "stroke_unit": r.stroke_unit,
            }
            for r in rows
        ],
    }


@router.get("/{part1}/{part2}/cv-stk", summary="按约束条件查询额定Cv和行程 (斜杠系列)")
def get_cv_stk_slash(
    part1: str, part2: str,
    dn_label: str = "",
    trim_label: str = "",
    flow_char: str = "",
    trim_type: str = "",
    pressure_rating: str = "",
    seat_type: str = "",
    db: Session = Depends(get_db),
):
    """处理含斜杠的系列代码，如 BV310/320"""
    series_code = f"{part1}/{part2}"
    return get_cv_stk(series_code, dn_label, trim_label, flow_char, trim_type, pressure_rating, seat_type, db)
