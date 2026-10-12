***

name: "excel-to-mssql-import"
description: "解析 Excel(.xlsx/.xlsm) 到 SQL Server：按数据字典优先扩列/其次增表，幂等 upsert 导入+抽样校验。当用户要求把 Excel 文件数据写入现有项目的 SQL Server 数据库时调用。"
------------------------------------------------------------------------------------------------------------------------------

# Excel → SQL Server 导入工作流 (excel-to-mssql-import)

本 Skill 固化「Excel/XLSM 数据解析 → DB 结构对齐（优先扩列/其次增表）→ 幂等 UPSERT → 自动抽样校验」四步流程，避免每次手工重复写临时脚本时出现的**列遗漏 / 主键冲突 / 角度/单位列未标准化 / 未校验就交付**四大类问题。

***

## 0. 前置检查（Skill 启动时必跑）

1. 确认工作区内已有数据库连接信息来源（以下任一即可）：

   - `.env` / `config.py` 中存在 `MSSQL_URL` 或 `DRIVER / SERVER / DATABASE / UID / PWD`

   - 已有 `app/models/__init__.py` 定义了目标表 ORM 模型
2. 在 Skill 目录外，要求用户提供 4 个关键参数（缺失则 AskUserQuestion）：

   - `excel_path`：绝对路径

   - `目标表名`（主表）：如 `valve_trim_sizes`

   - `关联元数据表名`（可选）：如 `valve_types`（Header / Factor Group 需回填）

   - `幂等键列`（复合主键字段集合）：如 `(series_code, asme_class, dn_mm, trim_code, remark)`
3. 用 `openpyxl` 加载 workbook（`data_only=True`，禁用公式字符串），打印 `wb.sheetnames` 给用户**确认哪几个 sheet 需要解析**。

***

## 1. Step-A：Excel 结构推断 & 数据字典对齐

### 1.1 自动推断三类 Sheet

- **Series Sheet**：以系列代码命名（如 `GC120 / BT210`），含 `DN 列 / Cv 列 / 压力等级` 等明细

- **Factor / Curve Sheet**：如 `Eq% Data / FL Data / Kc Data / Fd Data`，**必须**以"多项式系数表"形式解析，输出 `(eq_index, A0..An)` 或 `(eq_index, P0..Pn)`

- **Info/Header Sheet**：单行列名-值，更新元数据表 `valve_types.*_default / factor_group / eq_index`

### 1.2 数据字典对齐（强制走"扩列 > 增表"）

先用 `INFORMATION_SCHEMA.COLUMNS` 查询目标表：

```sql
SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?
```

**对每个 Excel 字段对比：**

| 情况                                                                        | 处理                                                                                     |
| ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| 字段不存在，但**语义可复用现有列**（例：`opening_deg` 无对应列 → 合并进 `remark` 并加前缀 `"XX deg "`） | 走"语义映射"，禁止直接 ALTER                                                                     |
| 字段不存在，且为**独立事实字段**（例：多项式 `a0~a6` / 系列默认系数 `fl_default`）                   | **ALTER TABLE … ADD col FLOAT/VARCHAR NULL**；仅当已有同类空列时合并                               |
| 字段长度超出现有 `VARCHAR(n)`                                                     | `ALTER TABLE … ALTER COLUMN col VARCHAR(255)`                                          |
| 整列完全是新对象 / 新维度（例：`valve_factor_curves` 从未存在）                              | 才 `CREATE TABLE`，并**必须**同步更新 `models/__init__.py` ORM + `schemas/__init__.py` Pydantic |

⚠️ **禁止**为 1-2 个辅助字段新建表；违反时强制回退为扩列。

***

## 2. Step-B：字段标准化（导入前清洗）

所有解析器统一调用标准清洗函数，避免后续计算引擎报错：

```python
# 规范 1：角度 / 行程字符串 → 数值 (存失败才塞 remark)
import re
def parse_deg(val) -> int | None:
    if val is None: return None
    m = re.search(r'(\d+)\s*(?:Deg|deg|°)', str(val))
    return int(m.group(1)) if m else None

# 规范 2：DN mm <-> inch 互查 (valve_sizing_indices 若已存数据就直接 JOIN；否则按 25.4 转换)
# 规范 3：压力等级标准化 → "150# / 300#" 统一格式，不允许出现 "150 Lb" 混写
# 规范 4：数值空值 → None（禁止 '' 或 'NA' 塞进 FLOAT 列）
# 规范 5：系数多项式阶 → None 填 0.0（否则 Σ Ai*x^i 会抛 TypeError）
```

***

## 3. Step-C：幂等 UPSERT 导入

### 3.1 Header / 元数据（valve\_types）

```python
cursor.execute("SELECT 1 FROM valve_types WHERE series_code=?", (series,))
if cursor.fetchone():
    cursor.execute("UPDATE valve_types SET factor_group=?, eq_index=?, fl_default=?, xt_default=?, fd_default=?, kc_default=?, trim_option_pressure=?, trim_option_opening=?, trim_option_types=? WHERE series_code=?",
                   (...))
else:
    cursor.execute("INSERT INTO valve_types (series_code, series_name, valve_category, ...) VALUES (...)")
```

