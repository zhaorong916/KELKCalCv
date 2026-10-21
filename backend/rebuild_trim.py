"""
重建 valve_trim_sizes 表并从 Excel 正确导入数据 v3

修复:
- BT120/BT210: 停止于 "Choices for Graphs" 行
- GV120/GV410: 修复 header 检测 + 数据起始行
- GV110: 独立解析器 (有 Cv 数据)
"""
import os

import pyodbc
import openpyxl
import re
from dotenv import load_dotenv

load_dotenv()
DB_CONN_STR = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={os.environ['DB_HOST']},{os.environ.get('DB_PORT', '1433')};"
    f"DATABASE={os.environ['DB_NAME']};UID={os.environ['DB_USER']};PWD={os.environ['DB_PASSWORD']}"
)
EXCEL_PATH = r'd:\KELK办公\信息化工作\207 自研系统\KELKCalCv\参考文件\KELK CalcCv Valve & Trim Factors.xlsm'

TARGET_SHEETS = {
    'GC120':  {'type': 'globe_eq_linear'},
    'GC210':  {'type': 'globe_eq_linear'},
    'GV120':  {'type': 'globe_sizeonly'},
    'GV110':  {'type': 'globe_with_cv'},   # GV110 有 Cv
    'GV410':  {'type': 'globe_with_cv'},   # GV410 结构同 GV110
    'BT120':  {'type': 'butterfly_60_90'},
    'BT110':  {'type': 'butterfly_60_90'},
    'BT210':  {'type': 'butterfly_60_90'},
    'BC110':  {'type': 'ball_metal_soft'},
    'BE120':  {'type': 'ball_metal_soft'},
}


def drop_and_recreate_table(cur):
    cur.execute("IF OBJECT_ID('valve_trim_sizes', 'U') IS NOT NULL DROP TABLE valve_trim_sizes")
    cur.execute("""
    CREATE TABLE valve_trim_sizes (
        id              INT IDENTITY(1,1) PRIMARY KEY,
        series_code     VARCHAR(32)   NOT NULL,
        asme_class      VARCHAR(16),
        dn_inch         VARCHAR(16),
        dn_mm           FLOAT,
        trim_inch       VARCHAR(16),
        plug_mm         FLOAT,
        stroke_mm       FLOAT,
        trim_type       VARCHAR(64),
        cv_min          FLOAT,
        cv_eq           FLOAT,
        cv_linear       FLOAT,
        cv_60deg        FLOAT,
        cv_90deg        FLOAT,
        cv_metal_seat   FLOAT,
        cv_soft_seat    FLOAT,
        stk_index_pct   FLOAT,
        remark          VARCHAR(255),
        is_active       BIT           DEFAULT 1,

        CONSTRAINT uq_trim_size UNIQUE (series_code, asme_class, dn_mm, trim_inch, plug_mm, stroke_mm, trim_type)
    )
    """)
    cur.execute("CREATE INDEX ix_trim_series ON valve_trim_sizes(series_code)")
    print("  ✓ 表重建完成")


def parse_dn_mm(dn_str):
    if not dn_str:
        return None, None
    m = re.match(r'^(.+?)\s*\((\d+(?:\.\d+)?)\)\s*$', str(dn_str).strip())
    if m:
        return m.group(1).strip(), float(m.group(2))
    try:
        return str(dn_str), float(dn_str)
    except:
        return str(dn_str).strip(), None


def is_number_or_fraction(s):
    if s is None:
        return False
    s = str(s).strip()
    if not s:
        return False
    if re.match(r'^[\d]+\.?[\d]*$', s):
        return True
    if re.match(r'^[\d]+\s*/\s*[\d]+$', s):
        return True
    if re.match(r'^[\d]+\s+[\d]+\s*/\s*[\d]+$', s):
        return True
    return False


