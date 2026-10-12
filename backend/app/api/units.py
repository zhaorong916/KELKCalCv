"""单位字典接口

单位字典存储在数据库 unit_definitions 表中，
后端启动时若表为空则从 BUILTIN_UNITS 种子注入。
支持完整 CRUD，用户可动态增删改单位以调整前端下拉选项。

路由顺序说明: 固定路径(/units/admin/*, /units/categories)必须在
参数路径(/units/{category})之前注册，否则会被拦截。
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import UnitDefinition
from app.calc.units import BUILTIN_UNITS, DEFAULT_UNIT_CODES, load_units_from_db

router = APIRouter(prefix="/units", tags=["单位字典"])


# ---- 请求/响应模型 ----
class UnitDefCreate(BaseModel):
    category: str
    unit_code: str
    unit_label: str
    factor: float = 1.0
    offset: float = 0.0
    unit_group: str = "metric"
    pressure_type: Optional[str] = None
    is_primary: bool = False
    sort_order: int = 0
    is_active: bool = True
    remark: Optional[str] = None


class UnitDefUpdate(BaseModel):
    unit_label: Optional[str] = None
    factor: Optional[float] = None
    offset: Optional[float] = None
    unit_group: Optional[str] = None
    pressure_type: Optional[str] = None
    is_primary: Optional[bool] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    remark: Optional[str] = None


class UnitDefOut(BaseModel):
    id: int
    category: str
    unit_code: str
    unit_label: str
    factor: float
    offset: float
    unit_group: str = "metric"
    pressure_type: Optional[str] = None
    is_primary: bool
    sort_order: int
    is_active: bool
    remark: Optional[str] = None

    class Config:
        from_attributes = True


def _get_defaults(db: Session) -> dict:
    defaults = {}
    for cat in set(r[0] for r in load_units_from_db(db)):
        primary = db.query(UnitDefinition).filter(
            UnitDefinition.category == cat,
            UnitDefinition.is_primary == True,
            UnitDefinition.is_active == True,
        ).first()
        defaults[cat] = primary.unit_code if primary else DEFAULT_UNIT_CODES.get(cat, "")
    return defaults


# ============================================================
#  管理接口（固定路径，必须在 /units/{category} 之前）
# ============================================================

@router.get("/admin/all", response_model=list[UnitDefOut], summary="管理视图：返回全部单位定义")
def admin_list_all(
    category: Optional[str] = Query(None, description="按类别筛选"),
    include_inactive: bool = Query(True, description="是否包含已停用的"),
    db: Session = Depends(get_db),
):
    q = db.query(UnitDefinition)
    if category:
        q = q.filter(UnitDefinition.category == category)
    if not include_inactive:
        q = q.filter(UnitDefinition.is_active == True)
    return q.order_by(UnitDefinition.category, UnitDefinition.sort_order, UnitDefinition.id).all()


@router.post("/admin", response_model=UnitDefOut, summary="新增单位定义")
def admin_create(payload: UnitDefCreate, db: Session = Depends(get_db)):
    exists = db.query(UnitDefinition).filter(
        UnitDefinition.category == payload.category,
        UnitDefinition.unit_code == payload.unit_code,
    ).first()
    if exists:
        raise HTTPException(400, f"类别 {payload.category} 下已存在 unit_code={payload.unit_code}")
    if payload.is_primary:
        db.query(UnitDefinition).filter(
            UnitDefinition.category == payload.category,
            UnitDefinition.is_primary == True,
        ).update({UnitDefinition.is_primary: False})
    obj = UnitDefinition(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/admin/{uid}", response_model=UnitDefOut, summary="修改单位定义")
def admin_update(uid: int, payload: UnitDefUpdate, db: Session = Depends(get_db)):
    obj = db.get(UnitDefinition, uid)
    if not obj:
        raise HTTPException(404, "单位定义不存在")
    data = payload.model_dump(exclude_unset=True)
    if data.get("is_primary"):
        db.query(UnitDefinition).filter(
            UnitDefinition.category == obj.category,
            UnitDefinition.is_primary == True,
            UnitDefinition.id != uid,
        ).update({UnitDefinition.is_primary: False})
    for k, v in data.items():
        setattr(obj, k, v)
    obj.updated_at = datetime.now()
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/admin/{uid}", summary="删除单位定义")
def admin_delete(uid: int, db: Session = Depends(get_db)):
    obj = db.get(UnitDefinition, uid)
    if not obj:
        raise HTTPException(404, "单位定义不存在")
    if obj.is_primary:
        raise HTTPException(400, "不能删除类别主单位，请先将其他单位设为主单位")
    db.delete(obj)
    db.commit()
    return {"ok": True}


@router.post("/admin/{uid}/toggle", response_model=UnitDefOut, summary="切换启用/停用")
def admin_toggle(uid: int, db: Session = Depends(get_db)):
    obj = db.get(UnitDefinition, uid)
    if not obj:
        raise HTTPException(404, "单位定义不存在")
    if obj.is_primary and obj.is_active:
        raise HTTPException(400, "主单位不能停用")
    obj.is_active = not obj.is_active
    obj.updated_at = datetime.now()
    db.commit()
    db.refresh(obj)
    return obj


# ============================================================
#  读取接口（给前端下拉框用）
# ============================================================

@router.get("/categories", summary="列出所有参数类别")
def list_categories(db: Session = Depends(get_db)):
    label_map = {
        "pressure": "压力",
        "temperature": "温度",
        "mass_flow": "质量流量",
        "vol_flow_liquid": "体积流量(液体)",
        "vol_flow_gas": "体积流量(气体标况)",
        "density": "密度",
        "viscosity": "动力粘度",
        "diameter": "口径/直径",
        "wall_thickness": "壁厚",
        "distance": "距离",
        "molecular_weight": "摩尔质量",
    }
    defaults = _get_defaults(db)
    all_cats = set(label_map.keys()) | set(defaults.keys())
    return [
        {
            "category": c,
            "label": label_map.get(c, c),
            "default_unit": defaults.get(c, ""),
        }
        for c in sorted(all_cats)
    ]


@router.get("", summary="获取全部单位字典(按类别分组,仅启用)")
def list_all(db: Session = Depends(get_db)):
    rows = db.query(UnitDefinition).filter(
        UnitDefinition.is_active == True
    ).order_by(
        UnitDefinition.category, UnitDefinition.sort_order, UnitDefinition.id
    ).all()
    grouped = {}
    for r in rows:
        grouped.setdefault(r.category, []).append({
            "unit_code": r.unit_code,
            "unit_label": r.unit_label,
            "factor": r.factor,
            "offset": r.offset,
            "is_primary": bool(r.is_primary),
            "unit_group": r.unit_group or "metric",
            "pressure_type": r.pressure_type,
        })
    return {"categories": grouped, "defaults": _get_defaults(db)}


# ============================================================
#  动态路由（必须放在最后）
# ============================================================

@router.get("/{category}", summary="获取指定类别的单位列表")
def list_category(category: str, db: Session = Depends(get_db)):
    rows = db.query(UnitDefinition).filter(
        UnitDefinition.category == category,
        UnitDefinition.is_active == True,
    ).order_by(UnitDefinition.sort_order, UnitDefinition.id).all()
    if not rows:
        builtin = [
            {"unit_code": u[1], "unit_label": u[2],
             "factor": u[3], "offset": u[4], "is_primary": u[5]}
            for u in BUILTIN_UNITS if u[0] == category
        ]
        if not builtin:
            raise HTTPException(404, f"参数类别 {category} 不存在")
        return {"category": category, "units": builtin, "source": "builtin_fallback"}
    return {
        "category": category,
        "units": [{
            "unit_code": r.unit_code, "unit_label": r.unit_label,
            "factor": r.factor, "offset": r.offset,
            "is_primary": bool(r.is_primary),
            "unit_group": r.unit_group or "metric",
            "pressure_type": r.pressure_type,
        } for r in rows],
        "primary": next(({"unit_code": r.unit_code, "unit_label": r.unit_label}
                         for r in rows if r.is_primary), None),
    }
