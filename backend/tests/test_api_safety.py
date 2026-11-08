"""回归测试: 选型历史级联删除 / SPA 静态文件路径穿越。

运行: cd backend && python -m unittest tests.test_api_safety
"""
import asyncio
import os
import tempfile
import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Project, Valve, SelectionRecord
from app.api.projects import delete_project
from app.api.valves import delete_valve


def _session():
    """内存 SQLite + 打开外键约束，复现数据库层的 FK 行为。"""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _project_with_history(db):
    p = Project(project_code="P1", project_name="项目")
    db.add(p)
    db.commit()
    v = Valve(project_id=p.id, tag_no="V1")
    db.add(v)
    db.commit()
    db.add(SelectionRecord(valve_id=v.id, project_id=p.id, input_snapshot="{}"))
    db.commit()
    return p, v


class TestDeleteWithSelectionHistory(unittest.TestCase):
    def test_delete_valve_with_history(self):
        db = _session()
        p, v = _project_with_history(db)
        self.assertEqual(delete_valve(p.id, v.id, db), {"ok": True})
        self.assertIsNone(db.get(Valve, v.id))
        self.assertEqual(db.query(SelectionRecord).count(), 0)

    def test_delete_project_with_history(self):
        db = _session()
        p, _ = _project_with_history(db)
        self.assertEqual(delete_project(p.id, db), {"ok": True})
        self.assertIsNone(db.get(Project, p.id))
        self.assertEqual(db.query(Valve).count(), 0)
        self.assertEqual(db.query(SelectionRecord).count(), 0)


class TestSpaFallbackTraversal(unittest.TestCase):
    def test_traversal_outside_static_is_blocked(self):
        import app.main as main

        fd, secret = tempfile.mkstemp(
            dir=os.path.dirname(main._static_dir), prefix="secret_", suffix=".txt")
        os.close(fd)
        try:
            rel = os.path.join("..", os.path.basename(secret))
            resp = asyncio.run(main.spa_fallback(rel, None))
            self.assertFalse(str(resp.path).endswith(os.path.basename(secret)))
            self.assertTrue(str(resp.path).endswith("index.html"))
        finally:
            os.remove(secret)


if __name__ == "__main__":
    unittest.main()
