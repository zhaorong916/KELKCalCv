# KELKCalCv 调节阀 Cv 计算与噪音分析系统

## 一、系统概述

本系统为调节阀 Cv 计算及噪音计算分析平台，采用 B/S 架构，中文界面，左侧导航菜单布局。支持项目管理、以位号为索引的阀门管理、同一阀门多版本计算、单台阀门同时录入 5 组工艺参数并行计算。计算依据 **IEC 60534、GB/T 17213、ISA-75.01** 标准。

### 核心功能

| 功能模块  | 说明                                       |
| ----- | ---------------------------------------- |
| 项目管理  | 创建/编辑/删除项目，项目下管理局域内调节阀（位号）               |
| 位号管理  | 以位号（tag\_no）为索引，项目内唯一，记录阀门基本信息           |
| 版本管理  | 同一台阀门多次计算自动生成版本号（V1, V2...），支持设置当前生效版本   |
| 阀门配置  | 额定 Cv、FL、xT、FD、阀座口径、流量特性等参数              |
| 工艺工况  | 单台阀门最多 5 组工况（正常/最大/最小/开工/事故等）            |
| Cv 计算 | 液体（非阻塞/阻塞流）、气体（膨胀系数法）、两相流（叠加法/均相法）       |
| 噪音预测  | 气动噪音（IEC 60534-8-3）、水动力噪音（IEC 60534-8-4） |
| 介质库   | 20 种常见介质预置，水/水蒸汽按 IAPWS-IF97 自动判定相态      |
| 计算标准  | IEC 60534 / GB/T 17213 / ISA-75.01 可选    |

***

## 二、技术栈

| 层   | 技术                                                  |
| --- | --------------------------------------------------- |
| 前端  | Vue 3 + Element Plus + Vite + ECharts + Axios       |
| 后端  | Python 3.12 + FastAPI + SQLAlchemy 2.0 + Pydantic 2 |
| 计算  | NumPy / SciPy + IAPWS-IF97（iapws 库）                 |
| 数据库 | Microsoft SQL Server（pyodbc + ODBC Driver 17）       |

***

## 三、数据库配置

| 参数      | 值                             |
| ------- | ----------------------------- |
| 服务器     | 192.168.1.112                 |
| 端口      | 1433                          |
| 数据库名    | KELKCalCv                     |
| 账号      | Sa                            |
| 密码      | QraLBZngRU0PipBmIun4          |
| ODBC 驱动 | ODBC Driver 17 for SQL Server |

配置文件位于 `backend/app/core/config.py`（或通过 `backend/.env` 覆盖）。

### 数据库表结构

```
projects（项目）
  └─ valves（位号，项目内 tag_no 唯一）
       └─ calculations（计算版本，version_no 自增）
            ├─ valve_configs（阀门配置参数，1:1）
            └─ process_cases（工艺工况，最多5组 case_no 1..5）
                 └─ calc_results（计算结果，1:1）

fluids（介质库，20种预置介质）
users（用户，内置 admin/admin123）
```

***

## 四、部署与启动

### 4.1 环境要求

* Python 3.10+

* Node.js 18+

* ODBC Driver 17 for SQL Server

* SQL Server 数据库（已配置 192.168.1.112）

### 4.2 后端部署

```powershell
cd backend

# 1. 安装依赖
python -m pip install -r requirements.txt

# 2. 初始化数据库（自动建库、建表、初始化介质库、创建管理员）
python init_db.py

# 3. 启动后端服务
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

后端启动后：

* API 地址：<http://localhost:8000/api/v1>

* Swagger 文档：<http://localhost:8000/docs>

* 健康检查：<http://localhost:8000/api/v1/health>

### 4.3 前端部署

```powershell
cd frontend

# 1. 安装依赖
npm install

# 2. 启动开发服务器
npm run dev
```

前端启动后访问：<http://localhost:5173>

> 前端通过 Vite 代理将 `/api` 请求转发至后端 `http://127.0.0.1:8000`（见 `vite.config.js`）。

### 4.4 生产构建

```powershell
cd frontend
npm run build    # 输出到 dist/
```

构建产物可由 Nginx 托管，API 反向代理至后端 8000 端口。

***

## 五、API 接口

所有接口前缀：`/api/v1`

### 5.1 项目管理

| 方法     | 路径                   | 说明                    |
| ------ | -------------------- | --------------------- |
| GET    | `/projects?keyword=` | 项目列表（支持关键词搜索）         |
| POST   | `/projects`          | 创建项目                  |
| GET    | `/projects/{pid}`    | 项目详情                  |
| PUT    | `/projects/{pid}`    | 更新项目                  |
| DELETE | `/projects/{pid}`    | 删除项目（级联删除位号/版本/工况/结果） |

### 5.2 位号管理

| 方法     | 路径                                | 说明                   |
| ------ | --------------------------------- | -------------------- |
| GET    | `/projects/{pid}/valves?keyword=` | 位号列表                 |
| POST   | `/projects/{pid}/valves`          | 创建位号（项目内 tag\_no 唯一） |
| GET    | `/projects/{pid}/valves/{vid}`    | 位号详情                 |
| PUT    | `/projects/{pid}/valves/{vid}`    | 更新位号                 |
| DELETE | `/projects/{pid}/valves/{vid}`    | 删除位号                 |

