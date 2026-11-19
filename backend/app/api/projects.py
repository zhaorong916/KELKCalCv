"""项目管理接口"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func

from app.api.deps import get_db
from app.models import Project, Valve, SelectionRecord
from app.schemas import ProjectCreate, ProjectUpdate, ProjectOut

router = APIRouter(prefix="/projects", tags=["项目管理"])


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), keyword: str | None = Query(None)):
    q = db.query(Project)
    if keyword:
        q = q.filter(
            (Project.project_code.contains(keyword)) |
            (Project.project_name.contains(keyword)) |
            (Project.client.contains(keyword))
        )
    projects = q.order_by(Project.created_at.desc()).all()
    out = []
    for p in projects:
        d = ProjectOut.model_validate(p).model_dump()
        d["valve_count"] = db.query(func.count(Valve.id)).filter(Valve.project_id == p.id).scalar() or 0
        out.append(d)
    return out


@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    if db.query(Project).filter(Project.project_code == payload.project_code).first():
        raise HTTPException(400, f"项目编号 {payload.project_code} 已存在")
    p = Project(**payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    d = ProjectOut.model_validate(p).model_dump()
    d["valve_count"] = 0
    return d


@router.get("/{pid}", response_model=ProjectOut)
def get_project(pid: int, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    d = ProjectOut.model_validate(p).model_dump()
    d["valve_count"] = db.query(func.count(Valve.id)).filter(Valve.project_id == pid).scalar() or 0
    return d


@router.put("/{pid}", response_model=ProjectOut)
def update_project(pid: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    d = ProjectOut.model_validate(p).model_dump()
    d["valve_count"] = db.query(func.count(Valve.id)).filter(Valve.project_id == pid).scalar() or 0
    return d


@router.delete("/{pid}")
def delete_project(pid: int, db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    # 选型历史外键为 NO_ACTION：先拦住并给出明确提示，避免直接抛 500
    valve_ids = db.query(Valve.id).filter(Valve.project_id == pid)
    n_sel = db.query(func.count(SelectionRecord.id)).filter(
        (SelectionRecord.project_id == pid) |
        (SelectionRecord.valve_id.in_(valve_ids))
    ).scalar() or 0
    if n_sel:
        raise HTTPException(409, f"该项目存在 {n_sel} 条选型记录，请先删除记录或停用项目")
    db.delete(p)
    db.commit()
    return {"ok": True}
