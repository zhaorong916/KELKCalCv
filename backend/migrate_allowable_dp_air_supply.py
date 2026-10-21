# -*- coding: utf-8 -*-
"""为 allowable_pressure_drops 增加 air_supply (气源压力) 列并重建唯一约束

背景: GC120 压差样本同一 (系列/执行机构/尺寸/填料/密封/阀芯) 组合在不同
气源压力 (300/340/400/500 kPa) 下允许压差不同。原唯一约束 uq_allowable_dp
不含气源压力, 导致 253 行被折叠为 135 行、后写覆盖先写。

幂等:
1. air_supply 列不存在 -> ALTER TABLE ADD
2. 唯一约束不含 air_supply -> DROP 后按新列集合重建
"""
import sys

from sqlalchemy import text

from app.core.database import engine

TABLE = "allowable_pressure_drops"
CONSTRAINT = "uq_allowable_dp"
NEW_KEY_COLS = ("series_code", "actuator_family", "actuator_size",
                "packing", "seat_type", "plug_inch", "air_supply")


def column_exists(conn, name: str) -> bool:
    return conn.execute(text("""
        SELECT COUNT(*) FROM sys.columns
        WHERE object_id = OBJECT_ID(:tbl) AND name = :col
    """), {"tbl": TABLE, "col": name}).scalar() > 0


def constraint_columns(conn) -> list:
    """返回唯一约束当前包含的列名 (按索引键序号); 约束不存在返回 []"""
    rows = conn.execute(text("""
        SELECT c.name
        FROM sys.key_constraints kc
        JOIN sys.indexes i
          ON i.object_id = kc.parent_object_id AND i.index_id = kc.unique_index_id
        JOIN sys.index_columns ic
          ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        JOIN sys.columns c
          ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE kc.parent_object_id = OBJECT_ID(:tbl) AND kc.name = :kc
        ORDER BY ic.key_ordinal
    """), {"tbl": TABLE, "kc": CONSTRAINT}).fetchall()
    return [r[0] for r in rows]


def main():
    with engine.begin() as conn:
        # 1. 加列
        if column_exists(conn, "air_supply"):
            print("air_supply 列已存在, 跳过 ADD COLUMN")
        else:
            conn.execute(text(
                f"ALTER TABLE {TABLE} ADD air_supply VARCHAR(16) NULL"))
            conn.execute(text("""
                EXEC sp_addextendedproperty
                    @name = N'MS_Description',
                    @value = N'气源压力 kPa(表压), 如 300(80)/340(120)/400/500',
                    @level0type = N'SCHEMA', @level0name = 'dbo',
                    @level1type = N'TABLE',  @level1name = 'allowable_pressure_drops',
                    @level2type = N'COLUMN', @level2name = 'air_supply'
            """))
            print("air_supply 列添加成功")

        # 2. 重建唯一约束
        current = constraint_columns(conn)
        if not current:
            print(f"未发现约束 {CONSTRAINT}, 直接创建")
            conn.execute(text(
                f"ALTER TABLE {TABLE} ADD CONSTRAINT {CONSTRAINT} "
                f"UNIQUE ({', '.join(NEW_KEY_COLS)})"))
            print("唯一约束创建成功:", ", ".join(NEW_KEY_COLS))
        elif current == list(NEW_KEY_COLS):
            print("唯一约束已包含 air_supply, 跳过")
        else:
            print("旧约束列:", ", ".join(current))
            conn.execute(text(
                f"ALTER TABLE {TABLE} DROP CONSTRAINT {CONSTRAINT}"))
            conn.execute(text(
                f"ALTER TABLE {TABLE} ADD CONSTRAINT {CONSTRAINT} "
                f"UNIQUE ({', '.join(NEW_KEY_COLS)})"))
            print("唯一约束重建成功:", ", ".join(NEW_KEY_COLS))


if __name__ == "__main__":
    main()
