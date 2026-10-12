"""公称尺寸对照表 API — 提供 in/mm/A/DN 之间的相互映射"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import asc

from app.core.database import get_db
from app.models import NominalSizeRef

router = APIRouter()


@router.get("/nominal-sizes", summary="获取公称尺寸对照表")
@router.get("/nominal-size-refs", summary="获取公称尺寸对照表 (别名)")
def list_nominal_sizes(
    dn_mm: int | None = None,
    jis_a: str | None = None,
    dn_label: str | None = None,
    db: Session = Depends(get_db),
):
    """获取公称尺寸映射表，可按条件精确查询"""
    q = db.query(NominalSizeRef).order_by(asc(NominalSizeRef.sort_order))
    if dn_mm:
        q = q.filter(NominalSizeRef.dn_mm == dn_mm)
    if jis_a:
        q = q.filter(NominalSizeRef.jis_a == jis_a)
    if dn_label:
        q = q.filter(NominalSizeRef.dn_label == dn_label)
    rows = q.all()
    return {
        "total": len(rows),
        "items": [
            {
                "id": r.id,
                "nps_in": r.nps_in,
                "nps_in_decimal": r.nps_in_decimal,
                "dn_mm": r.dn_mm,
                "jis_a": r.jis_a,
                "dn_label": r.dn_label,
            }
            for r in rows
        ],
    }


def seed_nominal_sizes(db: Session):
    """向 nominal_size_refs 表注入种子数据（若表为空）"""
    from sqlalchemy import func
    if db.query(func.count(NominalSizeRef.id)).scalar() > 0:
        return

    # (nps_in, nps_in_decimal, dn_mm, jis_a, dn_label)
    DATA = [
        ("1/64", 0.015625, 1, "1A", None),
        ("1/32", 0.03125, 3, "3A", None),
        ("1/16", 0.0625, 6, "6A", None),
        ("1/8", 0.125, 7, "7A", None),
        ("3/16", 0.1875, 8, "8A", None),
        ("1/4", 0.25, 10, "10A", None),
        ("5/16", 0.3125, 9, "9A", None),
        ("3/8", 0.375, 15, "15A", "DN15"),
        ("1/2", 0.5, 20, "20A", "DN20"),
        ("3/4", 0.75, 25, "25A", "DN25"),
        ("1", 1.0, 32, "32A", "DN32"),
        ("1 1/4", 1.25, 40, "40A", "DN40"),
        ("1 1/2", 1.5, 50, "50A", "DN50"),
        ("2", 2.0, 65, "65A", "DN65"),
        ("2 1/2", 2.5, 80, "80A", "DN80"),
        ("3", 3.0, 100, "100A", "DN100"),
        ("4", 4.0, 125, "125A", "DN125"),
        ("5", 5.0, 150, "150A", "DN150"),
        ("6", 6.0, 175, "175A", "DN175"),
        ("7", 7.0, 200, "200A", "DN200"),
        ("8", 8.0, 250, "250A", "DN250"),
        ("10", 10.0, 300, "300A", "DN300"),
        ("12", 12.0, 350, "350A", "DN350"),
        ("14", 14.0, 400, "400A", "DN400"),
        ("16", 16.0, 450, "450A", "DN450"),
        ("18", 18.0, 500, "500A", "DN500"),
        ("20", 20.0, 550, "550A", "DN550"),
        ("22", 22.0, 600, "600A", "DN600"),
        ("24", 24.0, 650, "650A", "DN650"),
        ("26", 26.0, 700, "700A", "DN700"),
        ("28", 28.0, 750, "750A", "DN750"),
        ("30", 30.0, 800, "800A", "DN800"),
        ("32", 32.0, 850, "850A", "DN850"),
        ("34", 34.0, 900, "900A", "DN900"),
        ("36", 36.0, 1000, "1000A", "DN1000"),
        ("40", 40.0, 1050, "1050A", "DN1050"),
        ("42", 42.0, 1100, "1100A", "DN1100"),
        ("44", 44.0, 1200, "1200A", "DN1200"),
        ("48", 48.0, 1300, "1300A", "DN1300"),
        ("52", 52.0, 1350, "1350A", "DN1350"),
        ("54", 54.0, 1500, "1500A", "DN1500"),
        ("60", 60.0, 1500, "1500A", "DN1500"),
    ]
    # 去重 (dn_mm 唯一约束，最后一个覆盖相同值)
    seen = set()
    deduped = []
    for row in DATA:
        if row[2] not in seen:
            seen.add(row[2])
            deduped.append(row)

    for idx, (nps, dec, mm, ja, dn) in enumerate(deduped):
        db.add(NominalSizeRef(
            nps_in=nps,
            nps_in_decimal=dec,
            dn_mm=mm,
            jis_a=ja,
            dn_label=dn,
            sort_order=idx,
        ))
    db.commit()