def safe_float(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s or s == '-' or s == '—':
        return None
    try:
        return float(s)
    except:
        return None


def is_end_of_table(ws, r):
    """判断是否已到 Table 数据结束行"""
    for c in range(1, 15):
        v = ws.cell(row=r, column=c).value
        if v:
            s = str(v).strip()
            if any(kw in s for kw in ['Choices for', 'Table 2', 'Cv/Cvrated']):
                return True
    return False


# ================================================================
def parse_globe_eq_linear(ws, sheet_name):
    """GC120/GC210: header R09, data R13+"""
    header_r = None
    for r in range(1, 20):
        b_val = ws.cell(row=r, column=2).value
        if b_val and 'ASME Pressure Rating' in str(b_val):
            header_r = r
            break
    if header_r is None:
        print(f"  ✗ {sheet_name}: 找不到 header")
        return []

    data_start = header_r + 4
    rows, cur_asme, cur_dn_inch, cur_dn_mm = [], None, None, None

    for r in range(data_start, ws.max_row + 1):
        if is_end_of_table(ws, r):
            break
        b_val = ws.cell(row=r, column=2).value
        c_val = ws.cell(row=r, column=3).value
        d_val = ws.cell(row=r, column=4).value
        e_val = ws.cell(row=r, column=5).value
        f_val = ws.cell(row=r, column=6).value
        g_val = ws.cell(row=r, column=7).value
        h_val = ws.cell(row=r, column=8).value

        if b_val is not None and str(b_val).strip():
            b_str = str(b_val).strip()
            if '#' in b_str or 'to' in b_str.lower():
                cur_asme = b_str
            elif '(' in b_str:
                cur_dn_inch, cur_dn_mm = parse_dn_mm(b_str)

        if c_val is not None and str(c_val).strip():
            c_str = str(c_val).strip()
            if '(' in c_str:
                cur_dn_inch, cur_dn_mm = parse_dn_mm(c_str)

        trim_inch = str(d_val).strip() if d_val and str(d_val).strip() else None
        if not trim_inch or not is_number_or_fraction(trim_inch):
            continue

        plug_mm = safe_float(e_val)
        stroke_mm = safe_float(f_val)
        cv_eq = safe_float(g_val)
        cv_linear = safe_float(h_val)

        rows.append({
            'series_code': sheet_name, 'asme_class': cur_asme,
            'dn_inch': cur_dn_inch, 'dn_mm': cur_dn_mm,
            'trim_inch': trim_inch, 'plug_mm': plug_mm, 'stroke_mm': stroke_mm,
            'cv_eq': cv_eq, 'cv_linear': cv_linear,
        })

    rows = [r for r in rows if r['plug_mm'] is not None or r['stroke_mm'] is not None or r['cv_eq'] is not None]
    return rows


# ================================================================
def parse_butterfly_60_90(ws, sheet_name):
    """BT120/BT110/BT210: header R09, data R12+"""
    header_r = None
    for r in range(1, 20):
        b_val = ws.cell(row=r, column=2).value
        if b_val and ('ASME Pressure Rating' in str(b_val) or 'Body and Trim' in str(b_val)):
            header_r = r
            break
    if header_r is None:
        print(f"  ✗ {sheet_name}: 找不到 header")
        return []

    data_start = header_r + 3
    rows, cur_asme = [], None

    for r in range(data_start, ws.max_row + 1):
        if is_end_of_table(ws, r):
            break
        b_val = ws.cell(row=r, column=2).value
        c_val = ws.cell(row=r, column=3).value
        d_val = ws.cell(row=r, column=4).value
        e_val = ws.cell(row=r, column=5).value
        f_val = ws.cell(row=r, column=6).value
        g_val = ws.cell(row=r, column=7).value

        if b_val is not None and str(b_val).strip():
            b_str = str(b_val).strip()
            if '#' in b_str or 'to' in b_str.lower():
                cur_asme = b_str

        dn_source = None
        if b_val and '(' in str(b_val):
            dn_source = str(b_val).strip()
        elif c_val and '(' in str(c_val):
            dn_source = str(c_val).strip()
        elif b_val and is_number_or_fraction(b_val):
            dn_source = str(b_val).strip()
        elif c_val and is_number_or_fraction(c_val):
            dn_source = str(c_val).strip()
        if dn_source is None:
            continue

        dn_inch, dn_mm = parse_dn_mm(dn_source)
        if dn_mm is None or dn_mm < 10:  # 过滤垃圾行 (dn_mm=0.005 之类)
            continue

        cv_min = safe_float(c_val)
        cv_60 = safe_float(d_val)
        cv_90 = safe_float(e_val)
        stk = safe_float(f_val)

        if cv_min is None and safe_float(d_val) is not None:
            cv_min = safe_float(d_val)
            cv_60 = safe_float(e_val)
            cv_90 = safe_float(f_val)
            stk = safe_float(g_val)

        rows.append({
            'series_code': sheet_name, 'asme_class': cur_asme,
            'dn_inch': dn_inch, 'dn_mm': dn_mm,
            'cv_min': cv_min, 'cv_60deg': cv_60, 'cv_90deg': cv_90,
            'stk_index_pct': stk,
        })

    return rows


# ================================================================
def parse_ball_metal_soft(ws, sheet_name):
    """BC110/BE120: header 无 ASME 列"""
    header_r = None
    for r in range(1, 20):
        v = ws.cell(row=r, column=2).value
        if v and ('Body and Trim' in str(v) or 'Nominal Valve Size' in str(v)):
            if 'Trim Type' not in str(ws.cell(row=r, column=1).value or ''):
                header_r = r
                break
    if header_r is None:
        print(f"  ✗ {sheet_name}: 找不到 header")
        return []

    data_start = header_r + 3
    rows = []

    for r in range(data_start, ws.max_row + 1):
        if is_end_of_table(ws, r):
            break
        b_val = ws.cell(row=r, column=2).value
        c_val = ws.cell(row=r, column=3).value
        d_val = ws.cell(row=r, column=4).value
        e_val = ws.cell(row=r, column=5).value
        f_val = ws.cell(row=r, column=6).value

        if b_val is None:
            continue
        dn_source = str(b_val).strip()
        if not ('(' in dn_source or is_number_or_fraction(b_val)):
            continue

        dn_inch, dn_mm = parse_dn_mm(dn_source)
        if dn_mm is None:
            continue

        cv_min = safe_float(c_val)
        cv_metal = safe_float(d_val)
        cv_soft = safe_float(e_val)
        stk = safe_float(f_val)

        rows.append({
            'series_code': sheet_name,
            'dn_inch': dn_inch, 'dn_mm': dn_mm,
            'cv_min': cv_min, 'cv_metal_seat': cv_metal, 'cv_soft_seat': cv_soft,
            'stk_index_pct': stk,
        })

    return rows


# ================================================================
def parse_globe_sizeonly(ws, sheet_name):
    """GV120/GV410: 数据从 B 列开始 (A 列空)
    B=Trim Type/DN, C=ASME, D=DN/Stroke, E=Stroke/Plug Min, F=Plug Min/Plug Max, G=Plug Max/Cv
    GV120 header = 'Trim Type', GV410 header = 'Nominal Valve Size'
    """
    header_r = None
    for r in range(1, 20):
        b_val = ws.cell(row=r, column=2).value
        if b_val and ('Trim Type' in str(b_val) or 'Nominal Valve Size' in str(b_val)):
            header_r = r
            break
    if header_r is None:
        print(f"  ✗ {sheet_name}: 找不到 header")
        return []

    data_start = header_r + 3
    rows, cur_trim_type, cur_asme = [], None, None
    
    # 读取压力等级 (Row 1-10 找 Pressure/ASME)
    for r in range(1, 10):
        for c in range(1, 15):
            v = ws.cell(row=r, column=c).value
            if v and isinstance(v, str) and ('pressure' in v.lower() or 'asme' in v.lower()):
                for c2 in range(c+1, 15):
                    v2 = ws.cell(row=r, column=c2).value
                    if v2 is not None and str(v2).strip():
                        cur_asme = str(v2).strip()
                        break
                if cur_asme:
                    break
        if cur_asme:
            break

    for r in range(data_start, ws.max_row + 1):
        if is_end_of_table(ws, r):
            break
        b_val = ws.cell(row=r, column=2).value
        c_val = ws.cell(row=r, column=3).value
        d_val = ws.cell(row=r, column=4).value
        e_val = ws.cell(row=r, column=5).value
        f_val = ws.cell(row=r, column=6).value
        g_val = ws.cell(row=r, column=7).value

        # ASME 在 C 列（GV120 特有）或从 Row 4 读取
        if c_val is not None and str(c_val).strip():
            c_str = str(c_val).strip()
            if '#' in c_str or 'to' in c_str.lower() or 'Standard' in c_str or 'With' in c_str:
                cur_asme = c_str

        # Trim Type 在 B 列（GV120 特有）
        if b_val is not None and str(b_val).strip():
            b_str = str(b_val).strip()
            if '#' in b_str or 'to' in b_str.lower():
                cur_asme = b_str
            elif not ('(' in b_str or is_number_or_fraction(b_val)):
                cur_trim_type = b_str.replace('\n', ' ')

        if d_val is None:
            continue
        dn_source = str(d_val).strip()
        if not ('(' in dn_source or is_number_or_fraction(d_val)):
            continue

        dn_inch, dn_mm = parse_dn_mm(dn_source)
        if dn_mm is None or dn_mm < 5:
            continue

        stroke_mm = safe_float(e_val)
        plug_min = safe_float(f_val)
        plug_max = safe_float(g_val)

        rows.append({
            'series_code': sheet_name, 'asme_class': cur_asme,
            'dn_inch': dn_inch, 'dn_mm': dn_mm,
            'trim_type': cur_trim_type, 'stroke_mm': stroke_mm, 'plug_mm': plug_min,
            'remark': f'Plug Max={plug_max}' if plug_max else None,
        })

    return rows


# ================================================================
def parse_globe_with_cv(ws, sheet_name):
    """GV110/GV410: 有 Cv 数据, 结构特殊"""
    header_r = None
    for r in range(1, 20):
        b_val = ws.cell(row=r, column=2).value
        if b_val and 'Nominal Valve Size' in str(b_val):
            header_r = r
            break
    if header_r is None:
        print(f"  ✗ {sheet_name}: 找不到 header")
        return []

    data_start = header_r + 3
    rows = []
    
    # 读取压力等级 (Row 1-8 找 Pressure Ratings / ASME)
    cur_asme = None
    for r in range(1, 10):
        for c in range(1, 15):
            v = ws.cell(row=r, column=c).value
            if v and isinstance(v, str) and ('pressure' in v.lower() or 'asme' in v.lower()):
                # 找右边第一个非空值
                for c2 in range(c+1, 15):
                    v2 = ws.cell(row=r, column=c2).value
                    if v2 is not None and str(v2).strip():
                        cur_asme = str(v2).strip()
                        break
                if cur_asme:
                    break
        if cur_asme:
            break

    for r in range(data_start, ws.max_row + 1):
        if is_end_of_table(ws, r):
            break
        b_val = ws.cell(row=r, column=2).value
        c_val = ws.cell(row=r, column=3).value  # Plug Min
        d_val = ws.cell(row=r, column=4).value  # Plug Max
        f_val = ws.cell(row=r, column=6).value  # Plug
        g_val = ws.cell(row=r, column=7).value  # Stroke
        h_val = ws.cell(row=r, column=8).value  # Min Cv
        i_val = ws.cell(row=r, column=9).value  # Rated Cv

        if b_val is None:
            continue
        dn_source = str(b_val).strip()
        if not ('(' in dn_source or is_number_or_fraction(b_val)):
            continue

        dn_inch, dn_mm = parse_dn_mm(dn_source)
        if dn_mm is None:
            continue

        plug_min = safe_float(c_val)
        plug_max = safe_float(d_val)
        plug_size = safe_float(f_val)
        stroke_mm = safe_float(g_val)
        cv_min = safe_float(h_val)
        cv_rated = safe_float(i_val)

        rows.append({
            'series_code': sheet_name, 'asme_class': cur_asme,
            'dn_inch': dn_inch, 'dn_mm': dn_mm,
            'trim_inch': None,
            'plug_mm': plug_size or plug_min,
            'stroke_mm': stroke_mm,
            'cv_min': cv_min,
            'cv_eq': cv_rated,
            'remark': f'Plug Min={plug_min} Max={plug_max}' if plug_min or plug_max else None,
        })

    return rows


def insert_rows(cur, rows):
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ', '.join(['?'] * len(cols))
    col_str = ', '.join(cols)
    sql = f"INSERT INTO valve_trim_sizes ({col_str}) VALUES ({placeholders})"

    count = 0
    for r in rows:
        vals = [r.get(c) for c in cols]
        try:
            cur.execute(sql, vals)
            count += 1
        except Exception as ex:
            pass  # 忽略唯一约束冲突
    return count


def main():
    conn = pyodbc.connect(DB_CONN_STR)
    cur = conn.cursor()

    print("=== Step 1: 重建表 ===")
    drop_and_recreate_table(cur)

    print("\n=== Step 2: 解析 Excel ===")
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True, keep_vba=True)

    total = 0
    for sn, meta in TARGET_SHEETS.items():
        if sn not in wb.sheetnames:
            print(f"  {sn}: Sheet 不存在，跳过")
            continue
        ws = wb[sn]
        print(f"\n  --- {sn} ({meta['type']}) ---")

        t = meta['type']
        parsers = {
            'globe_eq_linear': parse_globe_eq_linear,
            'globe_sizeonly': parse_globe_sizeonly,
            'globe_with_cv': parse_globe_with_cv,
            'butterfly_60_90': parse_butterfly_60_90,
            'ball_metal_soft': parse_ball_metal_soft,
        }
        rows = parsers[t](ws, sn) if t in parsers else []

        print(f"    解析 {len(rows)} 行", end='')
        n = insert_rows(cur, rows)
        print(f"  插入 {n} 行")
        total += n

    wb.close()
    conn.commit()

    print(f"\n=== Step 3: 验证 ===")
    cur.execute("SELECT series_code, COUNT(*) FROM valve_trim_sizes GROUP BY series_code ORDER BY series_code")
    for r in cur.fetchall():
        print(f"  {r[0]:20s} {r[1]:4d} 行")

    cur.execute("SELECT TOP 5 series_code, asme_class, dn_inch, dn_mm, trim_inch, plug_mm, stroke_mm, cv_eq, cv_linear FROM valve_trim_sizes WHERE series_code='GC120' ORDER BY id")
    print("\n  GC120:")
    for r in cur.fetchall(): print(f"    {r}")

    cur.execute("SELECT TOP 3 series_code, asme_class, dn_inch, dn_mm, cv_min, cv_60deg, cv_90deg, stk_index_pct FROM valve_trim_sizes WHERE series_code='BT120' ORDER BY id")
    print("\n  BT120:")
    for r in cur.fetchall(): print(f"    {r}")

    cur.execute("SELECT TOP 3 series_code, dn_inch, dn_mm, cv_min, cv_metal_seat, cv_soft_seat, stk_index_pct FROM valve_trim_sizes WHERE series_code='BC110' ORDER BY id")
    print("\n  BC110:")
    for r in cur.fetchall(): print(f"    {r}")

    cur.execute("SELECT TOP 3 series_code, asme_class, dn_inch, dn_mm, trim_type, stroke_mm, plug_mm FROM valve_trim_sizes WHERE series_code='GV120' ORDER BY id")
    print("\n  GV120:")
    for r in cur.fetchall(): print(f"    {r}")

    cur.execute("SELECT TOP 3 series_code, dn_inch, dn_mm, cv_min, cv_eq, stroke_mm FROM valve_trim_sizes WHERE series_code='GV110' ORDER BY id")
    print("\n  GV110:")
    for r in cur.fetchall(): print(f"    {r}")

    conn.close()


if __name__ == '__main__':
    main()
