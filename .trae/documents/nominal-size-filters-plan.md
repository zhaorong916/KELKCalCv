# 计划：增加公称通径和阀芯尺寸筛选器，自动确定 Plug Size

## 背景

当前 GC120 的筛选流程为：Trim Type → Pressure Rating → Plug Size (mm)，用户直接选择 plug_mm 数值。但 GC120 的 `ValveTrimSize` 表每行同时包含 `dn_mm`（公称通径）、`trim_inch`（阀芯公称尺寸，如 "5/8"、"1"、"1 1/2"）、`plug_mm` 三者，存在 `(压力等级, dn_mm, trim_inch) → plug_mm` 的明确行级映射。

用户要求将"公称通径 (Nominal Valve Size)"和"阀芯尺寸 (Nominal Trim Size)"作为筛选条件加入，由这两个选项自动确定 plug_size 值，替代直接选择 mm 数值的方式。GV120 已有 `nominal_dn` 筛选器且无 `trim_inch` 数据，保持不变。

## 改动范围

### 1. 后端：种子函数 — 插入/更新 ValveFilterConfig 行

**文件**：[valve_types.py](file:///d:/KELK办公/信息化工作/207%20自研系统/KELKCalCv/backend/app/api/valve_types.py) （`seed_valve_types` 函数附近，约 line 63）

新增 `seed_valve_filter_config(db)` 函数，按 `(series_code, filter_key)` 自然键做 upsert（查询存在则更新，不存在则插入）。对 GC120 插入/更新以下行：

| filter_key | display_label | order | enabled | source | dependent_on | value_field |
|---|---|---|---|---|---|---|
| nominal_dn | Nominal Valve Size | 25 | True | cascade | pressure_rating | dn_mm |
| nominal_trim | Nominal Trim Size | 28 | True | cascade | pressure_rating,nominal_dn | trim_inch |
| plug_size | Plug Size | 30 | **False** | cascade | pressure_rating | plug_mm |

关键：将 GC120 的 `plug_size` 筛选器设为 `is_enabled=False`（从渲染中移除），新增 `nominal_dn` 和 `nominal_trim` 两个级联筛选器。仅对 `trim_inch` 有数据的系列处理（用 `db.query(ValveTrimSize).filter(series_code=X, trim_inch.isnot(None)).count() > 0` 做守卫）。

**文件**：[main.py](file:///d:/KELK办公/信息化工作/207%20自研系统/KELKCalCv/backend/app/main.py) （line 27 后）

注册 `valve_types.seed_valve_filter_config(db)` 调用。

### 2. 后端：PARENT_FIELD_MAP 更新

**文件**：[valve_types.py](file:///d:/KELK办公/信息化工作/207%20自研系统/KELKCalCv/backend/app/api/valve_types.py) line 404-408

在 `PARENT_FIELD_MAP` 字典中增加一行：

```python
PARENT_FIELD_MAP = {
    'trim_type': 'trim_type',
    'pressure_rating': 'asme_class',
    'nominal_dn': 'dn_mm',
    'nominal_trim': 'trim_inch',   # 新增
}
```

`nominal_trim` 的 `value_field=trim_inch` 走通用级联分支（line 453-467），按 `(asme_class, dn_mm)` 父级组合分组查 `trim_inch`，生成 `options_by_parent`。

### 3. 后端：curves-by-selection API 增加 nominal_dn/nominal_trim 参数

**文件**：[valve_types.py](file:///d:/KELK办公/信息化工作/207%20自研系统/KELKCalCv/backend/app/api/valve_types.py)

- **line 510-520**：`get_curves_by_selection` 签名增加 `nominal_dn: float = 0` 和 `nominal_trim: str = ""`
- **line 523-535**：`get_curves_by_selection_slash` 同步增加（斜杠系列兼容）
- **line 538-546**：`_get_curves_by_selection_impl` 签名增加这两个参数
- **line 560 之后**（`cfg = _get_cfg(...)` 和 404 检查之后）：新增 plug_size 推导块：

```python
derived_plug_mm = None
TRIM_INCH_SERIES = ('GC120', 'GC210')
if series_code in TRIM_INCH_SERIES and nominal_dn and nominal_trim and pressure_rating:
    ts = db.query(ValveTrimSize).filter(
        ValveTrimSize.series_code == series_code,
        ValveTrimSize.asme_class == pressure_rating,
        ValveTrimSize.dn_mm == nominal_dn,
        ValveTrimSize.trim_inch == nominal_trim,
        ValveTrimSize.plug_mm.isnot(None),
    ).first()
    if ts:
        derived_plug_mm = ts.plug_mm
        plug_size = derived_plug_mm  # 覆盖 plug_size，下游逻辑统一使用
```

- **line 821-851**（返回字典）：增加 `"derived_plug_mm": derived_plug_mm`

覆盖 `plug_size` 变量后，下游 rated_cv 查找（line 654-705）和 stk_index 查找（line 760-801）自动使用正确值。非 GC 系列不进推导块，原 `plug_size` 参数直接透传。

### 4. 后端：default_selection 增加 nominal_dn/nominal_trim 默认值

**文件**：[valve_types.py](file:///d:/KELK办公/信息化工作/207%20自研系统/KELKCalCv/backend/app/api/valve_types.py) line 495-501

在 `default_plug` 计算后（line 345 附近），对 GC120/GC210 查首行匹配默认压力等级的 `dn_mm`+`trim_inch`：

```python
default_nominal_dn = None
default_nominal_trim = None
if series_code in ('GC120', 'GC210'):
    ts_def = db.query(ValveTrimSize).filter(
        ValveTrimSize.series_code == series_code,
        ValveTrimSize.asme_class == default_pres,
        ValveTrimSize.trim_inch.isnot(None),
    ).order_by(ValveTrimSize.dn_mm).first()
    if ts_def:
        default_nominal_dn = ts_def.dn_mm
        default_nominal_trim = ts_def.trim_inch
        default_plug = ts_def.plug_mm  # 保持初始加载一致
```

在 `default_selection` 字典中增加 `"nominal_dn": default_nominal_dn` 和 `"nominal_trim": default_nominal_trim`（非 GC 系列为 None，不影响现有行为）。

### 5. 前端：新增 selTrim ref + syncFilterValuesToOldVars 更新

**文件**：[ValveTypes.vue](file:///d:/KELK办公/信息化工作/207%20自研系统/KELKCalCv/frontend/src/views/ValveTypes.vue)

- **line 582 附近**（已有 `selDn` 声明）：新增 `const selTrim = ref('')` — 存放 nominal_trim 值
- **line 637-649**（`syncFilterValuesToOldVars`）：增加 `if (fv.nominal_trim !== undefined) selTrim.value = fv.nominal_trim`
- **line 833-844**（`keyToOld` 映射）：增加 `nominal_trim: 'nominal_trim'`；将 `nominal_dn: 'dn_mm'` 改为 `nominal_dn: 'nominal_dn'`（匹配 Section 4 新增的 default_selection 键名）
- **line 881**（`selectSeries` 末尾，`loadSelectedCurves()` 之前）：增加 `syncFilterValuesToOldVars()` 调用 — 确保首次加载时 `selDn`/`selTrim` 从 `filterValues` 同步

### 6. 前端：loadSelectedCurves 增加 nominal_dn/nominal_trim 参数

**文件**：[ValveTypes.vue](file:///d:/KELK办公/信息化工作/207%20自研系统/KELKCalCv/frontend/src/views/ValveTypes.vue) line 733-755

在 `params` 对象中增加：

```javascript
nominal_dn: selDn.value || 0,
nominal_trim: selTrim.value || '',
```

保留 `plug_size` 参数（GC120 时后端会用推导值覆盖；其他系列仍用 `plug_size`）。

### 7. 前端：显示推导出的 plug_mm

**文件**：[ValveTypes.vue](file:///d:/KELK办公/信息化工作/207%20自研系统/KELKCalCv/frontend/src/views/ValveTypes.vue) line 307-320（`cv-summary` 区域）

在 `Min Cv` 项后增加：

```html
<div class="cv-item" v-if="selectedCurves.derived_plug_mm != null">
  <span class="cv-label">Plug Size</span>
  <span class="cv-value">{{ fmtNum(selectedCurves.derived_plug_mm) }} mm</span>
</div>
```

仅当后端返回 `derived_plug_mm` 非空时显示（即 GC120 两个新筛选器都选定后）。

### 8. 前端：nominal_dn 选项标签用 formatDnLabel + 宽度调整

**文件**：[ValveTypes.vue](file:///d:/KELK办公/信息化工作/207%20自研系统/KELKCalCv/frontend/src/views/ValveTypes.vue)

- **line 121**（`:style` 宽度）：增加 `nominal_trim` 分支 → `'140px'`
- **line 124-128**（`el-option` 的 `:label`）：对 `nominal_dn` 使用 `formatDnLabel` 显示公称尺寸标注（in/mm/JIS/DN），`:value` 保持 `dn_mm` 原始值

```html
:label="fc.key === 'nominal_dn' ? formatDnLabel(formatOpt(opt, 'value')) : formatOpt(opt, 'label')"
```

`formatDnLabel` 函数（line 473-482）已存在，会根据 `dnLabelUnit` 从 `nominalSizeRefs` 查对照关系。切换单位时标签自动重渲染。`nominal_trim` 选项已是 inch 标注（如 "5/8"），直接用 `formatOpt` 即可。

## 不受影响的系列

- **GV120**：已有 `nominal_dn` 筛选器，无 `trim_inch` 数据，seed 守卫跳过，Table1/Table2 交集逻辑不变
- **BT/BC/BE**：无 `trim_inch` 数据，seed 守卫跳过，现有筛选器不变
- **GC210**：若有 `trim_inch` 数据则一并处理；若无 `asme_class` 数据则跳过

## 验证步骤

1. 重启后端，访问 `GET /api/v1/valve-types/GC120/curve-options`，确认 `filter_configs` 包含 `nominal_dn`（cascade, dep: pressure_rating）和 `nominal_trim`（cascade, dep: pressure_rating,nominal_dn），且 `plug_size` 不在其中（is_enabled=False）
2. 访问 `GET /api/v1/valve-types/GC120/curves-by-selection?pressure_rating=< 600#&nominal_dn=25&nominal_trim=5/8&trim_type=EQ%`，确认返回 `derived_plug_mm: 18` 且曲线数据正确
3. 前端选择 GC120 系列，确认筛选器显示：Trim Type → Pressure Rating → Nominal Valve Size → Nominal Trim Size（无 Plug Size 筛选器）
4. 选定 Nominal Valve Size 和 Nominal Trim Size 后，确认摘要卡片显示 "Plug Size 18 mm"
5. 切换单位（in/mm/JIS/DN），确认 Nominal Valve Size 选项标签随之变化
6. 切换到 GV120，确认筛选器和曲线加载行为不变
