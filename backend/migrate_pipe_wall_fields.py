"""迁移 valve_configs 表: 新增 pipe_wall_front / pipe_wall_back 列

背景: 前端计算页新增了"管道壁厚(阀前/阀后)"输入框并支持从管道规格自动填充,
但后端 ValveConfig 模型/表缺少对应列, 导致保存时该字段被 Pydantic 静默丢弃,
用户重新加载后壁厚丢失。本迁移为已存在的 valve_configs 表补列。
"""
import os

import pyodbc
from dotenv import load_dotenv

load_dotenv()
DB_CONN_STR = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.environ['DB_HOST']},{os.environ.get('DB_PORT', '1433')};"
    f"DATABASE={os.environ['DB_NAME']};UID={os.environ['DB_USER']};PWD={os.environ['DB_PASSWORD']};"
    f"TrustServerCertificate=yes;"
)

TABLE = "valve_configs"
COLS = [
    ("pipe_wall_front", "VARCHAR(64) NULL"),
    ("pipe_wall_back", "VARCHAR(64) NULL"),
]


def _col_exists(cur, table: str, col: str) -> bool:
    cur.execute(
        "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME = ? AND COLUMN_NAME = ?",
        table, col,
    )
    return cur.fetchone() is not None


def migrate():
    conn = pyodbc.connect(DB_CONN_STR)
    cur = conn.cursor()
    for col, ddl in COLS:
        if _col_exists(cur, TABLE, col):
            print(f"[skip] {TABLE}.{col} 已存在")
            continue
        cur.execute(f"ALTER TABLE {TABLE} ADD {col} {ddl}")
        conn.commit()
        print(f"[ok] 已添加 {TABLE}.{col} {ddl}")
    cur.close()
    conn.close()
    print("迁移完成!")


if __name__ == "__main__":
    migrate()
