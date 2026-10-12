"""计算版本 + 工艺工况 + 计算执行接口

核心: 同一位号多次计算以版本号(version_no)为索引，新版本自动递增并置为当前。
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.models import (
    Valve, Calculation, ValveConfig, ProcessCase, CalcResult, Fluid
)
from app.schemas import (
    CalculationCreate, CalculationOut,
    ValveConfigSchema, ProcessCaseSchema, ProcessCaseOut,
    CalculateRequest, CaseResultOut, CalcResultSave,
)
from app.calc.engine import calculate_case
from app.calc.cv_core import ValveCoeffs, FactorCurves
from app.calc.units import convert_process_case

router = APIRouter(prefix="/valves/{vid}/calculations", tags=["计算版本"])


def _parse_curve_coeffs(cfg) -> "FactorCurves | None":
    """从 ValveConfig.curve_coeffs (JSON 字符串) 解析 FactorCurves"""
    raw = getattr(cfg, 'curve_coeffs', None)
    if not raw:
        return None
    if isinstance(raw, dict):
        return FactorCurves.from_dict(raw)
    try:
        return FactorCurves.from_dict(json.loads(raw))
    except Exception:
        return None


def _get_valve(db: Session, vid: int) -> Valve:
    v = db.get(Valve, vid)
    if not v:
        raise HTTPException(404, "位号不存在")
    return v


def _build_fluid_dict(db: Session, fluid_id: int | None, fluid_name_custom: str | None) -> dict:
    """组装计算引擎所需的 fluid 字典。

    约定：计算引擎 engine.calculate_case 只通过 fluid 字典获取"基础默认物性"，
    再结合 ProcessCase 的 override 字段（density_override / mw_override / gamma_override 等）
    得到最终工况物性。因此自定义介质只需要一个 fluid_name，其余全 None 也能正常运行——
    调用方必须在 ProcessCase 的 override 字段提供非 None 值。
    """
    if fluid_id is not None:
        fluid = db.get(Fluid, fluid_id)
        if not fluid:
            raise HTTPException(400, f"介质 id={fluid_id} 不存在")
        return {
            "fluid_name": fluid.fluid_name, "is_water": fluid.is_water,
            "default_state": fluid.default_state,
            "density_liquid": fluid.density_liquid, "density_gas": fluid.density_gas,
            "molecular_weight": fluid.molecular_weight, "cp_cv_ratio": fluid.cp_cv_ratio,
            "critical_pressure": fluid.critical_pressure, "vapor_pressure": fluid.vapor_pressure,
            "viscosity": fluid.viscosity,
        }
    # 自定义介质：只给名字，其余全 None
    name = (fluid_name_custom or "").strip() or "自定义介质"
    return {
        "fluid_name": name, "is_water": False,
        "default_state": None,
        "density_liquid": None, "density_gas": None,
        "molecular_weight": None, "cp_cv_ratio": None,
        "critical_pressure": None, "vapor_pressure": None,
        "viscosity": None,
    }


# ---------- 版本管理 ----------
@router.get("", response_model=list[CalculationOut])
def list_calculations(vid: int, db: Session = Depends(get_db)):
    _get_valve(db, vid)
    return db.query(Calculation).filter(Calculation.valve_id == vid).order_by(Calculation.version_no).all()


@router.post("", response_model=CalculationOut)
def create_calculation(vid: int, payload: CalculationCreate, db: Session = Depends(get_db)):
    _get_valve(db, vid)
    # 自动版本号
    max_ver = db.query(Calculation).filter(Calculation.valve_id == vid).count()
    new_ver = max_ver + 1
    # 取消旧版本的 is_current
    db.query(Calculation).filter(Calculation.valve_id == vid).update({Calculation.is_current: False})
    calc = Calculation(
        valve_id=vid, version_no=new_ver, version_label=payload.version_label or f"V{new_ver}",
        is_current=True, calc_standard=payload.calc_standard, remark=payload.remark,
        status="草稿",
    )
    db.add(calc)
    db.commit()
    db.refresh(calc)
    return calc


@router.get("/{cid}", response_model=dict)
def get_calculation(vid: int, cid: int, db: Session = Depends(get_db)):
    calc = db.get(Calculation, cid)
    if not calc or calc.valve_id != vid:
        raise HTTPException(404, "计算版本不存在")
    cfg = db.query(ValveConfig).filter(ValveConfig.calculation_id == cid).first()
    cases = db.query(ProcessCase).filter(ProcessCase.calculation_id == cid).order_by(ProcessCase.case_no).all()
    results = db.query(CalcResult).join(ProcessCase).filter(ProcessCase.calculation_id == cid).all()
    return {
        "calculation": CalculationOut.model_validate(calc).model_dump(),
        "valve_config": ValveConfigSchema.model_validate(cfg).model_dump() if cfg else None,
        "cases": [ProcessCaseOut.model_validate(c).model_dump() for c in cases],
        "results": {
            r.process_case_id: {
                "cv_required": r.cv_required, "cv_rated_selected": r.cv_rated_selected,
                "cv_opening": r.cv_opening, "flow_regime": r.flow_regime,
                "dp": r.dp, "dp_choked": r.dp_choked, "x": r.x, "x_t_eff": r.x_t_eff,
                "y": r.y, "fl_eff": r.fl_eff, "reynolds": r.reynolds, "fp": r.fp,
                "noise_dba": r.noise_dba, "noise_freq_peak": r.noise_freq_peak,
                "noise_method": r.noise_method, "status": r.status, "message": r.message,
                "detail": json.loads(r.detail) if r.detail else None,
                "calculated_at": r.calculated_at.isoformat() if r.calculated_at else None,
            } for r in results
        },
    }


@router.delete("/{cid}")
def delete_calculation(vid: int, cid: int, db: Session = Depends(get_db)):
    calc = db.get(Calculation, cid)
    if not calc or calc.valve_id != vid:
        raise HTTPException(404, "计算版本不存在")
    db.delete(calc)
    db.commit()
    return {"ok": True}


@router.put("/{cid}/set-current", response_model=CalculationOut)
def set_current(vid: int, cid: int, db: Session = Depends(get_db)):
    calc = db.get(Calculation, cid)
    if not calc or calc.valve_id != vid:
        raise HTTPException(404, "计算版本不存在")
    db.query(Calculation).filter(Calculation.valve_id == vid).update({Calculation.is_current: False})
    calc.is_current = True
    db.commit()
    db.refresh(calc)
    return calc


# ---------- 阀门配置 + 工况保存 ----------
@router.put("/{cid}/config", response_model=ValveConfigSchema)
def save_config(vid: int, cid: int, payload: ValveConfigSchema, db: Session = Depends(get_db)):
    calc = db.get(Calculation, cid)
    if not calc or calc.valve_id != vid:
        raise HTTPException(404, "计算版本不存在")
    cfg = db.query(ValveConfig).filter(ValveConfig.calculation_id == cid).first()
    # eqcv / curve_coeffs 字段: dict → JSON 字符串 (Text 列存储)
    payload_dict = payload.model_dump()
    if isinstance(payload_dict.get('eqcv'), dict):
        payload_dict['eqcv'] = json.dumps(payload_dict['eqcv'], ensure_ascii=False)
    if isinstance(payload_dict.get('curve_coeffs'), dict):
        payload_dict['curve_coeffs'] = json.dumps(payload_dict['curve_coeffs'], ensure_ascii=False)
    if cfg:
        for k, v in payload_dict.items():
            setattr(cfg, k, v)
    else:
        cfg = ValveConfig(calculation_id=cid, **payload_dict)
        db.add(cfg)

    # 回写阀门选型关键参数到 Valve 主表（供列表/详情页只读展示）
    valve = db.get(Valve, vid)
    if valve:
        if payload.valve_style:
            valve.valve_type = payload.valve_style
        if payload.port_diameter:
            valve.line_size = f"DN{int(payload.port_diameter)}"
        # 从已保存的工艺工况中取第一组的壁厚作为 line_schedule
        first_case = db.query(ProcessCase).filter(
            ProcessCase.calculation_id == cid,
            ProcessCase.is_active == True,
        ).order_by(ProcessCase.case_no).first()
        if first_case and first_case.pipe_wall:
            valve.line_schedule = f"{first_case.pipe_wall} mm"

    db.commit()
    db.refresh(cfg)
    return ValveConfigSchema.model_validate(cfg)


@router.put("/{cid}/cases", response_model=list[ProcessCaseOut])
def save_cases(vid: int, cid: int, cases: list[ProcessCaseSchema], db: Session = Depends(get_db)):
    """保存(覆盖)该版本下的工艺工况(最多5组)。

    保存前将所有录入参数按用户选择的单位转换为内部统一单位；
    单位选择记录存入 *_unit 字段供界面反显。
    """
    calc = db.get(Calculation, cid)
    if not calc or calc.valve_id != vid:
        raise HTTPException(404, "计算版本不存在")
    if len(cases) > 5:
        raise HTTPException(400, "单台阀门最多5组工艺工况")
    # 校验介质（允许自定义名；选了 fluid_id 则必须存在于基础库）
    for c in cases:
        if c.fluid_id is None and not (c.fluid_name_custom and c.fluid_name_custom.strip()):
            raise HTTPException(400, "介质不能为空（请选择基础库介质或填写自定义介质名）")
        if c.fluid_id is not None and not db.get(Fluid, c.fluid_id):
            raise HTTPException(400, f"介质 id={c.fluid_id} 不存在")
    # 清空旧工况
    db.query(ProcessCase).filter(ProcessCase.calculation_id == cid).delete()
    out = []
    for c in cases:
        raw = c.model_dump()
        # 转换单位（优先使用数据库中配置的单位字典）
        raw = convert_process_case(raw, db_session=db)
        pc = ProcessCase(calculation_id=cid, **raw)
        db.add(pc)
        db.flush()
        out.append(ProcessCaseOut.model_validate(pc))
    db.commit()
    return out


# ---------- 执行计算 ----------
@router.post("/{cid}/run", response_model=list[CaseResultOut])
def run_calculation(vid: int, cid: int, db: Session = Depends(get_db)):
    """对已保存的配置与工况执行 Cv+噪音 计算，结果落库并返回。"""
    calc = db.get(Calculation, cid)
    if not calc or calc.valve_id != vid:
        raise HTTPException(404, "计算版本不存在")
    cfg = db.query(ValveConfig).filter(ValveConfig.calculation_id == cid).first()
    cases = db.query(ProcessCase).filter(
        ProcessCase.calculation_id == cid,
        ProcessCase.is_active == True,
    ).order_by(ProcessCase.case_no).all()
    if not cfg or not cases:
        raise HTTPException(400, "缺少阀门配置或工艺工况，请先保存")

    # 阀门系数
    vc = ValveCoeffs(
        rated_cv=cfg.rated_cv or 0.0,
        fl=cfg.fl or 0.9, flp=cfg.flp, fp=cfg.fp,
        xt=cfg.xt or 0.72, xtp=cfg.xtp, fd=cfg.fd or 0.46,
        port_diameter=cfg.port_diameter, reduced_port=False,
        stages=cfg.stages or 1,
        factor_curves=_parse_curve_coeffs(cfg),
    )
    rated_sel = cfg.rated_cv or 0.0

    out: list[CaseResultOut] = []
    for pc in cases:
        fluid_dict = _build_fluid_dict(db, pc.fluid_id, pc.fluid_name_custom)
        cr = calculate_case(
            case_no=pc.case_no, case_name=pc.case_name or f"工况{pc.case_no}",
            fluid=fluid_dict, valve_coeffs=vc,
            p1=pc.p1 or 0, p2=pc.p2 or 0, t1=pc.t1 or 0,
            mass_flow=pc.flow_mass or 0, vol_flow=pc.flow_vol or 0, flow_unit=pc.flow_unit,
            fluid_state_override=pc.fluid_state_override,
            density_override=pc.density_override, viscosity_override=pc.viscosity_override,
            mw_override=pc.molecular_weight_override, gamma_override=pc.gamma_override,
            mass_flow_gas=pc.mass_flow_gas or 0, mass_flow_liquid=pc.mass_flow_liquid or 0,
            twophase_method=pc.twophase_method, density_gas=pc.density_gas or 0,
            density_liquid=pc.density_liquid or 0,
            pipe_diameter=pc.pipe_diameter or 0, pipe_wall=pc.pipe_wall or 0,
            distance=pc.distance or 1.0, rated_cv_select=rated_sel,
        )
        # 落库结果
        cv = cr.cv
        nr = cr.noise
        _upsert_result(db, pc.id, cv, nr, cr)
        out.append(CaseResultOut(**cr.to_dict()))

    calc.status = "已计算"
    calc.updated_at = datetime.now()

    # 回写阀门选型关键参数到 Valve 主表（每次执行计算自动同步）
    valve = db.get(Valve, vid)
    if valve:
        if cfg.valve_style:
            valve.valve_type = cfg.valve_style
        if cfg.port_diameter:
            valve.line_size = f"DN{int(cfg.port_diameter)}"
        # 用第一组活跃工况的壁厚作为 line_schedule
        if cases and cases[0].pipe_wall:
            valve.line_schedule = f"{cases[0].pipe_wall} mm"

    db.commit()
    return out


@router.post("/preview", response_model=list[CaseResultOut])
def preview_calculation(vid: int, req: CalculateRequest, db: Session = Depends(get_db)):
    """即时预览计算(不落库): 基于传入的配置与工况。"""
    _get_valve(db, vid)
    cfg = req.valve_config
    vc = ValveCoeffs(
        rated_cv=cfg.rated_cv or 0.0,
        fl=cfg.fl or 0.9, flp=cfg.flp, fp=cfg.fp,
        xt=cfg.xt or 0.72, xtp=cfg.xtp, fd=cfg.fd or 0.46,
        port_diameter=cfg.port_diameter, reduced_port=False,
        stages=cfg.stages or 1,
        factor_curves=_parse_curve_coeffs(cfg) if hasattr(cfg, 'curve_coeffs') else None,
    )
    rated_sel = req.rated_cv_select or cfg.rated_cv or 0.0
    out = []
    for c in req.cases:
        if not getattr(c, "is_active", True):
            continue
        fluid_dict = _build_fluid_dict(db, c.fluid_id, getattr(c, "fluid_name_custom", None))
        # 预览也做单位转换（内存态，不写库；优先查数据库单位定义）
        raw_c = convert_process_case(c.model_dump(), db_session=db)
        cr = calculate_case(
            case_no=raw_c["case_no"], case_name=raw_c.get("case_name") or f"工况{raw_c['case_no']}",
            fluid=fluid_dict, valve_coeffs=vc,
            p1=raw_c.get("p1") or 0, p2=raw_c.get("p2") or 0, t1=raw_c.get("t1") or 0,
            mass_flow=raw_c.get("flow_mass") or 0, vol_flow=raw_c.get("flow_vol") or 0, flow_unit=raw_c.get("flow_unit") or "mass",
            fluid_state_override=raw_c.get("fluid_state_override") or "",
            density_override=raw_c.get("density_override"), viscosity_override=raw_c.get("viscosity_override"),
            mw_override=raw_c.get("molecular_weight_override"), gamma_override=raw_c.get("gamma_override"),
            mass_flow_gas=raw_c.get("mass_flow_gas") or 0, mass_flow_liquid=raw_c.get("mass_flow_liquid") or 0,
            twophase_method=raw_c.get("twophase_method") or "additive", density_gas=raw_c.get("density_gas") or 0,
            density_liquid=raw_c.get("density_liquid") or 0,
            pipe_diameter=raw_c.get("pipe_diameter") or 0, pipe_wall=raw_c.get("pipe_wall") or 0,
            distance=raw_c.get("distance") or 1.0, rated_cv_select=rated_sel,
        )
        out.append(CaseResultOut(**cr.to_dict()))
    return out


def _upsert_result(db: Session, case_id: int, cv, nr, cr):
    """保存/更新单工况计算结果。"""
    r = db.query(CalcResult).filter(CalcResult.process_case_id == case_id).first()
    if not r:
        r = CalcResult(process_case_id=case_id)
        db.add(r)
    r.cv_required = cv.cv_required if cv else None
    r.cv_rated_selected = cv.cv_rated_selected if cv else None
    r.cv_opening = cv.opening_pct if cv else None
    r.flow_regime = cv.flow_regime if cv else None
    r.dp = cv.dp if cv else None
    r.dp_choked = cv.dp_choked if cv else None
    r.x = cv.x if cv else None
    r.x_t_eff = cv.x_t_eff if cv else None
    r.y = cv.y if cv else None
    r.fl_eff = cv.fl_eff if cv else None
    r.reynolds = cv.reynolds if cv else None
    r.fp = cv.fp if cv else None
    r.noise_dba = nr.noise_dba if nr else None
    r.noise_freq_peak = nr.noise_freq_peak if nr else None
    r.noise_method = nr.method if nr else None
    r.status = cr.status
    r.message = cr.message
    detail = {}
    if cv and cv.detail:
        detail["cv"] = cv.detail
    if nr and nr.detail:
        detail["noise"] = nr.detail
    r.detail = json.dumps(detail, ensure_ascii=False, default=str)
    r.calculated_at = datetime.now()
