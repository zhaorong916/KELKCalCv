# 阀门型号参数查询与校核页面 实施计划

## Context

参考文件 `参考文件\KELK CalcCv Valve & Trim Factors.xlsm` 是 KELK 阀门选型与系数校核的权威数据源，每个型号一个 Sheet（GC120/BT210…）展示 Trim Options + Table 1 Rated Capacities + 多项式系数曲线。当前系统数据库已导入 40 个阀门系列（valve\_types）、219 条系数曲线（valve\_factor\_curves）和 4 个系列的 trim 数据（valve\_trim\_sizes），但前端没有任何页面可视化这些数据。

本次新增"各型号阀门参数查询和校核"页面，目标：

1. 按 Excel 样式展示每个型号的扩展参数、默认系数、多项式曲线、额定容量表
2. 提供多项式曲线校核功能：输入开度 %，实时求值 Eq%/FL/Kc/Fd 并对比 value\_min/max 钳制范围

## 数据现状（已确认）

| 表                     | 行数  | 说明                                                                                                   |
| --------------------- | --- | ---------------------------------------------------------------------------------------------------- |
| valve\_types          | 40  | 全系列，扩展字段齐全（factor\_group/eq\_index/fl\_default/xt\_default/fd\_default/kc\_default/trim\_option\_\*） |
| valve\_factor\_curves | 219 | eqcv=198 / fl=7 / kc=7 / fd=7，按 (factor\_type, eq\_index) 唯一                                         |
| valve\_trim\_sizes    | 298 | 仅 4 系列：GC120/GC210/BT120/BT210；`opening_deg` 列实际不存在（schema 漂移），开度写入 remark                           |

⚠️ 已知约束：

- valve\_trim\_sizes 表缺少 `opening_deg` 列，ORM 自动 SELECT 会报错 → 新端点用显式列查询

- 36 个系列无 trim 数据 → 页面显示"暂未导入 Trim/Cv 数据"占位

- 校核功能聚焦多项式曲线（数据干净），不做 Cv 额定值校核

## 实施步骤

### 1. 后端：扩展 Schema + 新增端点

**文件** **`backend/app/schemas/__init__.py`** **L367-377** — 扩展 `ValveTypeOut`，补 9 个扩展字段：

```python
class ValveTypeOut(BaseModel):
    ...
    factor_group: Optional[str] = None
    eq_index: Optional[int] = None
    fl_default: Optional[float] = None
    xt_default: Optional[float] = None
    fd_default: Optional[float] = None
    kc_default: Optional[float] = None
    trim_option_pressure: Optional[str] = None
    trim_option_opening: Optional[str] = None
    trim_option_types: Optional[str] = None
```

**文件** **`backend/app/api/valve_types.py`** — 新增 3 个端点（沿用现有 `router` 前缀 `/valve-types`）：

| 端点                                 | 返回                          | 说明                                                  |
| ---------------------------------- | --------------------------- | --------------------------------------------------- |
| `GET /{series_code}`               | `ValveTypeOut`              | 单系列详情（含扩展字段）                                        |
| `GET /{series_code}/factor-curves` | `list[ValveFactorCurveOut]` | 查 valve\_types.eq\_index → 返回 eqcv/fl/kc/fd 共 4 条曲线 |
| `GET /{series_code}/trim-sizes`    | `list[dict]`                | 用 `with_entities()` 显式列出存在的列，**避开 opening\_deg**    |

trim-sizes 端点示例：

```python
cols = [c for c in ValveTrimSize.__table__.columns if c.name != 'opening_deg']
rows = db.query(*cols).filter(ValveTrimSize.series_code == sc).all()
return [dict(zip([c.name for c in cols], r)) for r in rows]
```

factor-curves 端点：

```python
vt = db.query(ValveType).filter(ValveType.series_code == sc).first()
if not vt: return []
return db.query(ValveFactorCurve).filter(ValveFactorCurve.eq_index == vt.eq_index).all()
```

### 2. 前端：API + 路由 + 导航

**文件** **`frontend/src/api/index.js`** — 扩展 `valveTypesApi`：

```js
export const valveTypesApi = {
  list: () => http.get('/valve-types'),
  detail: (sc) => http.get(`/valve-types/${sc}`),
  factorCurves: (sc) => http.get(`/valve-types/${sc}/factor-curves`),
  trimSizes: (sc) => http.get(`/valve-types/${sc}/trim-sizes`),
}
```

**文件** **`frontend/src/router/index.js`** — 加路由：

```js
{ path: 'valve-types', name: 'valve-types', component: () => import('@/views/ValveTypes.vue') }
```

**文件** **`frontend/src/layouts/MainLayout.vue`** — quick-links 加"阀门型号"入口（在介质库与关于之间）：

```html
<div class="ql-item" :class="{active: route.path.startsWith('/valve-types')}" @click="$router.push('/valve-types')">
  <el-icon><Setting /></el-icon><span>阀门型号</span>
</div>
```

crumbs 加分支：`else if (route.name === 'valve-types') c.push({ text: '阀门型号' })`

### 3. 前端：ValveTypes.vue 主页面（参照 Excel 样式）

**文件** **`frontend/src/views/ValveTypes.vue`** — 两栏布局，右栏镜像 Excel Sheet 布局：