### 5.3 计算版本

| 方法     | 路径                                             | 说明              |
| ------ | ---------------------------------------------- | --------------- |
| GET    | `/valves/{vid}/calculations`                   | 版本列表            |
| POST   | `/valves/{vid}/calculations`                   | 创建新版本（自动递增版本号）  |
| GET    | `/valves/{vid}/calculations/{cid}`             | 版本详情（含配置/工况/结果） |
| DELETE | `/valves/{vid}/calculations/{cid}`             | 删除版本            |
| PUT    | `/valves/{vid}/calculations/{cid}/set-current` | 设为当前版本          |

### 5.4 配置与工况

| 方法   | 路径                                        | 说明           |
| ---- | ----------------------------------------- | ------------ |
| PUT  | `/valves/{vid}/calculations/{cid}/config` | 保存阀门配置       |
| PUT  | `/valves/{vid}/calculations/{cid}/cases`  | 保存工艺工况（最多5组） |
| POST | `/valves/{vid}/calculations/{cid}/run`    | 执行计算（结果落库）   |
| POST | `/valves/{vid}/calculations/preview`      | 即时预览计算（不落库）  |

### 5.5 介质库

| 方法     | 路径                            | 说明                  |
| ------ | ----------------------------- | ------------------- |
| GET    | `/fluids?keyword=`            | 介质列表                |
| POST   | `/fluids`                     | 新增介质                |
| PUT    | `/fluids/{fid}`               | 更新介质                |
| DELETE | `/fluids/{fid}`               | 删除介质                |
| GET    | `/fluids/water/resolve?t=&p=` | 水的相态自动判定（温度℃/压力kPa） |

***

## 六、计算引擎说明

### 6.1 Cv 计算（IEC 60534-2-1 / GB/T 17213.2）

| 介质类型 | 计算方法                                           |
| ---- | ---------------------------------------------- |
| 液体   | 非阻塞流：Q = N1·Cv·√(ΔP/ρ)；阻塞流：ΔP ≤ FL²·(P1-FF·Pv) |
| 气体   | 膨胀系数法：Y = 1 - x/(3Fγ·xT)，x = ΔP/P1             |
| 两相流  | 叠加法（IEC 60534-2-1 附录）、均相法                      |

关键中间量：压差比 x、膨胀系数 Y、临界压差比 xT、压力恢复系数 FL、雷诺数 Re、管件几何系数 Fp。

### 6.2 噪音预测

| 类型    | 标准            | 方法                      |
| ----- | ------------- | ----------------------- |
| 气动噪音  | IEC 60534-8-3 | 基于声功率法，考虑阀门出口马赫数、管道传播损失 |
| 水动力噪音 | IEC 60534-8-4 | 基于闪蒸/空化判定，计算 A 计权声压级    |

### 6.3 水的物性（IAPWS-IF97）

水/水蒸汽介质根据工况温度和压力，按 IAPWS-IF97 标准自动判定相态：

* P > Psat(T) → 液态（liquid）

* P < Psat(T) → 过热蒸汽（gas）

* P ≈ Psat(T) → 饱和（saturated）

密度、粘度、比热比、声速等物性参数均由 IAPWS-IF97 精确计算。

***

## 七、验证结果

### 7.1 计算引擎验证（verify\_engine.py）

| 工况   | 介质   | 相态         | Cv     | 流态       | 噪音 dB(A) |
| ---- | ---- | ---------- | ------ | -------- | -------- |
| 水-正常 | 水    | liquid（自动） | 64.78  | 非阻塞(湍流)  | 78.2     |
| 过热蒸汽 | 水    | gas（自动）    | 31.86  | 亚临界(非阻塞) | 48.8     |
| 空气   | 空气   | gas        | 100.01 | 亚临界(非阻塞) | 65.9     |
| 气液两相 | 水+空气 | gas        | 59.62  | 亚临界-叠加   | -        |

### 7.2 API 端到端联调（verify\_api.py）

完整流程验证通过：健康检查 → 介质库 → 建项目 → 建位号 → 建版本 → 保存配置 → 保存5组工况 → 执行计算 → 结果落库 → 查询详情 → 清理。

5 组工况计算结果：

| 工况    | 介质 | 相态      | Cv     | 噪音 dB(A) |
| ----- | -- | ------- | ------ | -------- |
| 水-正常  | 水  | liquid  | 64.78  | 78.2     |
| 水-最大  | 水  | liquid  | 77.85  | 81.5     |
| 水蒸汽   | 水  | gas（自动） | 31.86  | 48.8     |
| 空气-正常 | 空气 | gas     | 100.01 | 65.9     |
| 空气-最小 | 空气 | gas     | 62.51  | 50.7     |

***

## 八、使用指南

### 8.1 典型操作流程

