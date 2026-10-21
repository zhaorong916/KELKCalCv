"""系列数据适配器基类与注册表

将 docs/<系列>_structured_data.json 中的异构数据映射到统一表结构：
- valve_cv_stk (额定Cv与行程)
- body_pt_ratings (阀体温压限制)
- allowable_pressure_drops (最大允许压差)
- 尺寸数据 (预留)

设计原则:
1. 每个系列一个 Adapter 类，继承 SeriesAdapter
2. Adapter 只负责解析 JSON → 统一格式的 dict 列表，不直接操作数据库
3. 统一使用 JIS A 格式作为 dn_label/trim_label (如 25A, 100A)
4. 通过 ADAPTERS 注册表管理所有系列
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

# 结构化数据文件根目录
DOCS_DIR = Path(__file__).parent.parent.parent.parent / "docs"


# ---------------------------------------------------------------------------
# 通用工具函数
# ---------------------------------------------------------------------------

def jis_a_to_mm(jis_a: str) -> Optional[float]:
    """JIS A 标签 → mm 数值: '25A' → 25, '100A' → 100"""
    if not jis_a:
        return None
    m = re.match(r"(\d+(?:\.\d+)?)A", jis_a, re.IGNORECASE)
    return float(m.group(1)) if m else None


def mm_to_jis_a(mm: float) -> str:
    """mm 数值 → JIS A 标签: 25 → '25A', 100 → '100A'"""
    return f"{int(mm)}A"


def inch_to_mm(inch_str: str) -> Optional[float]:
    """英寸标签 → mm 数值: '1-1/2' → 40, '1/2' → 15, '1' → 25"""
    if not inch_str:
        return None
    inch_str = inch_str.strip()
    # 处理 "1-1/2" 格式
    if "-" in inch_str:
        parts = inch_str.split("-")
        whole = float(parts[0])
        frac_parts = parts[1].split("/")
        frac = float(frac_parts[0]) / float(frac_parts[1])
        inch = whole + frac
    # 处理 "1/2" 格式
    elif "/" in inch_str:
        parts = inch_str.split("/")
        inch = float(parts[0]) / float(parts[1])
    else:
        inch = float(inch_str)
    # 标准换算表 (常用口径)
    inch_to_mm_map = {
        0.125: 6, 0.25: 8, 0.375: 10, 0.5: 15, 0.75: 20,
        1: 25, 1.25: 32, 1.5: 40, 2: 50, 2.5: 65, 3: 80,
        4: 100, 5: 125, 6: 150, 8: 200, 10: 250, 12: 300,
        14: 350, 16: 400, 18: 450, 20: 500, 24: 600,
    }
    return inch_to_mm_map.get(inch, inch * 25.4)


def parse_fraction_inch(s: str) -> Optional[float]:
    """解析英寸分数为小数: '1-1/2' → 1.5, '3/4' → 0.75, '1' → 1.0"""
    if not s:
        return None
    s = s.strip()
    if "-" in s:
        parts = s.split("-")
        whole = float(parts[0])
        frac_parts = parts[1].split("/")
        return whole + float(frac_parts[0]) / float(frac_parts[1])
    elif "/" in s:
        parts = s.split("/")
        return float(parts[0]) / float(parts[1])
    else:
        return float(s)


def parse_temp_range(s: str) -> tuple[Optional[float], Optional[float]]:
    """解析温度范围: '-45~+230' → (-45, 230), '-196~-45' → (-196, -45)"""
    if not s:
        return None, None
    s = s.replace("℃", "").replace("°C", "").strip()
    # 匹配 "-45~+230" 或 "-196~-45"
    m = re.match(r"([+-]?\d+(?:\.\d+)?)\s*[~\-]\s*([+-]?\d+(?:\.\d+)?)", s)
    if m:
        t1, t2 = float(m.group(1)), float(m.group(2))
        return (min(t1, t2), max(t1, t2))
    return None, None


def safe_float(v: Any) -> Optional[float]:
    """安全转换为 float: '—'/'-'/None → None, '1,234' → 1234.0"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s in ("—", "-", "–", "", "N/A", "n/a"):
        return None
    # 移除千位分隔符
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Adapter 基类
# ---------------------------------------------------------------------------

