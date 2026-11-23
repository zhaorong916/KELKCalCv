"""迁移 selection_rules 表: 支持规则版本化

变更:
- 新增 version INT NOT NULL DEFAULT 1
- 新增 prev_rule_id INT NULL
- 删除原 rule_code 唯一约束, 改为 UNIQUE (rule_code, version)

安全: 不使用 DELETE/DROP TABLE; 重复执行幂等。
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
    conn.autocommit = True
    cur = conn.cursor()

    print("=== 1. 现有规则/唯一约束 ===")
    cur.execute("SELECT COUNT(*) FROM selection_rules")
    print("  规则行数:", cur.fetchone()[0])
    cur.execute("""
        SELECT name FROM sys.key_constraints
        WHERE parent_object_id = OBJECT_ID('selection_rules') AND type = 'UQ'
    """)
    uq_names = [r[0] for r in cur.fetchall()]
    print("  UQ 约束:", uq_names)

    print("\n=== 2. 新增 version / prev_rule_id 列 ===")
    if cur.execute("SELECT COL_LENGTH('selection_rules','version')").fetchone()[0] is None:
        cur.execute("""
            ALTER TABLE selection_rules
            ADD version INT NOT NULL CONSTRAINT DF_selection_rules_version DEFAULT 1 WITH VALUES
        """)
        print("  version 列已添加")
    else:
        print("  version 列已存在")
    if cur.execute("SELECT COL_LENGTH('selection_rules','prev_rule_id')").fetchone()[0] is None:
        cur.execute("ALTER TABLE selection_rules ADD prev_rule_id INT NULL")
        print("  prev_rule_id 列已添加")
    else:
        print("  prev_rule_id 列已存在")

    print("\n=== 3. 替换唯一约束为 (rule_code, version) ===")
    for name in uq_names:
        cur.execute(f"ALTER TABLE selection_rules DROP CONSTRAINT [{name}]")
        print("  已删除:", name)
    if cur.execute("""
        SELECT COUNT(*) FROM sys.indexes
        WHERE name = 'uq_selection_rules_code_version'
          AND object_id = OBJECT_ID('selection_rules')
    """).fetchone()[0] == 0:
        cur.execute("""
            CREATE UNIQUE INDEX uq_selection_rules_code_version
            ON selection_rules(rule_code, version)
        """)
        print("  已创建 uq_selection_rules_code_version")

    print("\n=== 4. 校验 ===")
    cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT rule_code, version FROM selection_rules
            GROUP BY rule_code, version HAVING COUNT(*) > 1
        ) t
    """)
    print("  (rule_code, version) 重复组:", cur.fetchone()[0])
    for col in ("version", "prev_rule_id"):
        cur.execute(f"SELECT COL_LENGTH('selection_rules','{col}')")
        print(f"  {col} 列长度:", cur.fetchone()[0])

    cur.close()
    conn.close()
    print("\n迁移完成!")


if __name__ == "__main__":
    migrate()
