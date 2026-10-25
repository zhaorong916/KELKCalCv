"""回归测试: ValveConfigSchema 必须保留 pipe_wall_front / pipe_wall_back

缺陷: 前端计算页新增"管道壁厚(阀前/阀后)"字段后, 后端 ValveConfigSchema
未声明对应字段, Pydantic v2 默认 extra='ignore' 会在保存配置时静默丢弃,
导致用户重新加载页面后壁厚丢失。

本测试覆盖: schema 接收并输出这两个字段, 使其能经 setattr 写入模型。
"""
import unittest

from app.schemas import ValveConfigSchema


class ValveConfigPipeWallTest(unittest.TestCase):
    def test_pipe_wall_fields_are_preserved(self):
        payload = {
            "valve_style": "单座柱塞阀",
            "pipe_wall_front": "0.216 in (5 mm)",
            "pipe_wall_back": "5 mm",
        }
        schema = ValveConfigSchema(**payload)
        dumped = schema.model_dump()
        self.assertEqual(dumped["pipe_wall_front"], "0.216 in (5 mm)")
        self.assertEqual(dumped["pipe_wall_back"], "5 mm")

    def test_pipe_wall_fields_default_none(self):
        schema = ValveConfigSchema(valve_style="单座柱塞阀")
        dumped = schema.model_dump()
        self.assertIsNone(dumped["pipe_wall_front"])
        self.assertIsNone(dumped["pipe_wall_back"])


if __name__ == "__main__":
    unittest.main()