1. **新建项目**：进入「项目管理」→ 新建项目，填写项目编号、名称、客户
2. **添加位号**：进入项目详情 → 添加阀门位号（如 TV-1001），填写阀门信息
3. **创建版本**：进入计算页面 → 新建计算版本（自动 V1）
4. **配置阀门参数**：在「阀门配置」页签填写额定 Cv、FL、xT、FD 等
5. **录入工艺工况**：在「工艺工况」页签录入最多 5 组工况参数
6. **执行计算**：点击计算按钮，查看 Cv、流态、噪音结果
7. **版本管理**：修改参数后新建版本（V2），可对比历史版本

### 8.2 水的相态自动判定

选择介质为「水」时，系统根据录入的温度和阀前压力自动判定液态或蒸汽：

* 录入 25℃、680 kPa → 自动判定为液态

* 录入 200℃、1500 kPa → 自动判定为过热蒸汽

无需手动选择相态，也可通过 `fluid_state_override` 字段强制覆盖。

***

## 九、项目结构

```
KELKCalCv/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── core/
│   │   │   ├── config.py        # 配置（数据库/CORS/应用）
│   │   │   └── database.py      # SQLAlchemy 引擎与会话
│   │   ├── models/__init__.py   # 数据库模型
│   │   ├── schemas/__init__.py  # Pydantic 请求/响应模型
│   │   ├── api/
│   │   │   ├── projects.py      # 项目管理 API
│   │   │   ├── valves.py        # 位号管理 API
│   │   │   ├── calculations.py  # 计算版本与执行 API
│   │   │   └── fluids.py        # 介质库 API
│   │   └── calc/
│   │       ├── cv_core.py       # Cv 计算核心结构与工具
│   │       ├── cv_liquid.py     # 液体 Cv 计算
│   │       ├── cv_gas.py        # 气体 Cv 计算
│   │       ├── cv_twophase.py   # 两相流 Cv 计算
│   │       ├── noise.py         # 噪音预测
│   │       ├── properties.py    # 物性服务（IAPWS-IF97）
│   │       └── engine.py        # 计算引擎编排
│   ├── init_db.py               # 数据库初始化脚本
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── router/index.js      # 路由
│   │   ├── api/index.js         # API 客户端
│   │   ├── layouts/MainLayout.vue  # 主布局（左侧导航）
│   │   └── views/
│   │       ├── Dashboard.vue    # 仪表盘
│   │       ├── Projects.vue     # 项目管理
│   │       ├── ProjectDetail.vue # 项目详情（位号管理）
│   │       ├── Calculation.vue  # 计算页面（配置/工况/结果）
│   │       ├── Fluids.vue       # 介质库管理
│   │       └── About.vue        # 关于
│   ├── vite.config.js
│   └── package.json
├── verify_engine.py             # 计算引擎验证脚本
├── verify_calc.py               # Cv 计算验证脚本
└── verify_api.py                # API 端到端联调脚本
```

***

## 十、开发与实施流程约定

### 10.1 选型模块任务的强制参考基线

后续凡涉及「调节阀选型模块」的开发与实施任务，**必须先查阅并以以下两份产出物为权威基线**，不得自行另立方案或重复建表：

| 产出物 | 文件 | 关注重点 |
| --- | --- | --- |
| 调节阀选型模块实施方案规划 | `docs/选型模块优化方案.md`（方案/架构）、`docs/选型模块实施计划.md`（里程碑 P0–P6、依赖关系、工程基线） | **方案的变更**：架构、里程碑、表结构设计的调整 |
| 选型样本结构化数据整理 | `docs/*_structured_data.json`、`docs/*_样本基础数据分析.md`（如 `GC120_210_structured_data.json`、`GC320_structured_data.json`、`GC120_210_样本基础数据分析.md`、`GC320_样本基础数据分析.md`）及相关 `*_all_tables_raw.json` / `*_dimensions.json` | **结构化数据的建表**：字段口径、字段映射、表结构 |

### 10.2 执行约束

- **方案变更**：选型模块的架构、里程碑或表结构如有调整，须**先更新上述规划文档，再据此实施编码**；禁止"代码先行、文档滞后"。
- **结构化数据建表**：新增/修改数据表必须以「选型样本结构化数据整理」的字段口径与建表映射为准；建表须遵循 `.trae/skills/excel-to-mssql-import/SKILL.md` 的固化步骤（Step-A ~ Step-D），并同步 ORM 模型与 Pydantic Schema。
- **一致性**：任何与上述文档冲突的实现，须先澄清并同步更新文档，不得静默偏离。

***

## 十一、计算标准依据

| 标准            | 适用范围                      |
| ------------- | ------------------------- |
| IEC 60534-2-1 | 调节阀口径计算（液体/气体/两相流）        |
| IEC 60534-8-3 | 气动噪音预测                    |
| IEC 60534-8-4 | 水动力噪音预测                   |
| GB/T 17213.2  | 工业过程控制阀（等同 IEC 60534-2-1） |
| ISA-75.01     | 控制阀口径计算                   |
| IAPWS-IF97    | 水和水蒸汽热力学性质                |