```
┌─ 左栏 (240px) ────┬─ 右栏 (flex:1) ──────────────────────────┐
│ 搜索框            │ [深色标题条] GC120, 套筒导向型... [globe]│
│ ▸ 调节阀 (18)     │                                          │
│   • GC120 套筒... │ ┌ Trim Options 卡片 ─────────────────┐  │
│   • GC210 ...     │ │ Pressure Rating | Opening | Trim...│  │
│   ...             │ └────────────────────────────────────┘  │
│ ▸ 球阀 (10)       │ ┌ 默认系数 卡片 (4 个 metric 砖)──────┐  │
│ ▸ 蝶阀 (8)        │ │ factor_group | eq_index | FL | xT...│  │
│ ▸ 闸阀 (2)        │ └────────────────────────────────────┘  │
│                   │ ┌ 系数曲线 卡片 [Tab: Eq%|FL|Kc|Fd] ─┐  │
│                   │ │ Index|Min|Max|A6..A0/P4..P0 表格   │  │
│                   │ │ SVG 曲线预览 (0-100% 开度)          │  │
│                   │ └────────────────────────────────────┘  │
│                   │ ┌ 额定容量表 卡片 (Excel 样式) ──────┐  │
│                   │ │ ASME# | DN | Trim | Cv...          │  │
│                   │ │ (Cv 值红色加粗，压力等级合并显示)  │  │
│                   │ └────────────────────────────────────┘  │
│                   │ ┌ 校核 卡片 ─────────────────────────┐  │
│                   │ │ 开度%: [滑块 0-100] [输入框]        │  │
│                   │ │ Eq% = 0.45  FL = 0.92  Kc = 0.68...│  │
│                   │ │ ✓在范围内 / ✗超出钳制(红色)        │  │
│                   │ └────────────────────────────────────┘  │
└───────────────────┴──────────────────────────────────────────┘
```

**Excel 样式还原要点**：

- 标题条：深色背景（#2c3e50）+ 白字 + Arial 12pt 加粗

- 表头行：浅灰背景（#f0f2f5）+ 加粗

- Cv 值：红色（#e17055）+ 加粗，对齐右

- 压力等级单元格：垂直合并外观（用 rowspan 或同色块）

- 表格字体：Arial / Consolas，10pt

- 列宽紧凑（参照 Excel \~8.8 字符宽）

**多项式求值（前端 JS 实现 Horner 法）**：

```js
function evalPoly(coeffs, x) {
  // coeffs: [c_n, c_n-1, ..., c_1, c_0] (高次到低次)
  // Eq% 用 A6..A0 (6次)，FL/Kc/Fd 用 P4..P0 (4次)
  return coeffs.reduce((acc, c) => acc * x + c, 0)
}
// x = opening_pct / 100  (0..1)
```

**校核逻辑**：

- 输入开度 x%（0-100）→ x = x/100

- 对 4 条曲线分别求值：Eq% = Σ A\_i·x^i，FL/Kc/Fd = Σ P\_i·x^i

- 对 FL/Kc/Fd：与 value\_min/value\_max 对比，若超出则显示钳制值并标红

- 实时随滑块更新（@input 事件，无防抖）

**Rated Capacities 表渲染策略**：

- 无数据：`<el-empty description="该系列暂未导入 Trim/Cv 数据" />`

- 有数据（GC120 套筒型）：按 asme\_class 分组，trim\_code 作为子列；Cv 值红色

- 有数据（BT210 蝶阀）：按 asme\_class + DN 分组，remark 解析开度（"60 deg"/"90 deg"）作为列头

- 用 `rowspan` 合并压力等级/通径单元格，还原 Excel 视觉

### 4. 关键文件清单

| 文件                                         | 改动                                         |
| ------------------------------------------ | ------------------------------------------ |
| `backend/app/schemas/__init__.py` L367-377 | 扩展 ValveTypeOut（+9 字段）                     |
| `backend/app/api/valve_types.py`           | +3 端点（detail / factor-curves / trim-sizes） |
| `frontend/src/api/index.js`                | valveTypesApi +3 方法                        |
| `frontend/src/router/index.js`             | +1 路由                                      |
| `frontend/src/layouts/MainLayout.vue`      | +1 导航入口 + crumbs 分支                        |
| `frontend/src/views/ValveTypes.vue`        | 新建（核心页面）                                   |

## 验证方式

1. 启动后端：`cd backend; python -m uvicorn app.main:app --reload`
2. 启动前端：`cd frontend; npm run dev`
3. 浏览器访问 `http://localhost:5173/valve-types`
4. 测试矩阵：

   - 选 GC120（有 trim 数据 + eq\_index=1）：右侧应显示 Trim Options / 默认系数 / 4 条曲线 / 101 行 trim 表 / 校核

   - 选 BT210（蝶阀，trim 数据格式不同）：trim 表按开度列呈现

   - 选 GV110（无 trim 数据）：额定容量区显示"暂无"占位，但默认系数 + 曲线正常

   - 校核：拖动开度滑块 0→100%，Eq%/FL/Kc/Fd 值实时变化；FL>value\_max 时标红

   - curl `http://localhost:8000/api/v1/valve-types/GC120/factor-curves` 返回 4 条曲线

   - curl `http://localhost:8000/api/v1/valve-types/GC120/trim-sizes` 不报 opening\_deg 错误

