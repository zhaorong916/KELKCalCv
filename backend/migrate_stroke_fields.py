"""迁移 valve_cv_stk 表: stroke/stroke_mm → stroke_value/stroke_unit

变更:
- stroke_value FLOAT        ← 原 stroke_mm (行程数值)
- stroke_unit VARCHAR(10)   ← 从原 stroke 字符串提取单位 (mm / °)
- 删除原 stroke (VARCHAR) 和 stroke_mm (FLOAT) 列
"""
import os

import pyodbc
from dotenv import load_dotenv

load_dotenv()
DB_CONN_STR = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.environ['DB_HOST']},{os.environ.get('DB_PORT', '1433')};"
    f"DATABASE={os.environ['DB_NAME']};UID={os.environ['DB_USER']};PWD={os.environ['DB_PASSWORD']}"
)


def migrate():
    conn = pyodbc.connect(DB_CONN_STR)
    cur = conn.cursor()

    # 1. 预览现有 stroke 值分布
    print("=== 现有 stroke 值分布 ===")
    cur.execute("""
        SELECT stroke, COUNT(*) as cnt
        FROM valve_cv_stk
        WHERE stroke IS NOT NULL
        GROUP BY stroke
        ORDER BY cnt DESC
    """)
    for row in cur.fetchall():
        print(f"  '{row.stroke}': {row.cnt}")

    # 2. 添加新列
    print("\n=== 添加新列 stroke_value / stroke_unit ===")
    cur.execute("ALTER TABLE valve_cv_stk ADD stroke_value FLOAT NULL")
    cur.execute("ALTER TABLE valve_cv_stk ADD stroke_unit VARCHAR(10) NULL")
    conn.commit()
    print("  列已添加")

    # 3. 迁移数据
    #    stroke_value = stroke_mm
    #    stroke_unit  = 从 stroke 字符串提取: 含 'mm' → 'mm'; 含 'Deg'/'°'/'º' → '°'
    print("\n=== 迁移数据 ===")
    cur.execute("""
        UPDATE valve_cv_stk
        SET stroke_value = stroke_mm,
            stroke_unit = CASE
                WHEN stroke LIKE '%mm%' THEN 'mm'
                WHEN stroke LIKE '%Deg%' OR stroke LIKE '%°%' OR stroke LIKE '%º%' THEN '°'
                ELSE NULL
            END
    """)
    conn.commit()
    print(f"  已迁移 {cur.rowcount} 行")

    # 4. 验证迁移结果
    print("\n=== 验证迁移结果 ===")
    cur.execute("""
        SELECT stroke_unit, COUNT(*) as cnt
        FROM valve_cv_stk
        WHERE stroke_value IS NOT NULL
        GROUP BY stroke_unit
    """)
    for row in cur.fetchall():
        print(f"  stroke_unit='{row.stroke_unit}': {row.cnt} 行")

    # 5. 抽查几行
    print("\n=== 抽查 (前 5 行有 stroke_value 的记录) ===")
    cur.execute("""
        SELECT TOP 5 series_code, dn_label, stroke_mm, stroke, stroke_value, stroke_unit
        FROM valve_cv_stk
        WHERE stroke_value IS NOT NULL
    """)
    for row in cur.fetchall():
        print(f"  {row.series_code} {row.dn_label}: old=({row.stroke_mm}, '{row.stroke}') → new=({row.stroke_value}, '{row.stroke_unit}')")

    # 6. 删除旧列
    print("\n=== 删除旧列 stroke / stroke_mm ===")
    # SQL Server 需要先删除约束/索引 (如果有), 这里直接删列
    cur.execute("ALTER TABLE valve_cv_stk DROP COLUMN stroke")
    cur.execute("ALTER TABLE valve_cv_stk DROP COLUMN stroke_mm")
    conn.commit()
    print("  旧列已删除")

    # 7. 最终验证
    print("\n=== 最终表结构 ===")
    cur.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'valve_cv_stk'
          AND COLUMN_NAME IN ('stroke_value', 'stroke_unit', 'stroke', 'stroke_mm')
    """)
    for row in cur.fetchall():
        print(f"  {row.COLUMN_NAME}: {row.DATA_TYPE}({row.CHARACTER_MAXIMUM_LENGTH})")

    cur.close()
    conn.close()
    print("\n迁移完成!")


if __name__ == "__main__":
    migrate()
