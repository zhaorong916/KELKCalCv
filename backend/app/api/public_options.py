"""公共选项 API：连接形式、密封面、材质、填料等下拉数据"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import PublicOption


router = APIRouter(prefix="/public-options", tags=["公共选项"])


@router.get("")
def list_public_options(
    group: Optional[str] = Query(None, description="按分组过滤, 如 connection_type / body_material"),
    db: Session = Depends(get_db),
):
    """获取所有(或指定分组)公共选项

    返回结构:
        {
            "groups": {
                "connection_type": [{value, label, sort_order, is_default}, ...],
                ...
            }
        }
    """
    q = db.query(PublicOption).filter(PublicOption.is_active == True)
    if group:
        q = q.filter(PublicOption.group_key == group)
    rows = q.order_by(PublicOption.group_key, PublicOption.sort_order).all()

    groups = {}
    for row in rows:
        groups.setdefault(row.group_key, []).append({
            "value": row.value,
            "label": row.label or row.value,
            "sort_order": row.sort_order,
            "is_default": row.is_default,
        })
    return {"groups": groups}
