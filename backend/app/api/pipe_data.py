"""管道规格数据 API (pipe_data 表)"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models import PipeData

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
            "od_mm": r.od_mm,
            "thk_mm": r.thk_mm,
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
