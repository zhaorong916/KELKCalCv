"""为 valve_cv_stk 表添加 cv_min 列（最小可控Cv）

幂等脚本：检查列是否存在，不存在则添加。
依据: docs/选型模块优化方案.md v2.0 §2.5
"""
import sys
from sqlalchemy import text

from app.core.database import engine


def check_column_exists() -> bool:
    """检查 cv_min 列是否已存在"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) FROM sys.columns
            WHERE object_id = OBJECT_ID('valve_cv_stk') AND name = 'cv_min'
        """))
        return result.scalar() > 0


def add_cv_min_column():
    """添加 cv_min 列"""
    if check_column_exists():
        print("cv_min 列已存在，跳过")
        return

    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE valve_cv_stk ADD cv_min FLOAT NULL
        """))
        conn.execute(text("""
            EXEC sp_addextendedproperty
                @name = N'MS_Description',
                @value = N'最小可控Cv（多孔套筒/微流量系列专用）',
                @level0type = N'SCHEMA', @level0name = 'dbo',
                @level1type = N'TABLE', @level1name = 'valve_cv_stk',
                @level2type = N'COLUMN', @level2name = 'cv_min'
        """))
        conn.commit()
        print("cv_min 列添加成功")


if __name__ == "__main__":
    add_cv_min_column()
