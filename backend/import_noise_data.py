# -*- coding: utf-8 -*-
"""从 Noise 2.3.xlsm 导入流体/管道/阀门数据

目标：
  1) [FluidData] 合并到 fluids 表，保留原有20条记录并扩展字段，补充中文名称
  2) [PipeData]  写入 pipe_data 表（新表）
  3) [ValveData] 写入 valve_sizing_indices 表（新表）

依赖：openpyxl, sqlalchemy (后端 requirements.txt 已包含)
运行：
  cd backend
  python import_noise_data.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# 确保 backend 目录在 sys.path
BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

import openpyxl
from sqlalchemy import text
from sqlalchemy.engine import Inspector, reflection

from app.core.database import Base, engine, SessionLocal
from app.models import Fluid, PipeData, ValveSizingIndex, ValveNominalSize


NOISE_XLSM = BASE.parent / r"参考文件\Noise 2.3.xlsm"
CN_XLSX = BASE.parent / r"参考文件\介质名称对照中英文.xlsx"


# =============================================================================
# 建表
# =============================================================================
def ensure_tables():
    """为 PipeData / ValveSizingIndex 建表；为 Fluid 新增列使用原生 ALTER。"""
    # 1) 新建缺失的 pipe_data / valve_sizing_indices 表
    insp: Inspector = reflection.Inspector.from_engine(engine)
    existing_tables = set(insp.get_table_names())

    new_meta_tables = [("pipe_data", PipeData.__table__),
                       ("valve_sizing_indices", ValveSizingIndex.__table__),
                       ("valve_nominal_sizes", ValveNominalSize.__table__)]
    for name, table in new_meta_tables:
        if name not in existing_tables:
            table.create(bind=engine, checkfirst=True)
            print(f"[表] 已创建 {name}")
        else:
            print(f"[表] {name} 已存在")

    # 2) 为 fluids 表补齐新增列（如果 SQL Server 中还没有）
    fluid_cols_to_add = [
        ("fluid_name_cn", "NVARCHAR(128)"),
        ("specific_name", "NVARCHAR(128)"),
        ("valtek_no", "INT"),
        ("boiling_point", "FLOAT"),
        ("acentric_factor", "FLOAT"),
        ("gf_constant", "FLOAT"),
        ("antoine_a", "FLOAT"),
        ("antoine_b", "FLOAT"),
        ("antoine_c", "FLOAT"),
        ("antoine_tmin_k", "FLOAT"),
        ("cp_a", "FLOAT"), ("cp_b", "FLOAT"), ("cp_c", "FLOAT"), ("cp_d", "FLOAT"),
        ("shomate_a", "FLOAT"), ("shomate_b", "FLOAT"), ("shomate_c", "FLOAT"),
        ("shomate_d", "FLOAT"), ("shomate_e", "FLOAT"), ("shomate_f", "FLOAT"),
        ("shomate_g", "FLOAT"), ("shomate_h", "FLOAT"),
        ("savage_c1", "FLOAT"), ("savage_c2", "FLOAT"), ("savage_c3", "FLOAT"),
        ("savage_c4", "FLOAT"), ("savage_c5", "FLOAT"), ("savage_c6", "FLOAT"),
        ("savage_c7", "FLOAT"), ("savage_c8", "FLOAT"), ("savage_c9", "FLOAT"),
        ("temperature_base", "FLOAT DEFAULT 273.15"),
        ("pressure_base", "FLOAT DEFAULT 101.325"),
    ]
    fluid_cols_insp = {c["name"] for c in insp.get_columns("fluids")}
    with engine.begin() as conn:
        for col, sqltype in fluid_cols_to_add:
            if col not in fluid_cols_insp:
                ddl = f"ALTER TABLE fluids ADD [{col}] {sqltype}"
                try:
                    conn.execute(text(ddl))
                    print(f"  fluids.ALTER ADD {col} {sqltype}")
                except Exception as e:  # pragma: no cover
                    print(f"  ! fluids.ALTER ADD {col} 失败: {e}")
            else:
                # print(f"  fluids.{col} 已存在")
                pass

        # valve_sizing_indices.no_coefficient 改为 VARCHAR(32)
        try:
            vsi_cols = {c["name"] for c in insp.get_columns("valve_sizing_indices")}
            if "no_coefficient" in vsi_cols:
                with engine.begin() as conn:
                    conn.execute(text(
                        "ALTER TABLE valve_sizing_indices ALTER COLUMN no_coefficient VARCHAR(32)"
                    ))
        except Exception as e:
            print(f"  ! 调整 no_coefficient 列长度失败: {e}")

    print("[表] 结构准备完成")


# =============================================================================
# 工具：读取中英文对照表
# =============================================================================
def load_cn_map() -> dict:
    """建立 英文名称 -> 中文名称 映射

    对照表 sheet1 的结构：
      col2 中文名称  col3 分子式  col4 英文名称
    清洗策略：
      - 英文去除空白/括号内中文/常见符号差异
      - 建立三个键：原始英文 / 小写去符号 / 分子式
    """
    wb = openpyxl.load_workbook(CN_XLSX, data_only=True, keep_links=False)
    ws = wb[wb.sheetnames[0]]
    cn_name_by_en = {}
    cn_name_by_formula = {}

    def _norm(s: str) -> str:
        if not s:
            return ""
        s = str(s).strip().lower()
        # 去除空白、短横线、斜杠等符号
        s = re.sub(r"[\s\-_,\/\.\(\)\[\]'\"‘’“”]+", "", s)
        return s

    for r in range(2, ws.max_row + 1):
        cn = ws.cell(row=r, column=2).value
        formula = ws.cell(row=r, column=3).value
        en = ws.cell(row=r, column=4).value
        if not cn:
            continue
        if en:
            cn_name_by_en[_norm(en)] = cn
            cn_name_by_en[str(en).strip()] = cn
        if formula:
            cn_name_by_formula[str(formula).strip()] = cn
            cn_name_by_formula[_norm(formula)] = cn

    # 补充一些常见 Excel/Noise 拼写差异
    extra = {
        "Water": "水（液体）/水蒸气",
        "Steam": "水蒸气",
        "Air": "空气",
        "Ammonia": "氨（液氨/氨气）",
        "Argon": "氩气",
        "Acetylene": "乙炔",
        "Hydrogen": "氢气",
        "Nitrogen": "氮气",
        "Oxygen": "氧气",
        "CarbonDioxide": "二氧化碳",
        "Carbon Monoxide": "一氧化碳",
        "Methane": "甲烷",
        "Ethane": "乙烷",
        "Propane": "丙烷",
        "Butane": "丁烷",
        "Isobutane": "异丁烷",
        "Ethylene": "乙烯",
        "Propylene": "丙烯",
        "1-Butene": "1-丁烯",
        "Benzene": "苯",
        "Toluene": "甲苯",
        "Xylene": "二甲苯",
        "Methanol": "甲醇",
        "Ethanol": "乙醇",
        "Natural Gas": "天然气",
        "Helium": "氦气",
        "Neon": "氖气",
        "Chlorine": "氯气",
        "HydrogenSulfide": "硫化氢",
        "SulfurDioxide": "二氧化硫",
        "SulfurTrioxide": "三氧化硫",
        "NitrogenDioxide": "二氧化氮",
        "Propene": "丙烯",
        "MethylAlcohol": "甲醇",
        "1-Propene, 2-methyl-": "异丁烯",
        "1,3-Butadiene, 2-methyl-": "异戊二烯",
        "Benzene, (1-methylethyl)-": "异丙苯",
    }
    for k, v in extra.items():
        if _norm(k) not in cn_name_by_en and k.strip() not in cn_name_by_en:
            cn_name_by_en[_norm(k)] = v

    print(f"[对照表] 英文键 {len(cn_name_by_en)} 条，分子式键 {len(cn_name_by_formula)} 条")
    return {"en": cn_name_by_en, "formula": cn_name_by_formula, "_norm": _norm}


def lookup_cn(name: str, formula: str, m: dict) -> str | None:
    if name:
        if name in m["en"]:
            return m["en"][name]
        key = m["_norm"](name)
        if key in m["en"]:
            return m["en"][key]
    if formula:
        if formula in m["formula"]:
            return m["formula"][formula]
        fk = m["_norm"](formula)
        if fk in m["formula"]:
            return m["formula"][fk]
    return None


# =============================================================================
# 导入 FluidData
# =============================================================================
def _v(x):
    """把值转为 float 或原样；None 保持 None。"""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x).strip())
    except Exception:
        return None


def import_fluids(cn_map: dict):
    wb = openpyxl.load_workbook(NOISE_XLSM, data_only=True, keep_links=False)
    ws = wb["FluidData"]

    # rows 101 = headers (Common Name/Formula/MW/Tc/Pc/(LmLim)/A/B/C/GFB/TB/k/omega/C1..C9/a..d/A..H/...)
    #      102 = units (Tc K / Pc barA / TB K)
    #      103.. = data rows

    fluids_noise = []
    for r in range(103, ws.max_row + 1):
        common_name = ws.cell(row=r, column=2).value
        if common_name is None or str(common_name).strip() == "":
            continue
        # 取 Water/Steam 的 Special name 做特判
        common_name = str(common_name).strip()
        formula = ws.cell(row=r, column=4).value
        valtek_no = ws.cell(row=r, column=3).value
        mw = _v(ws.cell(row=r, column=5).value)
        tc_k = _v(ws.cell(row=r, column=6).value)
        pc_bar = _v(ws.cell(row=r, column=7).value)
        antoine_t_lower = _v(ws.cell(row=r, column=8).value)
        a_a = _v(ws.cell(row=r, column=9).value)
        a_b = _v(ws.cell(row=r, column=10).value)
        a_c = _v(ws.cell(row=r, column=11).value)
        gfb = _v(ws.cell(row=r, column=12).value)
        tb_k = _v(ws.cell(row=r, column=13).value)
        k = _v(ws.cell(row=r, column=14).value)
        omega = _v(ws.cell(row=r, column=15).value)
        # Savage C1..C9 cols 16..24
        sav = [_v(ws.cell(row=r, column=c).value) for c in range(16, 25)]
        # Kyle a,b,c,d cols 25..28  (but there are two 'a' headers at col25 & col29;
        # in Excel data we see: for Acetylene col25=a=5.21, 26=b=0.012227, 27=c=-4.812e-06, 28=d=7.457e-10
        # Shomate A..H cols 33..40
        kyle = [_v(ws.cell(row=r, column=c).value) for c in range(25, 29)]
        shomate = [_v(ws.cell(row=r, column=c).value) for c in range(33, 41)]

        # 单位转换：Pc barA → kPa(abs)，Tc K 不变
        pc_kpa = pc_bar * 100.0 if pc_bar is not None else None

        # 自动判定默认相态：沸点 < 293K (20℃) 通常为气态
        default_state = "liquid"
        if tb_k is not None and tb_k < 293.0:
            default_state = "gas"
        # 特殊项
        if common_name.lower().startswith("water") or common_name.lower().startswith("steam"):
            default_state = "liquid"

        # 标准状态密度（用于介质库默认值）：
        #   液体密度：若不存在，可粗略取 700+kg/m³ 留空；
        #   气体密度：由理想气体标况公式 1.01325×MW/(8.314×273.15) kg/m³
        rho_gas = None
        if mw is not None and default_state == "gas":
            rho_gas = 101.325 * mw / (8.314 * 273.15)

        fluids_noise.append({
            "common_name": common_name,
            "formula": str(formula).strip() if formula else None,
            "valtek_no": int(valtek_no) if valtek_no is not None and isinstance(valtek_no, (int,float)) else None,
            "molecular_weight": mw,
            "critical_temp": tc_k,
            "critical_pressure": pc_kpa,
            "cp_cv_ratio": k,
            "boiling_point": tb_k,
            "acentric_factor": omega,
            "gf_constant": gfb,
            "antoine_a": a_a, "antoine_b": a_b, "antoine_c": a_c,
            "antoine_tmin_k": antoine_t_lower,
            "savage_c1": sav[0], "savage_c2": sav[1], "savage_c3": sav[2],
            "savage_c4": sav[3], "savage_c5": sav[4], "savage_c6": sav[5],
            "savage_c7": sav[6], "savage_c8": sav[7], "savage_c9": sav[8],
            "cp_a": kyle[0], "cp_b": kyle[1], "cp_c": kyle[2], "cp_d": kyle[3],
            "shomate_a": shomate[0], "shomate_b": shomate[1],
            "shomate_c": shomate[2], "shomate_d": shomate[3],
            "shomate_e": shomate[4], "shomate_f": shomate[5],
            "shomate_g": shomate[6], "shomate_h": shomate[7],
            "density_gas": rho_gas,
            "default_state": default_state,
        })

    with SessionLocal() as db:
        # 1) 清空前先保存旧 fluid_id -> fluid_name 映射，用于事后重建 process_cases 关联
        old_fluid_map = {}
        try:
            for row in db.execute(text("SELECT id, fluid_name FROM fluids")).fetchall():
                old_fluid_map[row[0]] = row[1]
            print(f"[介质库] 已备份旧 fluids 映射 {len(old_fluid_map)} 条")
        except Exception as e:
            print(f"[介质库] 备份旧 fluids 失败: {e}")

        # 2) 将 process_cases.fluid_id 列改为允许 NULL，解除外键引用
        try:
            db.execute(text("ALTER TABLE process_cases ALTER COLUMN fluid_id INT NULL"))
            db.commit()
        except Exception as e:
            print(f"[介质库] ALTER fluid_id NULL (可能已执行): {e}")

        # 3) 保存 process_cases 的 fluid_id -> case_id 关联（fluid_id 暂存到单独列做备份？
        #    这里简单保存 case_id -> old_fluid_id 映射，事后按名称关联新 id）
        case_fluid_backup = {}
        for row in db.execute(text("SELECT id, fluid_id FROM process_cases WHERE fluid_id IS NOT NULL")).fetchall():
            case_fluid_backup[row[0]] = row[1]
        print(f"[介质库] 已备份 process_cases.fluid_id 映射 {len(case_fluid_backup)} 条")

        # 4) 置空 process_cases.fluid_id，清空 fluids，重新导入
        db.execute(text("UPDATE process_cases SET fluid_id = NULL WHERE fluid_id IS NOT NULL"))
        db.commit()
        deleted = db.query(Fluid).delete()
        db.commit()
        print(f"[介质库] 已清空旧数据 {deleted} 条")

        created = 0
        no_cn = []
        for item in fluids_noise:
            name = item["common_name"]
            formula = item["formula"]

            f_obj = Fluid(fluid_name=name)
            # 写入所有字段（None 也写入，保持干净）
            f_obj.specific_name = name
            f_obj.formula = formula
            f_obj.valtek_no = item["valtek_no"]
            f_obj.molecular_weight = item["molecular_weight"]
            f_obj.critical_temp = item["critical_temp"]
            f_obj.critical_pressure = item["critical_pressure"]
            f_obj.cp_cv_ratio = item["cp_cv_ratio"]
            f_obj.boiling_point = item["boiling_point"]
            f_obj.acentric_factor = item["acentric_factor"]
            f_obj.gf_constant = item["gf_constant"]
            f_obj.antoine_a = item["antoine_a"]
            f_obj.antoine_b = item["antoine_b"]
            f_obj.antoine_c = item["antoine_c"]
            f_obj.antoine_tmin_k = item["antoine_tmin_k"]
            f_obj.savage_c1 = item["savage_c1"]
            f_obj.savage_c2 = item["savage_c2"]
            f_obj.savage_c3 = item["savage_c3"]
            f_obj.savage_c4 = item["savage_c4"]
            f_obj.savage_c5 = item["savage_c5"]
            f_obj.savage_c6 = item["savage_c6"]
            f_obj.savage_c7 = item["savage_c7"]
            f_obj.savage_c8 = item["savage_c8"]
            f_obj.savage_c9 = item["savage_c9"]
            f_obj.cp_a = item["cp_a"]
            f_obj.cp_b = item["cp_b"]
            f_obj.cp_c = item["cp_c"]
            f_obj.cp_d = item["cp_d"]
            f_obj.shomate_a = item["shomate_a"]
            f_obj.shomate_b = item["shomate_b"]
            f_obj.shomate_c = item["shomate_c"]
            f_obj.shomate_d = item["shomate_d"]
            f_obj.shomate_e = item["shomate_e"]
            f_obj.shomate_f = item["shomate_f"]
            f_obj.shomate_g = item["shomate_g"]
            f_obj.shomate_h = item["shomate_h"]
            f_obj.density_gas = item["density_gas"]
            f_obj.default_state = item["default_state"]

            # 特殊项：水/蒸汽
            if name.lower().startswith("water") or name.lower().startswith("steam"):
                f_obj.is_water = True
                # 液态水密度默认值
                if f_obj.density_liquid is None:
                    f_obj.density_liquid = 1000.0

            # 中文名称
            cn = lookup_cn(name, formula, cn_map)
            if cn:
                f_obj.fluid_name_cn = cn
            else:
                no_cn.append(name)

            db.add(f_obj)
            created += 1

        db.commit()
        total = db.query(Fluid).count()
        print(f"[介质库] 新增 {created} 条，共 {total} 条")
        if no_cn:
            print(f"  ! 缺少中文名称({len(no_cn)}): {no_cn[:20]} ...")

        # 5) 重建 process_cases 的 fluid_id 关联：旧名称 -> 新 id
        if case_fluid_backup and old_fluid_map:
            new_fluid_by_name = {f.fluid_name: f.id for f in db.query(Fluid).all()}
            restored = 0
            not_found = set()
            for case_id, old_fid in case_fluid_backup.items():
                old_name = old_fluid_map.get(old_fid)
                if old_name and old_name in new_fluid_by_name:
                    new_fid = new_fluid_by_name[old_name]
                    db.execute(text("UPDATE process_cases SET fluid_id = :fid WHERE id = :cid"),
                               {"fid": new_fid, "cid": case_id})
                    restored += 1
                else:
                    not_found.add(old_name or f"id={old_fid}")
            db.commit()
            print(f"[介质库] 已重建 process_cases.fluid_id: {restored}/{len(case_fluid_backup)}")
            if not_found:
                print(f"  ! 未匹配介质({len(not_found)}): {list(not_found)[:10]} ...")


# =============================================================================
# 导入 PipeData
# =============================================================================
_NPS_RE = re.compile(r"^([\d\.\/]+)in\s*\((\d+)mm\),\s*Schd\s*(.+)$")


def parse_lookup_key(s: str) -> tuple:
    """解析 NPS 标签，返回 (nps_label, dn_mm, schedule)。"""
    if not s:
        return (None, None, None)
    s = str(s).strip()
    m = _NPS_RE.match(s)
    if m:
        nps = m.group(1)
        dn = int(m.group(2))
        sch = m.group(3).strip()
        return (nps, dn, sch)
    # 兜底
    return (None, None, None)


def import_pipe_data():
    wb = openpyxl.load_workbook(NOISE_XLSM, data_only=True, keep_links=False)
    ws = wb["PipeData"]

    rows = []
    # data 从 row6 开始
    for r in range(6, ws.max_row + 1):
        key = ws.cell(row=r, column=1).value
        od_in = _v(ws.cell(row=r, column=2).value)
        thk_in = _v(ws.cell(row=r, column=3).value)
        id_in = _v(ws.cell(row=r, column=4).value)
        if key is None and od_in is None:
            continue
        nps_label, dn_mm, sch = parse_lookup_key(key)
        if od_in is None or thk_in is None or id_in is None:
            continue
        rows.append({
            "lookup_key": str(key).strip() if key else None,
            "nps_label": nps_label,
            "dn_mm": dn_mm,
            "schedule": sch,
            "od_in": od_in, "od_mm": round(od_in * 25.4, 5),
            "thk_in": thk_in, "thk_mm": round(thk_in * 25.4, 5),
            "id_in": id_in, "id_mm": round(id_in * 25.4, 5),
            "note_col_e": _v(ws.cell(row=r, column=5).value),
            "note_col_f": _v(ws.cell(row=r, column=6).value),
        })

    with SessionLocal() as db:
        inserted = updated = 0
        for row in rows:
            obj = db.query(PipeData).filter(PipeData.lookup_key == row["lookup_key"]).first()
            if obj is None:
                obj = PipeData(**row)
                db.add(obj)
                inserted += 1
            else:
                for k, v in row.items():
                    setattr(obj, k, v)
                updated += 1
        db.commit()
        total = db.query(PipeData).count()
        print(f"[PipeData] 新增 {inserted} / 更新 {updated}，共 {total} 条")


# =============================================================================
# 导入 ValveData
# =============================================================================
def import_valve_sizing_indices():
    """导入 ValveData 上半段 Table 1. Valve Sizing Indices (row4..row23)。
    先清空表中误导（通径矩阵行）再重新写入。"""
    wb = openpyxl.load_workbook(NOISE_XLSM, data_only=True, keep_links=False)
    ws = wb["ValveData"]

    rows = []
    # row4 - row23 是标准阀型系数；row26之后是通径额定尺寸矩阵
    for r in range(4, 24):
        valve_type = ws.cell(row=r, column=1).value
        if not valve_type:
            continue
        no = ws.cell(row=r, column=8).value
        if no is not None:
            # 统一 str: 数字保留整数/短浮点，"Calc'd" 原样
            if isinstance(no, float) and no.is_integer():
                no_str = str(int(no))
            else:
                no_str = str(no)
        else:
            no_str = None
        rows.append({
            "valve_type": str(valve_type).strip(),
            "cv_per_d2": _v(ws.cell(row=r, column=2).value),
            "fl": _v(ws.cell(row=r, column=3).value),
            "xt": _v(ws.cell(row=r, column=4).value),
            "fd": _v(ws.cell(row=r, column=5).value),
            "kc": _v(ws.cell(row=r, column=6).value),
            "opt_pn": (int(ws.cell(row=r, column=7).value)
                       if ws.cell(row=r, column=7).value is not None else None),
            "no_coefficient": no_str,
            "aeta_db": _v(ws.cell(row=r, column=9).value),
            "stp": _v(ws.cell(row=r, column=10).value),
            "d_spl_sw_db": _v(ws.cell(row=r, column=11).value),
            "fd_flag": (int(ws.cell(row=r, column=12).value)
                        if ws.cell(row=r, column=12).value is not None else None),
        })

    with SessionLocal() as db:
        # 清理已误插入的通径类行（含 'in (' 或数值 cv_per_d2 >= 1.0 的错行）
        db.query(ValveSizingIndex).filter(ValveSizingIndex.valve_type.like("%in (%")).delete(synchronize_session=False)
        inserted = updated = 0
        for row in rows:
            obj = db.query(ValveSizingIndex).filter(
                ValveSizingIndex.valve_type == row["valve_type"]).first()
            if obj is None:
                obj = ValveSizingIndex(**row)
                db.add(obj)
                inserted += 1
            else:
                for k, v in row.items():
                    setattr(obj, k, v)
                updated += 1
        db.commit()
        total = db.query(ValveSizingIndex).count()
        print(f"[ValveData-Indices] 新增 {inserted} / 更新 {updated}，共 {total} 条")


def import_valve_nominal_sizes():
    """导入 ValveData 下半段 Nominal Valve Size 通径-压力等级内径矩阵 (row28..row51)。"""
    wb = openpyxl.load_workbook(NOISE_XLSM, data_only=True, keep_links=False)
    ws = wb["ValveData"]

    rows = []
    for r in range(28, 52):
        label = ws.cell(row=r, column=1).value
        if not label:
            continue
        rows.append({
            "size_label": str(label).strip(),
            "nps_in": _v(ws.cell(row=r, column=2).value),
            "dn_mm": (int(ws.cell(row=r, column=3).value)
                     if ws.cell(row=r, column=3).value is not None else None),
            "id_class_150":  _v(ws.cell(row=r, column=4).value),
            "id_class_300":  _v(ws.cell(row=r, column=5).value),
            "id_class_600":  _v(ws.cell(row=r, column=6).value),
            "id_class_900":  _v(ws.cell(row=r, column=7).value),
            "id_class_1500": _v(ws.cell(row=r, column=8).value),
            "id_class_2500": _v(ws.cell(row=r, column=9).value),
            "id_class_4500": _v(ws.cell(row=r, column=10).value),
        })

    with SessionLocal() as db:
        inserted = updated = 0
        for row in rows:
            obj = db.query(ValveNominalSize).filter(
                ValveNominalSize.size_label == row["size_label"]).first()
            if obj is None:
                obj = ValveNominalSize(**row)
                db.add(obj)
                inserted += 1
            else:
                for k, v in row.items():
                    setattr(obj, k, v)
                updated += 1
        db.commit()
        total = db.query(ValveNominalSize).count()
        print(f"[ValveData-NominalSize] 新增 {inserted} / 更新 {updated}，共 {total} 条")


# =============================================================================
# main
# =============================================================================
def main():
    if not NOISE_XLSM.exists():
        print(f"ERROR: {NOISE_XLSM} 不存在")
        sys.exit(1)
    if not CN_XLSX.exists():
        print(f"WARN: {CN_XLSX} 不存在，跳过中文名称匹配")
    ensure_tables()
    cn_map = load_cn_map() if CN_XLSX.exists() else {"en": {}, "formula": {}, "_norm": lambda s: s}
    import_fluids(cn_map)
    import_pipe_data()
    import_valve_sizing_indices()
    import_valve_nominal_sizes()
    print("\n全部导入完成。")


if __name__ == "__main__":
    main()
