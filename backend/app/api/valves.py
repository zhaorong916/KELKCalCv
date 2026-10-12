"""调节阀(位号)管理接口"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_db
from app.models import Project, Valve, Calculation
from app.schemas import ValveCreate, ValveUpdate, ValveOut

router = APIRouter(prefix="/projects/{pid}/valves", tags=["位号管理"])


@router.get("", response_model=list[ValveOut])
def list_valves(pid: int, db: Session = Depends(get_db), keyword: str | None = Query(None)):
    if not db.get(Project, pid):
        raise HTTPException(404, "项目不存在")
    q = db.query(Valve).filter(Valve.project_id == pid)
    if keyword:
        q = q.filter(
            (Valve.tag_no.contains(keyword)) |
            (Valve.valve_name.contains(keyword)) |
            (Valve.service.contains(keyword))
        )
    valves = q.order_by(Valve.tag_no).all()
    out = []
    for v in valves:
        d = ValveOut.model_validate(v).model_dump()
        d["calc_count"] = db.query(func.count(Calculation.id)).filter(Calculation.valve_id == v.id).scalar() or 0
        cur = db.query(Calculation).filter(Calculation.valve_id == v.id, Calculation.is_current == True).first()
        d["current_version"] = cur.version_no if cur else None
        out.append(d)
    return out


@router.post("", response_model=ValveOut)
def create_valve(pid: int, payload: ValveCreate, db: Session = Depends(get_db)):
    if not db.get(Project, pid):
        raise HTTPException(404, "项目不存在")
    if db.query(Valve).filter(Valve.project_id == pid, Valve.tag_no == payload.tag_no).first():
        raise HTTPException(400, f"位号 {payload.tag_no} 在本项目内已存在")
    v = Valve(project_id=pid, **payload.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    d = ValveOut.model_validate(v).model_dump()
    d["calc_count"] = 0
    d["current_version"] = None
    return d


@router.get("/{vid}", response_model=ValveOut)
def get_valve(pid: int, vid: int, db: Session = Depends(get_db)):
    v = db.get(Valve, vid)
    if not v or v.project_id != pid:
        raise HTTPException(404, "位号不存在")
    d = ValveOut.model_validate(v).model_dump()
    d["calc_count"] = db.query(func.count(Calculation.id)).filter(Calculation.valve_id == vid).scalar() or 0
    cur = db.query(Calculation).filter(Calculation.valve_id == vid, Calculation.is_current == True).first()
    d["current_version"] = cur.version_no if cur else None
    return d


@router.put("/{vid}", response_model=ValveOut)
def update_valve(pid: int, vid: int, payload: ValveUpdate, db: Session = Depends(get_db)):
    v = db.get(Valve, vid)
    if not v or v.project_id != pid:
        raise HTTPException(404, "位号不存在")
    for k, val in payload.model_dump(exclude_unset=True).items():
        setattr(v, k, val)
    db.commit()
    db.refresh(v)
    return ValveOut.model_validate(v)


@router.delete("/{vid}")
def delete_valve(pid: int, vid: int, db: Session = Depends(get_db)):
    v = db.get(Valve, vid)
    if not v or v.project_id != pid:
        raise HTTPException(404, "位号不存在")
    db.delete(v)
    db.commit()
    return {"ok": True}
