"""介质库管理接口"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import Fluid
from app.schemas import FluidCreate, FluidOut
from app.calc.properties import water_properties

router = APIRouter(prefix="/fluids", tags=["介质库"])


@router.get("", response_model=list[FluidOut])
def list_fluids(db: Session = Depends(get_db), keyword: str | None = Query(None)):
    q = db.query(Fluid)
    if keyword:
        from sqlalchemy import or_
        kw = f"%{keyword}%"
        q = q.filter(or_(Fluid.fluid_name.like(kw), Fluid.fluid_name_cn.like(kw)))
    return q.order_by(Fluid.id).all()


@router.post("", response_model=FluidOut)
def create_fluid(payload: FluidCreate, db: Session = Depends(get_db)):
    if db.query(Fluid).filter(Fluid.fluid_name == payload.fluid_name).first():
        raise HTTPException(400, f"介质 {payload.fluid_name} 已存在")
    f = Fluid(**payload.model_dump())
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


@router.put("/{fid}", response_model=FluidOut)
def update_fluid(fid: int, payload: FluidCreate, db: Session = Depends(get_db)):
    f = db.get(Fluid, fid)
    if not f:
        raise HTTPException(404, "介质不存在")
    for k, v in payload.model_dump().items():
        setattr(f, k, v)
    db.commit()
    db.refresh(f)
    return f


@router.delete("/{fid}")
def delete_fluid(fid: int, db: Session = Depends(get_db)):
    f = db.get(Fluid, fid)
    if not f:
        raise HTTPException(404, "介质不存在")
    db.delete(f)
    db.commit()
    return {"ok": True}


@router.get("/water/resolve")
def resolve_water(t: float, p: float, db: Session = Depends(get_db)):
    """按温度(℃)/压力(kPa abs)解析水的相态与物性(自动判定液态/蒸汽)。"""
    fp = water_properties(t, p)
    return fp.to_dict()