class SeriesAdapter(ABC):
    """系列数据适配器基类

    子类必须实现 parse_rated_cv(), 可选实现 parse_allowable_dp/parse_body_pt/parse_dimensions
    """

    def __init__(self, series_code: str, json_path: Optional[Path] = None):
        self.series_code = series_code
        self.json_path = json_path or (DOCS_DIR / f"{series_code}_structured_data.json")
        self._data: Optional[Dict[str, Any]] = None

    @property
    def data(self) -> Dict[str, Any]:
        """懒加载 JSON 数据"""
        if self._data is None:
            with open(self.json_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        return self._data

    @abstractmethod
    def parse_rated_cv(self) -> List[Dict[str, Any]]:
        """解析额定Cv数据 → valve_cv_stk 行格式

        返回格式:
        [
            {
                "series_code": "GC120",
                "dn_label": "40A",       # JIS A 格式
                "trim_label": "25A",     # JIS A 格式
                "flow_char": "EQ%",      # EQ% / Linear / ON-OFF
                "trim_type": "Standard", # Standard / Large Cv / Full / etc.
                "pressure_rating": "300#",  # 150# / 300# / 600# / etc.
                "seat_type": None,       # Soft / Metal / etc.
                "rated_cv": 36.0,
                "stroke_unit": "mm",
                "stroke_value": 25.0,
                "plug_mm": 25.0,
                "cv_min": None,          # GC210 等多孔套筒系列需要
                "stk_index": None,
                "kfd": None, "kfo": None, "kfb": None,
            },
            ...
        ]
        """
        raise NotImplementedError

    def parse_allowable_dp(self) -> List[Dict[str, Any]]:
        """解析允许压差数据 → allowable_pressure_drops 行格式

        返回格式:
        [
            {
                "series_code": "GC120",
                "dn_label": "40A",
                "trim_label": "25A",
                "pressure_rating": "300#",
                "seat_type": "Metal",
                "max_dp_mpa": 1.5,
                "flow_direction": "FTO",
                "actuator_type": "Diaphragm",
                "spring_range": "80-200",
                "remark": None,
            },
            ...
        ]
        """
        return []

    def parse_body_pt(self) -> List[Dict[str, Any]]:
        """解析阀体温压数据 → body_pt_ratings 行格式

        返回格式:
        [
            {
                "series_code": "GC120",
                "body_material": "A216-WCB",
                "standard": "ASME B16.34",
                "pressure_class": "300#",
                "temp_c": 200.0,
                "max_pressure_mpa": 5.1,
            },
            ...
        ]
        """
        return []

    def parse_dimensions(self) -> List[Dict[str, Any]]:
        """解析尺寸数据 (预留)"""
        return []

    def _norm_dn_label(self, dn_mm: Optional[float] = None, dn_inch: Optional[str] = None,
                       dn_label: Optional[str] = None) -> Optional[str]:
        """统一转换为 JIS A 格式的 dn_label"""
        if dn_label:
            return dn_label
        if dn_mm:
            return mm_to_jis_a(dn_mm)
        if dn_inch:
            mm = inch_to_mm(dn_inch)
            return mm_to_jis_a(mm) if mm else None
        return None

    def _norm_trim_label(self, plug_mm: Optional[float] = None, plug_inch: Optional[str] = None,
                         trim_label: Optional[str] = None) -> Optional[str]:
        """统一转换为 JIS A 格式的 trim_label"""
        if trim_label:
            return trim_label
        if plug_mm:
            return mm_to_jis_a(plug_mm)
        if plug_inch:
            mm = inch_to_mm(plug_inch)
            return mm_to_jis_a(mm) if mm else None
        return None


# ---------------------------------------------------------------------------
# Adapter 注册表
# ---------------------------------------------------------------------------

ADAPTERS: Dict[str, type[SeriesAdapter]] = {}


def register_adapter(cls: type[SeriesAdapter]) -> type[SeriesAdapter]:
    """注册 adapter 类的装饰器"""
    # 支持一个类注册多个系列 (如 GC120 和 GC210 共用)
    for code in cls.SERIES_CODES:
        ADAPTERS[code] = cls
    return cls


def get_adapter(series_code: str) -> SeriesAdapter:
    """获取指定系列的 adapter 实例"""
    if series_code not in ADAPTERS:
        raise ValueError(f"未注册的系列: {series_code}，已注册: {list(ADAPTERS.keys())}")
    return ADAPTERS[series_code](series_code)


def list_registered_series() -> List[str]:
    """列出所有已注册的系列代码"""
    return sorted(ADAPTERS.keys())


# ---------------------------------------------------------------------------
# 导入所有 adapter 模块 (触发注册)
# ---------------------------------------------------------------------------
# 注意: 新增 adapter 时必须在此导入，否则不会注册
def _import_all_adapters():
    """导入所有 adapter 模块以触发注册"""
    from . import (
        gc120_210_adapter,
        gc320_adapter,
        gv120_adapter,
        bt210_adapter,
        bv210_adapter,
        ga510_adapter,
        gv110_adapter,
        gv130_adapter,
        bt110_adapter,
        bt310_adapter,
        bv130_adapter,
        gz800_adapter,
    )


# 延迟导入，避免循环依赖
try:
    _import_all_adapters()
except ImportError:
    # 部分 adapter 尚未创建时静默跳过
    pass
