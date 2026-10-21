# KELK 调节阀选型模块开发日志

> 基于 [选型模块优化方案 v2](选型模块优化方案.md) 和 [选型模块实施计划 v2](选型模块实施计划.md)

---

## 里程碑总览

| 阶段 | 名称 | 状态 | 开始日期 | 完成日期 |
|---|---|---|---|---|
| **P0** | 基础设施 | ✅ 已完成 | 2026-10-15 | 2026-10-15 |
| **P1** | 数据入库与校验 | 🟡 进行中 | 2026-10-15 | — |
| **P2** | 规则库 v1 + 匹配引擎 | ⚪ 未开始 | — | — |
| **P3** | API + 前端 MVP | ⚪ 未开始 | — | — |
| **P4** | 选型→精细计算贯通 | ⚪ 未开始 | — | — |
| **P5** | 规则管理 UI | ⚪ 未开始 | — | — |
| **P6** | 执行机构选型 | ⚪ 未开始 | — | — |

---

## P0 基础设施

### P0.1 新增 4 张表的 ORM 模型

**状态**: 🟡 进行中  
**涉及文件**: `backend/app/models/__init__.py`  
**新增模型**:
- `SelectionRule` — 选型规则库
- `BodyPtRating` — 阀体材质温压限制
- `AllowablePressureDrop` — 最大允许压差
- `SelectionRecord` — 选型历史记录

**验收标准**: `python -c "from app.models import SelectionRule, BodyPtRating, AllowablePressureDrop, SelectionRecord"` 无报错

### P0.2 新增 Pydantic Schema

**状态**: ⚪ 未开始  
**涉及文件**: `backend/app/schemas/__init__.py`

**新增 Schema**:
- `SelectionRuleBase/Create/Out`
- `SelectionInput`
- `CandidateOut`
- `SelectionResultOut`
- `SelectionRecordCreate/Out`

### P0.3 valve_cv_stk 增列脚本

**状态**: ⚪ 未开始  
**涉及文件**: 新建 `backend/add_cv_min_column.py`

**内容**: 幂等脚本，为 valve_cv_stk 添加 `cv_min FLOAT NULL` 列

### P0.4 启动自检

**状态**: ⚪ 未开始  
**验收**: 4 张新表自动创建且不影响既有表

---

## 变更记录

| 日期 | 变更内容 | 提交 |
|---|---|---|
| 2026-10-15 | 创建开发日志，开始 P0 基础设施 | — |
