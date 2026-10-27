"""选型模块接口 (P3.1)

依据: docs/选型模块前端界面设计.md §11 数据契约
      docs/选型模块实施计划.md P3 任务 3.1

端点:
  POST /selection/run                运行选型(四阶段流水线)
  GET  /selection/rules              规则库列表(只读)
  GET  /selection/records            历史记录列表
  GET  /selection/records/{id}       单条记录详情
  POST /selection/records            创建记录(保存快照)
  POST /selection/records/{id}/apply 应用记录(标记选中项; ValveConfig/ProcessCase 回填由 P4.1 实现)
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.calc.selector import ValveSelector
from app.models import SelectionRecord, SelectionRule
from app.schemas import (
    SelectionInput,
    SelectionResultOut,
    SelectionRuleOut,
    SelectionRecordCreate,
    SelectionRecordOut,
)

router = APIRouter(prefix="/selection", tags=["选型"])

# 候选清单返回上限(引擎输出可能包含数百个组合, 前端表格与响应体都需要收敛)
MAX_CANDIDATES = 50


# ---------------------------------------------------------------------------
# 辅助: 警告聚合
# ---------------------------------------------------------------------------
def _warn_group(w: str) -> Optional[str]:
    """识别「逐候选」类警告的归并键（候选前缀含空格/斜杠等, 用子串匹配而非正则）。"""
    if "缺少 cv_min" in w:
        return "缺少 cv_min，可调比未知"
    if "曲线解析失败" in w:
        return "曲线解析失败"
    if "可调比" in w and "< 要求" in w:
        return "可调比不满足要求"
    if "阀前压力" in w and "允许值" in w:
        return "阀前压力超过材质温压允许值"
    if "缺少最大允许压差数据" in w:
        return "系列缺少最大允许压差数据，未校核"
    return None


def _compact_warnings(warnings: list[str]) -> list[str]:
    """同类逐候选警告归并为单条汇总, 避免刷屏(如数百条 '缺少 cv_min')。

    非重复类警告(流态、规则命中、介质兜底等)原样保留。
    """
    groups: dict[str, list[str]] = {}
    others: list[str] = []
    for w in warnings:
        key = _warn_group(w)
        if key:
            groups.setdefault(key, []).append(w)
        else:
            others.append(w)

    out: list[str] = []
    for key, items in groups.items():
        if len(items) == 1:
            out.append(items[0])
        else:
            out.append(f"{key}（共 {len(items)} 项，示例: {items[0]}）")
    return out + others


# ---------------------------------------------------------------------------
# 辅助: Text JSON 字段反序列化
# ---------------------------------------------------------------------------
def _rule_to_out(rule: SelectionRule) -> dict:
    """SelectionRule (Text JSON 字段) → SelectionRuleOut (dict 字段)"""
    return {
        "id": rule.id,
        "rule_code": rule.rule_code,
        "rule_name": rule.rule_name,
        "category": rule.category,
        "target_series": rule.target_series,
        "condition_expr": json.loads(rule.condition_expr) if rule.condition_expr else None,
        "condition_op": rule.condition_op,
        "action": rule.action,
        "action_payload": json.loads(rule.action_payload) if rule.action_payload else None,
        "priority": rule.priority,
        "source_ref": rule.source_ref,
        "is_active": rule.is_active,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def _record_to_out(rec: SelectionRecord) -> dict:
    """SelectionRecord (Text JSON 字段) → SelectionRecordOut (dict 字段)"""
    return {
        "id": rec.id,
        "valve_id": rec.valve_id,
        "project_id": rec.project_id,
        "input_snapshot": json.loads(rec.input_snapshot) if rec.input_snapshot else None,
        "candidates_json": json.loads(rec.candidates_json) if rec.candidates_json else None,
        "selected_series": rec.selected_series,
        "selected_config": json.loads(rec.selected_config) if rec.selected_config else None,
        "applied_rule_ids": rec.applied_rule_ids,
        "created_at": rec.created_at,
        "created_by": rec.created_by,
    }


# ---------------------------------------------------------------------------
# 选型运行
# ---------------------------------------------------------------------------
@router.post("/run", response_model=SelectionResultOut)
def run_selection(payload: SelectionInput, db: Session = Depends(get_db)):
    """运行选型四阶段流水线

    - 必填: media, flow_rate, p1, p2, t1
    - 多工况: 传入 cases 时按全部工况综合判断（同一阀型须同时满足每个工况）
    - 返回: 候选清单(按评分+开度+额定 Cv 排序) + 命中规则数 + 警告
    """
    selector = ValveSelector(db, stages=1)

    # 多工况：逐工况运行引擎后取交集, 按最不利开度综合排序
    case_list = payload.cases or []
    if len(case_list) > 1:
        result = _run_multi_case(selector, payload, case_list)
        result.candidates = result.candidates[:MAX_CANDIDATES]
        result.warnings = _compact_warnings(result.warnings)
        return result

    # 字段校验（先换算为内部单位, 避免不同压力单位直接比较）
    from app.calc.units import convert

    _validate_single(payload)
    try:
        result = selector.select(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"选型引擎异常: {e}")

    # 收敛响应体: 候选截取 Top N(引擎已排序), 警告同类归并
    result.candidates = result.candidates[:MAX_CANDIDATES]
    result.warnings = _compact_warnings(result.warnings)
    return result


# ---------------------------------------------------------------------------
# 多工况综合选型
# ---------------------------------------------------------------------------
def _validate_single(inp: SelectionInput) -> None:
    """单工况必填校验（压力换算后比较）"""
    from app.calc.units import convert

    if inp.flow_rate is None or inp.flow_rate <= 0:
        raise HTTPException(422, "flow_rate 必须大于 0")
    if inp.p1 is None or inp.p2 is None:
        raise HTTPException(422, "p1/p2 必填")
    p1 = convert(inp.p1, inp.p1_unit, "pressure")
    p2 = convert(inp.p2, inp.p2_unit, "pressure")
    if p1 is None or p2 is None:
        raise HTTPException(422, "p1/p2 单位无法解析")
    if p1 <= p2:
        raise HTTPException(422, "p1 必须大于 p2")
    if inp.t1 is None:
        raise HTTPException(422, "t1 必填")


def _case_input(payload: SelectionInput, cs) -> SelectionInput:
    """把单个工况叠加到公共参数上, 构造独立的单工况选型输入"""
    data = payload.model_dump(exclude={"cases", "main_case_index"})
    data.update({
        "media": cs.media or payload.media,
        "fluid_name": cs.fluid_name or payload.fluid_name,
        "flow_rate": cs.flow_rate,
        "flow_rate_unit": cs.flow_rate_unit or payload.flow_rate_unit,
        "p1": cs.p1, "p1_unit": cs.p1_unit or payload.p1_unit,
        "p2": cs.p2, "p2_unit": cs.p2_unit or payload.p2_unit,
        "t1": cs.t1, "t1_unit": cs.t1_unit or payload.t1_unit,
        "dp": cs.dp,
        "pipe_size": cs.pipe_size,
        "pipe_size_unit": cs.pipe_size_unit or payload.pipe_size_unit,
        "cv_required": cs.cv_required if cs.cv_required is not None else payload.cv_required,
    })
    return SelectionInput(**data)


def _is_case_complete(inp: SelectionInput) -> bool:
    from app.calc.units import convert

    if inp.flow_rate is None or inp.flow_rate <= 0:
        return False
    if inp.p1 is None or inp.p2 is None or inp.t1 is None:
        return False
    p1 = convert(inp.p1, inp.p1_unit, "pressure")
    p2 = convert(inp.p2, inp.p2_unit, "pressure")
    return p1 is not None and p2 is not None and p1 > p2


def _cand_key(c) -> tuple:
    """候选唯一键（同一口径/阀芯/特性/额定Cv 视为同一阀型）"""
    return (c.series_code, c.dn_label, c.trim_label, c.flow_char, c.rated_cv)


def _run_multi_case(selector: ValveSelector, payload: SelectionInput, case_list: list) -> SelectionResultOut:
    """逐工况选型后取交集：同一阀型必须同时出现在每个工况的可行解中"""
    warnings: list[str] = []
    main_idx = payload.main_case_index or 0
    if not (0 <= main_idx < len(case_list)):
        main_idx = 0

    per_case: dict[int, SelectionResultOut] = {}
    for i, cs in enumerate(case_list):
        sub = _case_input(payload, cs)
        if not _is_case_complete(sub):
            warnings.append(f"工况 {i + 1} 参数不完整（介质/流量/P1/P2/T1），已跳过综合判断")
            continue
        try:
            per_case[i] = selector.select(sub)
        except Exception as e:
            warnings.append(f"工况 {i + 1} 选型异常: {e}")
            continue

    if not per_case:
        raise HTTPException(422, "没有可参与选型的完整工况")
    if main_idx not in per_case:
        main_idx = next(iter(per_case))

    maps = {i: {_cand_key(c): c for c in r.candidates} for i, r in per_case.items()}
    common = set(next(iter(maps.values())).keys())
    for m in maps.values():
        common &= set(m.keys())

    fallback = False
    if not common:
        fallback = True
        common = set(maps[main_idx].keys())
        warnings.append("没有同时满足全部工况的阀型，已按主工况单独推荐")

    # 以主工况的候选顺序为基准, 逐个聚合各工况开度
    merged = []
    for c in per_case[main_idx].candidates:
        key = _cand_key(c)
        if key not in common:
            continue
        openings = []
        detail = []
        for i, res in sorted(maps.items()):
            sub_c = res.get(key)
            if sub_c is None:
                continue
            op = sub_c.opening
            detail.append({
                "index": i,
                "case_no": (case_list[i].case_no or (i + 1)),
                "case_name": case_list[i].case_name or f"工况 {i + 1}",
                "opening": op,
                "is_main": i == main_idx,
            })
            if op is not None:
                openings.append(op)
        base = c
        main_op = maps[main_idx][key].opening
        merged.append({
            "cand": base,
            "opening": main_op,
            "opening_max": max(openings) if openings else None,
            "opening_min": min(openings) if openings else None,
            "case_openings": detail,
            "score": max((m[key].score for m in maps.values() if key in m), default=0),
            "rules": sorted({r for m in maps.values() if key in m for r in m[key].applied_rules}),
        })

    # 排序: 评分降序 → 最不利开度接近 70 → 额定 Cv 升序
    merged.sort(key=lambda x: (
        -x["score"],
        abs((x["opening_max"] if x["opening_max"] is not None else 999.0) - 70.0),
        (x["cand"].rated_cv or 0.0),
    ))

    from app.schemas import CandidateOut

    out = []
    for rank, m in enumerate(merged, start=1):
        c = m["cand"]
        out.append(CandidateOut(
            rank=rank,
            series_code=c.series_code,
            series_name=c.series_name,
            dn_label=c.dn_label,
            trim_label=c.trim_label,
            flow_char=c.flow_char,
            rated_cv=c.rated_cv,
            cv_min=c.cv_min,
            opening=m["opening"],
            opening_max=m["opening_max"],
            opening_min=m["opening_min"],
            case_openings=m["case_openings"],
            rangeability=c.rangeability,
            score=m["score"],
            applied_rules=m["rules"],
            flags=c.flags or None,
        ))

    if fallback:
        warnings.append("综合候选为空：可能各工况所需 Cv 差异过大，建议分阀选型")

    base_warnings = list(per_case[main_idx].warnings)
    return SelectionResultOut(
        candidates=out,
        applied_rule_count=len({r for m in merged for r in m["rules"]}),
        warnings=list(dict.fromkeys(warnings + base_warnings)),
    )


# ---------------------------------------------------------------------------
# 规则库 (只读)
# ---------------------------------------------------------------------------
@router.get("/rules", response_model=list[SelectionRuleOut])
def list_rules(
    category: Optional[str] = Query(None, description="scope/constraint/preference/post_filter"),
    target_series: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    keyword: Optional[str] = Query(None, description="模糊匹配 rule_code/rule_name/source_ref"),
    db: Session = Depends(get_db),
):
    q = db.query(SelectionRule)
    if category:
        q = q.filter(SelectionRule.category == category)
    if target_series:
        q = q.filter(SelectionRule.target_series == target_series)
    if is_active is not None:
        q = q.filter(SelectionRule.is_active == is_active)
    if keyword:
        kw = f"%{keyword}%"
        from sqlalchemy import or_
        q = q.filter(or_(
            SelectionRule.rule_code.like(kw),
            SelectionRule.rule_name.like(kw),
            SelectionRule.source_ref.like(kw),
        ))
    rows = q.order_by(SelectionRule.priority, SelectionRule.rule_code).all()
    return [_rule_to_out(r) for r in rows]


# ---------------------------------------------------------------------------
# 历史记录
# ---------------------------------------------------------------------------
@router.get("/records", response_model=list[SelectionRecordOut])
def list_records(
    valve_id: int = Query(..., description="位号 ID"),
    db: Session = Depends(get_db),
):
    rows = (db.query(SelectionRecord)
              .filter(SelectionRecord.valve_id == valve_id)
              .order_by(SelectionRecord.created_at.desc())
              .all())
    return [_record_to_out(r) for r in rows]


@router.get("/records/{rid}", response_model=SelectionRecordOut)
def get_record(rid: int, db: Session = Depends(get_db)):
    rec = db.get(SelectionRecord, rid)
    if not rec:
        raise HTTPException(404, "选型记录不存在")
    return _record_to_out(rec)


@router.post("/records", response_model=SelectionRecordOut)
def create_record(payload: SelectionRecordCreate, db: Session = Depends(get_db)):
    """创建选型记录(保存快照)

    - 仅归档 input_snapshot / candidates_json, 不应用任何配置
    """
    rec = SelectionRecord(
        valve_id=payload.valve_id,
        project_id=payload.project_id,
        input_snapshot=json.dumps(payload.input_snapshot, ensure_ascii=False) if payload.input_snapshot else None,
        candidates_json=json.dumps(payload.candidates_json, ensure_ascii=False) if payload.candidates_json else None,
        selected_series=payload.selected_series,
        selected_config=json.dumps(payload.selected_config, ensure_ascii=False) if payload.selected_config else None,
        applied_rule_ids=payload.applied_rule_ids,
        created_by="工程师",
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _record_to_out(rec)


@router.post("/records/{rid}/apply", response_model=SelectionRecordOut)
def apply_record(rid: int, payload: dict, db: Session = Depends(get_db)):
    """应用选型记录(标记选中项)

    P3 阶段: 仅更新 SelectionRecord.selected_series / selected_config
    P4 阶段: 增加回填 ValveConfig + ProcessCase (幂等 upsert)
    """
    rec = db.get(SelectionRecord, rid)
    if not rec:
        raise HTTPException(404, "选型记录不存在")

    selected_series = payload.get("selected_series")
    selected_config = payload.get("selected_config")
    if not selected_series:
        raise HTTPException(422, "selected_series 必填")

    rec.selected_series = selected_series
    if selected_config is not None:
        rec.selected_config = json.dumps(selected_config, ensure_ascii=False)
    db.commit()
    db.refresh(rec)
    return _record_to_out(rec)
