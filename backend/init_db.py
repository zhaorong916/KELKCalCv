"""数据库初始化脚本

用法:
    python init_db.py

功能:
    1) 连接 SQL Server，若数据库 KELKCalCv 不存在则创建
    2) 创建全部表
    3) 初始化介质库(20种常见介质)
    4) 创建默认管理员
"""
import pyodbc
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.models import Fluid, User
from app.calc.properties import get_fluid_defaults


def ensure_database():
    """连接 master 库，若目标库不存在则创建。"""
    master_conn = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={settings.DB_HOST},{settings.DB_PORT};"
        f"DATABASE=master;UID={settings.DB_USER};PWD={settings.DB_PASSWORD};"
        f"TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(master_conn, autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute("SELECT database_id FROM sys.databases WHERE name = ?", settings.DB_NAME)
        if cur.fetchone():
            print(f"[数据库] {settings.DB_NAME} 已存在")
        else:
            cur.execute(f"CREATE DATABASE [{settings.DB_NAME}]")
            conn.commit()
            print(f"[数据库] 已创建 {settings.DB_NAME}")
    finally:
        conn.close()


def create_tables():
    Base.metadata.create_all(bind=engine, checkfirst=True)
    print("[表结构] 创建完成")


def seed_fluids():
    with SessionLocal() as db:
        if db.query(Fluid).count() > 0:
            print("[介质库] 已存在数据，跳过初始化")
            return
        for item in get_fluid_defaults():
            db.add(Fluid(**item))
        db.commit()
        print(f"[介质库] 已初始化 {len(get_fluid_defaults())} 种介质")


def seed_units():
    from app.calc.units import seed_unit_definitions
    with SessionLocal() as db:
        n = seed_unit_definitions(db)
        if n > 0:
            print(f"[单位字典] 已初始化 {n} 条单位定义")
        else:
            print("[单位字典] 已存在数据，跳过初始化")


def create_admin():
    import hashlib
    with SessionLocal() as db:
        if db.query(User).filter(User.username == "admin").first():
            print("[用户] admin 已存在")
            return
        pw_hash = hashlib.sha256("admin123".encode()).hexdigest()
        db.add(User(username="admin", display_name="管理员", password_hash=pw_hash, role="admin"))
        db.commit()
        print("[用户] 已创建管理员 admin/admin123")


if __name__ == "__main__":
    print("=" * 60)
    print(f"初始化 {settings.APP_NAME}")
    print("=" * 60)
    ensure_database()
    create_tables()
    seed_fluids()
    seed_units()
    create_admin()
    print("初始化完成。启动后端: uvicorn app.main:app --reload --port 8000")
