"""管道规格数据 API (pipe_data 表) + ASME B31.3 管道壁厚 / SCH 推荐

SCH 推荐依据：
  ASME B31.3-2012 §304.1.2 式(3a)  t = P·D / (2·(S·E·W + P·Y))
  所需成品壁厚            t_req = (t + CA) / (1 - 制造负偏差)
  S 取 Table A-1 该材质在设计温度下的基本许用应力（线性插值）
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import PipeData, PipeMaterialAllowableStress
from app.schemas import (
    AllowableStressOut,
    PipeMaterialSummaryOut,
    SchCandidateOut,
    SuggestSchOut,
)

router = APIRouter(prefix="/pipe-data", tags=["管道规格数据"])


@router.get("")
def list_pipe_data(
    schedule: str = Query(None, description="按 SCH 过滤, 如 40/80/STD"),
    db: Session = Depends(get_db),
):
    """查询管道规格列表, 返回 lookup_key + nps_label + schedule 等信息

    用于前端「管道规格」下拉框, 选中后自动填充「管道尺寸」(nps_label)。
    """
    q = db.query(PipeData).order_by(PipeData.dn_mm, PipeData.schedule)
    if schedule:
        q = q.filter(PipeData.schedule == schedule)
    rows = q.all()
    return [
        {
            "id": r.id,
            "lookup_key": r.lookup_key,
            "nps_label": r.nps_label,
            "dn_mm": r.dn_mm,
            "schedule": r.schedule,
            "od_in": r.od_in,
            "od_mm": r.od_mm,
            "thk_in": r.thk_in,
            "thk_mm": r.thk_mm,
            "id_in": r.id_in,
            "id_mm": r.id_mm,
        }
        for r in rows
    ]


@router.get("/schedules")
def list_schedules(db: Session = Depends(get_db)):
    """获取所有可用的 SCH 等级列表"""
    rows = (
        db.query(PipeData.schedule)
        .filter(PipeData.schedule.isnot(None))
        .distinct()
        .order_by(PipeData.schedule)
        .all()
    )
    return [r[0] for r in rows if r[0]]


# ---------------------------------------------------------------------------
# ASME B31.3 Table A-1 许用应力
# ---------------------------------------------------------------------------
@router.get("/materials", response_model=list[PipeMaterialSummaryOut])
def list_materials(db: Session = Depends(get_db)):
    """获取许用应力表中已收录的管材清单（供前端下拉框）"""
    rows = (
        db.query(PipeMaterialAllowableStress)
        .order_by(PipeMaterialAllowableStress.material_code)
        .all()
    )
    if not rows:
        return []

    summary: dict[str, dict] = {}
    for r in rows:
        item = summary.setdefault(
            r.material_code,
            {
                "material_code": r.material_code,
                "material_group": r.material_group,
                "min_temp_c": r.temp_c,
                "max_temp_c": r.temp_c,
                "max_use_temp_c": r.max_use_temp_c,
                "temp_points": 0,
                "notes": r.notes,
            },
        )
        item["min_temp_c"] = min(item["min_temp_c"], r.temp_c)
        item["max_temp_c"] = max(item["max_temp_c"], r.temp_c)
        item["temp_points"] += 1
    return sorted(summary.values(), key=lambda x: x["material_code"])


def _lookup_stress(rows: list, temp_c: float) -> tuple[float, bool, float, float]:
    """在材质温度曲线上线性插值，返回 (S, 是否插值, 下界温度, 上界温度)"""
    pts = sorted((r.temp_c, r.s_mpa) for r in rows)
    if temp_c < pts[0][0]:
        # 低于表内最低温度点: 按最低温度点的许用应力取值（不插值, 不外推）
        return pts[0][1], False, pts[0][0], pts[0][0]
    if temp_c > pts[-1][0]:
        raise HTTPException(
            400,
            f"设计温度 {temp_c}°C 超出该材质许用应力表覆盖范围（最高 {pts[-1][0]}°C），"
            f"高温工况请改用合金钢或不锈钢",
        )
    for t, s in pts:
        if temp_c == t:
            return s, False, t, t
    for i in range(len(pts) - 1):
        t0, s0 = pts[i]
        t1, s1 = pts[i + 1]
        if t0 <= temp_c <= t1:
            ratio = (temp_c - t0) / (t1 - t0)
            return round(s0 + ratio * (s1 - s0), 2), True, t0, t1
    return pts[-1][1], False, pts[-1][0], pts[-1][0]


@router.get("/allowable-stress", response_model=AllowableStressOut)
def get_allowable_stress(
    material_code: str = Query(..., description="材质代码, 如 A106-B / A216-WCB / TP304"),
    temp_c: float = Query(..., description="金属设计温度 °C"),
    db: Session = Depends(get_db),
):
    """查询指定材质在指定温度下的基本许用应力 S (MPa)，两点之间线性插值"""
    rows = (
        db.query(PipeMaterialAllowableStress)
        .filter(PipeMaterialAllowableStress.material_code == material_code)
        .all()
    )
    if not rows:
        raise HTTPException(404, f"许用应力表中不存在材质 {material_code}")

    max_use = rows[0].max_use_temp_c
    if max_use is not None and temp_c > max_use:
        raise HTTPException(
            400,
            f"材质 {material_code} 最高使用温度 {max_use}°C，设计温度 {temp_c}°C 超限"
            f"（碳钢石墨化/蠕变限制），请改用 A335 P11/P22 或奥氏体不锈钢",
        )

    s, interp, t0, t1 = _lookup_stress(rows, temp_c)
    return {
        "material_code": material_code,
        "temp_c": temp_c,
        "s_mpa": s,
        "interpolated": interp,
        "lower_temp_c": t0,
        "upper_temp_c": t1,
        "max_use_temp_c": max_use,
    }


# ---------------------------------------------------------------------------
# SCH 推荐
# ---------------------------------------------------------------------------
def _temp_factor_y(material_group: str | None, temp_c: float) -> float:
    """ASME B31.3 Table 304.1.1 温度折算系数 Y

    铁素体钢(碳钢/低合金钢) 与 奥氏体不锈钢 分档不同，此处按材料组近似取档。
    仅适用于 t < D/6 的薄壁工况（本接口的压力等级下均满足）。
    """
    is_austenitic = bool(material_group and "奥氏体" in material_group)
    if is_austenitic:
        if temp_c <= 593:
            return 0.4
        if temp_c <= 621:
            return 0.5
        return 0.7
    # 铁素体钢
    if temp_c <= 482:
        return 0.4
    if temp_c <= 538:
        return 0.5
    if temp_c <= 621:
        return 0.7
    return 0.7


@router.get("/suggest-sch", response_model=SuggestSchOut)
def suggest_schedule(
    dn_mm: int = Query(..., description="公制通径 DN mm, 如 50"),
    pressure_mpa: float = Query(..., gt=0, description="设计压力 (表压) MPa"),
    temp_c: float = Query(..., description="设计温度 °C"),
    material_code: str = Query(..., description="管材代码, 如 A106-B"),
    weld_factor_e: float = Query(1.0, gt=0, le=1.0, description="焊缝系数 E：无缝管 1.0，焊管 0.85~0.95"),
    temp_factor_y: float | None = Query(None, description="温度折算系数 Y；留空则按 B31.3 Table 304.1.1 自动取值"),
    corrosion_allowance_mm: float = Query(1.5, ge=0, description="腐蚀裕量 CA mm"),
    mill_tolerance: float = Query(0.125, ge=0, lt=1, description="制造负偏差（无缝管通常 12.5%）"),
    db: Session = Depends(get_db),
):
    """按 ASME B31.3 反算最小壁厚，并在同一 DN 下推荐最轻的合格 SCH"""
    if not (material_code or "").strip():
        raise HTTPException(422, "缺少参数：管道材质 material_code")

    mat_rows = (
        db.query(PipeMaterialAllowableStress)
        .filter(PipeMaterialAllowableStress.material_code == material_code)
        .all()
    )
    if not mat_rows:
        codes = [
            r[0] for r in db.query(PipeMaterialAllowableStress.material_code)
            .distinct().order_by(PipeMaterialAllowableStress.material_code).all()
        ]
        raise HTTPException(
            404,
            f"许用应力表中不存在材质 {material_code}；可选材质（共 {len(codes)} 种）："
            f"{'、'.join(codes)}",
        )

    max_use = mat_rows[0].max_use_temp_c
    if max_use is not None and temp_c > max_use:
        raise HTTPException(
            400,
            f"材质 {material_code} 最高使用温度 {max_use}°C，设计温度 {temp_c}°C 超限，"
            f"请改用 A335 P11/P22 或奥氏体不锈钢",
        )

    s_mpa, _, stress_t_lo, _ = _lookup_stress(mat_rows, temp_c)
    y = temp_factor_y if temp_factor_y is not None else _temp_factor_y(mat_rows[0].material_group, temp_c)

    pipes_any = (
        db.query(PipeData)
        .filter(PipeData.dn_mm == dn_mm)
        .order_by(PipeData.thk_mm.asc())
        .all()
    )
    if not pipes_any:
        raise HTTPException(
            404,
            f"pipe_data 中不存在 DN{dn_mm} 的管道规格，无法推荐 SCH；"
            f"请先在管道数据中补充该公称通径的外径/壁厚数据",
        )
    pipes = [p for p in pipes_any if p.thk_mm and p.thk_mm > 0]
    if not pipes:
        schedules = "、".join(sorted({(p.schedule or "?") for p in pipes_any}))
        raise HTTPException(
            400,
            f"DN{dn_mm} 的管道规格（SCH：{schedules}）缺少壁厚 thk_mm 数据，无法计算所需壁厚",
        )

    od_mm = pipes[0].od_mm
    if not od_mm:
        raise HTTPException(
            400,
            f"DN{dn_mm} 的管道规格 {pipes[0].schedule or ''} 缺少外径 od_mm 数据，"
            f"无法按 B31.3 式(3a) 计算壁厚",
        )

    # B31.3 式(3a)：t = P·D / (2·(S·E·W + P·Y))，W=1（无纵向焊缝强度折减）
    t_pressure = pressure_mpa * od_mm / (2 * (s_mpa * weld_factor_e + pressure_mpa * y))
    t_req = (t_pressure + corrosion_allowance_mm) / (1 - mill_tolerance)

    candidates = []
    recommended = None
    for p in pipes:
        ok = p.thk_mm >= t_req
        if ok and recommended is None:
            recommended = p.schedule
        candidates.append(
            SchCandidateOut(
                schedule=p.schedule,
                thk_mm=p.thk_mm,
                id_mm=p.id_mm,
                margin_mm=round(p.thk_mm - t_req, 3),
                ok=ok,
            )
        )

    if t_pressure >= od_mm / 6:
        note = "计算壁厚 t ≥ D/6，已超出式(3a) 适用范围，需按 B31.3 式(3b) 另行核算"
    elif recommended:
        note = (
            f"按 B31.3 式(3a) 计算：t={round(t_pressure, 3)}mm，"
            f"加腐蚀裕 {corrosion_allowance_mm}mm 并计入 {mill_tolerance * 100:.1f}% 负偏差后需 "
            f"t_req={round(t_req, 3)}mm；推荐 {recommended}"
        )
    else:
        note = (
            f"按 B31.3 式(3a) 需 t_req={round(t_req, 3)}mm，"
            f"DN{dn_mm} 最大 SCH 壁厚 {pipes[-1].thk_mm}mm 仍不满足，请提高压力等级用材或加大壁厚"
        )

    if temp_c < stress_t_lo:
        note = (
            f"设计温度 {temp_c}°C 低于许用应力表最低温度点 {stress_t_lo}°C，"
            f"已按 {stress_t_lo}°C 的许用应力 {s_mpa} MPa 取值；" + note
        )

    return {
        "dn_mm": dn_mm,
        "nps_label": pipes[0].nps_label,
        "od_mm": od_mm,
        "material_code": material_code,
        "design_pressure_mpa": pressure_mpa,
        "design_temp_c": temp_c,
        "allowable_stress_mpa": s_mpa,
        "weld_factor_e": weld_factor_e,
        "temp_factor_y": y,
        "corrosion_allowance_mm": corrosion_allowance_mm,
        "mill_tolerance": mill_tolerance,
        "pressure_thickness_mm": round(t_pressure, 4),
        "required_thk_mm": round(t_req, 4),
        "recommended_schedule": recommended,
        "candidates": candidates,
        "note": note,
    }


# ---------------------------------------------------------------------------
# 种子数据：ASME B31.3 Table A-1（常用管材 S(T)）
# 数据已按 参考文件/ASME_B31.3_Table_A-1_S_T.csv 人工复核后内置
# ---------------------------------------------------------------------------
# 温度点 °C → 许用应力 MPa
_C_G11 = [
    (38, 137.9), (93, 137.9), (149, 137.9), (204, 137.2), (260, 131.0),
    (316, 123.4), (343, 119.3), (371, 115.1), (399, 95.8), (427, 78.6),
    (454, 60.0), (482, 40.7), (510, 27.6), (538, 17.2), (566, 11.0), (593, 6.9),
]
_C_G11_LT = [
    (38, 126.2), (93, 126.2), (149, 122.0), (204, 117.9), (260, 112.4),
    (316, 105.5), (343, 102.0), (371, 98.6), (399, 89.6), (427, 74.5),
    (454, 60.0), (482, 40.7), (510, 27.6), (538, 17.2), (566, 11.0), (593, 6.9),
]
_C_P11 = [
    (38, 137.9), (93, 137.9), (149, 131.0), (204, 117.2), (260, 106.9),
    (316, 100.0), (371, 88.9), (427, 79.3), (482, 46.2),
]
_C_P22 = [
    (38, 137.9), (93, 137.9), (149, 131.0), (204, 117.2), (260, 106.9),
    (316, 100.0), (371, 90.3), (427, 86.2), (482, 55.2),
]
_C_SS = [
    (38, 137.9), (93, 137.9), (149, 137.9), (204, 128.2), (260, 120.7),
    (316, 114.5), (343, 111.7), (371, 108.9), (399, 106.9), (427, 104.8),
    (454, 102.7), (482, 100.7),
]
_C_SSL = [
    (38, 115.1), (93, 115.1), (149, 115.1), (204, 108.9), (260, 101.4),
    (316, 96.5), (343, 94.5), (371, 93.1), (399, 91.7), (427, 89.6),
    (454, 88.3), (482, 86.9),
]
_C_SS316 = [
    (38, 137.9), (93, 137.9), (149, 137.9), (204, 133.1), (260, 124.1),
    (316, 117.2), (343, 114.5), (371, 112.4), (399, 111.0), (427, 109.6),
    (454, 108.2), (482, 107.6),
]
_C_SS316L = [
    (38, 115.1), (93, 115.1), (149, 115.1), (204, 108.2), (260, 102.0),
    (316, 96.5), (343, 94.5), (371, 93.1), (399, 91.0), (427, 88.9),
    (454, 87.6), (482, 85.5),
]
_C_TP321 = [
    (38, 137.9), (93, 137.9), (149, 137.9), (204, 137.9), (260, 133.1),
    (316, 126.2), (343, 123.4), (371, 120.7),
]
_C_TP347 = [
    (38, 137.9), (93, 137.9), (149, 137.9), (204, 137.9), (260, 137.9),
    (316, 133.1), (343, 131.0), (371, 128.9),
]

# (material_code, material_group, curve, min_use_temp_c, max_use_temp_c, notes)
_SEED_MATERIALS = [
    ("A106-B", "Group 1.1", _C_G11, -29, 593, "无缝碳钢管，最常用"),
    ("A53-B", "Group 1.1", _C_G11, -29, 593, "焊接/无缝碳钢管"),
    ("API5L-B", "Group 1.1", _C_G11, -29, 593, "API 5L 碳钢管"),
    ("A333-6", "Group 1.1", _C_G11, -46, 593, "低温无缝碳钢管"),
    ("A334-6", "Group 1.1", _C_G11, -46, 593, "低温换热管"),
    ("A216-WCB", "Group 1.1", _C_G11, -29, 427, "铸钢阀体，石墨化上限 427°C"),
    ("A105", "Group 1.1", _C_G11, -29, 427, "碳钢锻件(法兰/小口径)，石墨化上限 427°C"),
    ("A350-LF2", "Group 1.1", _C_G11, -46, 427, "低温碳钢锻件"),
    ("A333-1", "Group 1.1 低强", _C_G11_LT, -46, 593, "低温碳钢管(55ksi 级)"),
    ("A334-1", "Group 1.1 低强", _C_G11_LT, -46, 593, "低温换热管(55ksi 级)"),
    ("A335-P11", "Group 1.2 P11", _C_P11, -29, 593, "1.25Cr-0.5Mo 高温管道"),
    ("A335-P22", "Group 1.2 P22", _C_P22, -29, 649, "2.25Cr-1Mo 高温管道"),
    ("TP304", "奥氏体不锈钢", _C_SS, -196, 815, "A312 TP304 无缝不锈钢管"),
    ("TP304L", "奥氏体不锈钢", _C_SSL, -196, 815, "A312 TP304L 低碳不锈钢管"),
    ("TP316", "奥氏体不锈钢", _C_SS316, -196, 815, "A312 TP316 含钼不锈钢管"),
    ("TP316L", "奥氏体不锈钢", _C_SS316L, -196, 815, "A312 TP316L 低碳含钼不锈钢管"),
    ("TP321", "奥氏体不锈钢", _C_TP321, -196, 815, "Ti 稳定不锈钢管(表内仅至 371°C)"),
    ("TP347", "奥氏体不锈钢", _C_TP347, -196, 815, "Nb 稳定不锈钢管(表内仅至 371°C)"),
]


def seed_pipe_material_stress(db: Session):
    """向 pipe_material_allowable_stress 表注入 ASME B31.3 Table A-1 种子数据

    幂等：表非空则跳过；按 (material_code, temp_c) upsert，不做全表 DELETE。
    """
    existing = {
        (r.material_code, r.temp_c)
        for r in db.query(
            PipeMaterialAllowableStress.material_code,
            PipeMaterialAllowableStress.temp_c,
        ).all()
    }
    added = 0
    for code, group, curve, tmin, tmax, notes in _SEED_MATERIALS:
        for temp_c, s_mpa in curve:
            if (code, float(temp_c)) in existing:
                continue
            db.add(
                PipeMaterialAllowableStress(
                    material_code=code,
                    material_group=group,
                    temp_c=float(temp_c),
                    s_mpa=float(s_mpa),
                    min_use_temp_c=tmin,
                    max_use_temp_c=tmax,
                    notes=notes,
                )
            )
            added += 1
    if added:
        db.commit()
