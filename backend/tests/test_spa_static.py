"""SPA 静态回退路由的安全性测试

回归: spa_fallback 直接用 os.path.join(_static_dir, full_path) 拼接路径,
`full_path` 含 `../` 时可越出 static 目录读取服务器任意文件(源码/配置/凭据)。
"""
import asyncio
import os
import unittest

from starlette.requests import Request

from app.main import spa_fallback, _static_dir


def _request() -> Request:
    return Request({
        "type": "http", "method": "GET", "path": "/", "query_string": b"",
        "headers": [], "http_version": "1.1", "scheme": "http",
        "server": ("testserver", 80), "client": ("testclient", 123),
    })


def _serve(full_path: str):
    return asyncio.run(spa_fallback(full_path, _request()))


class TestSpaFallbackTraversal(unittest.TestCase):
    def setUp(self):
        self.static_root = os.path.realpath(_static_dir)
        self.index_path = os.path.realpath(os.path.join(self.static_root, "index.html"))

    def test_parent_traversal_does_not_escape_static_dir(self):
        """../ 穿越必须回退到 SPA 入口, 不得返回 static 之外的文件。"""
        resp = _serve("../app/main.py")
        served = os.path.realpath(resp.path)
        self.assertEqual(served, self.index_path)

    def test_absolute_path_does_not_escape_static_dir(self):
        resp = _serve("/etc/passwd")
        self.assertEqual(os.path.realpath(resp.path), self.index_path)

    def test_nested_traversal_does_not_escape_static_dir(self):
        resp = _serve("assets/../../app/main.py")
        self.assertEqual(os.path.realpath(resp.path), self.index_path)

    def test_existing_static_file_still_served(self):
        resp = _serve("index.html")
        self.assertEqual(os.path.realpath(resp.path), self.index_path)


if __name__ == "__main__":
    unittest.main()