### 3.2 明细 / 曲线表

**先用** **`DELETE`** **清掉本次导入涉及的窗口范围**（比逐行冲突捕获更安全，也避免唯一键复合 remark 出错）：

```python
cursor.execute(f"DELETE FROM {table} WHERE series_code IN ({series_placeholders})", series_list)
cursor.execute(f"DELETE FROM valve_factor_curves WHERE factor_type IN ('eqcv','fl','kc','fd')")
cursor.executemany(insert_sql, rows)
```

**仅当** `DELETE` 会破坏历史数据时（表已有历史手工录入数据），才用 `try INSERT except IntegrityError: UPDATE` 逐行模式。

### 3.3 `valve_factor_curves` 专用规范

- `eqcv` 因子 → `a0..a6` 六次多项式，缺项补 `0.0`

- `fl / kc / fd` → `p0..p4` 四次多项式，`value_min / value_max` 必须存入（用于计算引擎钳制）

- `group_name = factor_group`，`eq_index` 从 1 连续编号

### 3.4 `valve_trim_sizes` 专用规范

- `characteristic` 默认 `'eq'`（等百分比，XLSM 原始 `=%` 标记统一映射）

- `stk_index_pct`：Sheet 有 Stroke Index 就填；没有就 `NULL`（不要伪造 100/0）

- `remark`：**必塞 opening\_deg 文本前缀** **`"60 deg "`** **/** **`"90 deg "`**（原表无 opening\_deg 列的兜底存储）

***

## 4. Step-D：抽样校验（必须输出 3 组指标）

导入完成后**务必**生成 `_verify_*.py` 一次性脚本跑校验，然后删除脚本（不许留临时文件）：

| 指标组                 | SQL                                                                                                                                                                                            | 判定                                   |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| ① 行数统计              | `SELECT factor_type, COUNT(*) FROM valve_factor_curves GROUP BY factor_type`                                                                                                                   | eqcv ≈ 40×阶数？fl/kc/fd 每组 4\~10 条才算正常 |
| ② 元数据回填             | `SELECT TOP 5 series_code, factor_group, eq_index, fl_default FROM valve_types WHERE series_code IN (...)`                                                                                     | 目标系列全部 non-null 才算 PASS              |
| ③ Cv / 多项式抽样**并回代** | `SELECT dn_mm, cv_rated FROM valve_trim_sizes WHERE series_code='GC120' AND dn_mm=100 AND asme_class='< 600#'; SELECT a0..a6 FROM valve_factor_curves WHERE factor_type='eqcv' AND eq_index=1` | 数值与 Excel 中肉眼读取值差异 ≤ 1e-4            |

**校验输出格式**：每项开头打印 `✅ PASS` / `❌ FAIL`，任一项 FAIL 必须立即停止交付，回到 Step-A/B 排查字段映射。

***

## 5. Models / Schemas 同步检查

完成 DDL 后必须打开 `backend/app/models/__init__.py` 和 `backend/app/schemas/__init__.py`：

### 5.1 Model 同步项

- `ValveType`：`factor_group / eq_index / fl_default / xt_default / fd_default / kc_default / trim_option_pressure / trim_option_opening / trim_option_types` 九列齐

- `ValveFactorCurve`：`a0..a6 + p0..p4 + group_name + value_min/max` 齐

- `ValveTrimSize`：如本次新增列必须立刻补 ORM 字段（含 `comment=`）

### 5.2 Schema 同步项

- `ValveTrimSizeOut`（Pydantic BaseModel）字段集与 Model 字段 1:1

- `ValveFactorCurveOut` 同上

***

## 6. 交付输出清单（用户每次调用该 Skill 后必须收到）

1. ✅ **DDL 变更清单**（ALTER/CREATE 语句逐条列出，禁止模糊说"已更新"）
2. ✅ **Models + Schemas 改动文件路径**（点击可跳转的链接）
3. ✅ **导入结果统计表**：每表写入多少行、主系列各多少行
4. ✅ **3 组抽样校验结果**（通过/失败，含值）
5. ⚠️ **遗留问题列表**（如：哪些 Series Sheet 解析 0 行需要补充模板适配）

***

## 7. 典型触发示例（供 Skill 路由匹配）

- ✅ 「把 `参考文件/XXX.xlsm` 的计算数据写入现有数据库」

- ✅ 「分析 XX.xlsx 的数据结构，现有表字段不够，补齐字段后导入」

- ✅ 「上次导入的阀系数/额定 Cv 再跑一遍新版 Excel」

- ❌ 不接：纯报表制作、前端 UI 调整、纯 API 新端点开发（这些交给对应 Skill）

***

## 8. 安全红线（禁止操作）

- ❌ 禁止把数据库账号密码硬编码写进 SKILL.md（一律从环境或已有配置读取）

- ❌ 禁止 `DELETE FROM 表` 不带 WHERE（只允许按本次导入的 series\_code / factor\_type 窗口删除）

- ❌ 禁止不跑第 4 步抽样就直接交付

- ❌ 禁止在 `valve_types.series_code` 上破坏唯一索引（UPSERT 时必须以它为匹配键）

