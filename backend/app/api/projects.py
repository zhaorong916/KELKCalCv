"""项目管理接口"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, or_

from app.api.deps import get_db
from app.models import Project, Valve, SelectionRecord
from app.schemas import ProjectCreate, ProjectUpdate, ProjectOut

router = APIRouter(prefix="/projects", tags=["项目管理"])


def _selection_count(db: Session, pid: int) -> int:
    """项目自身或其位号下关联的选型记录数"""
    valve_ids = db.query(Valve.id).filter(Valve.project_id == pid)
    return db.query(func.count(SelectionRecord.id)).filter(
        (SelectionRecord.project_id == pid) |
        (SelectionRecord.valve_id.in_(valve_ids))
    ).scalar() or 0


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    keyword: str | None = Query(None),
    include_disabled: bool = Query(False, description="是否包含已停用项目"),
):
    q = db.query(Project)
    if not include_disabled:
        # 已停用项目默认不显示；停用状态用于保留历史、阻止误删
        q = q.filter(or_(Project.status.is_(None), Project.status != "停用"))
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
        d["selection_record_count"] = _selection_count(db, p.id)
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
    d["selection_record_count"] = _selection_count(db, pid)
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
    d["selection_record_count"] = _selection_count(db, pid)
    return d


@router.delete("/{pid}")
def delete_project(
    pid: int,
    force: bool = Query(False, description="为 true 时连同选型记录一并删除"),
    db: Session = Depends(get_db),
):
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    # 仅允许删除已停用项目，避免误删在用项目
    if p.status != "停用":
        raise HTTPException(409, "仅可删除已停用项目，请先将项目状态改为「停用」")
    # 选型历史外键为 NO_ACTION：默认拦住，确认后(force=true)一并删除
    n_sel = _selection_count(db, pid)
    if n_sel and not force:
        raise HTTPException(409, f"该项目存在 {n_sel} 条选型记录，确认一并删除请带 force=true")
    if n_sel:
        valve_ids = db.query(Valve.id).filter(Valve.project_id == pid)
        db.query(SelectionRecord).filter(
            (SelectionRecord.project_id == pid) |
            (SelectionRecord.valve_id.in_(valve_ids))
        ).delete(synchronize_session=False)
    db.delete(p)
    db.commit()
    return {"ok": True, "deleted_selection_records": n_sel}
