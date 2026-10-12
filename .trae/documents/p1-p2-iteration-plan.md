# P1-P2 级迭代实现计划

## Context

计算引擎迭代文档 §12.1 中有 5 项 P1-P2 待迭代项。P0 级（Fr/RK-Z/Annex C）已于 2026-09-04 完成。本次实现全部 5 项 P1-P2 迭代，使计算引擎与 Excel 参考实现全面对齐。

## 实现顺序（按依赖关系排列）

| 序号 | 项                               | 文件                                        | 依赖                   |
| -- | ------------------------------- | ----------------------------------------- | -------------------- |
| 1  | P1-2 Ff Pc≤Pv 兜底                | cv\_liquid.py                             | 无                    |
| 2  | P1-1 IEC Eq.20/30/33 Fp/Flp/xTP | cv\_core.py, cv\_liquid.py, cv\_gas.py    | 无                    |
| 3  | P2-3 湿蒸汽 Singleton              | cv\_twophase.py, engine.py, properties.py | P1-1 的 fl\_effective |
| 4  | P2-1 噪音 5 级 Regime              | noise.py, engine.py                       | P1-1 的 Flp           |
| 5  | P2-2 噪音倍频程分析                    | noise.py                                  | P2-1 的中间变量           |

***

## 1. P1-2: Ff Pc≤Pv 兜底 (cv\_liquid.py)

**改动**：将 `cv_liquid.py` 第 64-70 行的 Ff 计算改为三分支（与 cv\_twophase.py L97-102 一致）：

```python
if pv <= 0:
    ff = 0.96
elif pc > 0 and pv < pc:
    ff = 0.96 - 0.28 * math.sqrt(pv / pc)
    ff = max(min(ff, 1.0), 0.0)
else:
    ff = 0.68   # Pv≥Pc (IEC Eq.12)
```

同步修复 noise.py L202 的 `predict_liquid_noise` 中相同问题。

***

## 2. P1-1: IEC Eq.20/30/33 严格 Fp/Flp/xTP (cv\_core.py)

### 新增常量

```python
N5_PRIME = 0.00241  # xTP 管件计算用系数 (IEC Eq.33)
```

### 新增辅助函数 `_iecfittings(vc) -> (K1, K2, KB1, KB2)`

- β = d/D

- K1 (进口): `0.5*(1-β²)²` if d\<D else `(1-(D/d)²)²/(D/d)^4`

- K2 (出口): 同 K1 结构

- KB1=KB2 = `1-β^4`

### 修改 `compute_fp()` — 替换 ζ1/ζ2 为 IEC K1/K2/KB1/KB2 (Eq.20)

```python
K1, K2, KB1, KB2 = _iecfittings(vc)
cd = cv / (d * d)
fp = 1.0 / math.sqrt(1.0 + (K1+K2+KB1-KB2) * cd**2 / N2)
```

### 修改 `fl_effective(vc, fp, cv_operating=None)` — 增加 Eq.30 计算

- 用户提供 flp → 直接用（不变）

- 缩径 + 有几何参数 → `Flp = FL/√(1 + FL²·(K1+KB1)·Cd²/N2)`

- 否则 → 返回裸 FL（不变）

### 修改 `xt_effective(vc, fp, cv_operating=None)` — 增加 Eq.33 计算

- 用户提供 xtp → 直接用（不变）

- 缩径 + 有几何参数 → `xTP = (xT/Fp²) / (1 + xT·(K1+KB1)·Cd²/N5_PRIME)`

- 否则 → 返回裸 xT（不变）

### 调用方更新

- `cv_liquid.py`：先按 rated\_cv 算 Fp/Flp → 得 cv\_required → 用 cv\_operating=cv\_required 重算 Flp → 重算 dp\_choked/Cv（单次迭代，与 Excel 一致）

- `cv_gas.py`：同理用 cv\_required 重算 xTP

- `cv_twophase.py`：无需改动（默认 cv\_operating=None 用 rated\_cv）

***

## 3. P2-3: 湿蒸汽 Singleton 模型 (cv\_twophase.py + engine.py + properties.py)

### cv\_twophase.py — 新增 `method='singleton'` 分支

```
ρ1fe = ρ_liquid / (1-Q)       # 液相等效密度
ρ1ge = ρ_gas * Y² / Q          # 气相等效密度
Cv = (1/(K_LIQ·Fp)) · √(W_total · (1/(ρ1fe·ΔPfe) + 1/(ρ1ge·ΔPge)))
```

- 有效压差 ΔPfe/ΔPge 与 Annex C 相同（含 Ff/FL/xT 阻塞判定）

- Q = 质量含气率 (0\<Q<1)

- 返回 flow\_regime = "湿蒸汽-Singleton\[液相阻塞/气相阻塞]" 或 "湿蒸汽-Singleton(亚临界)"

### properties.py — 新增 `water_saturation_phase_densities(t_c, p_kpa) -> (rho_l, rho_g)`

利用 IAPWS97 x=0 和 x=1 获取饱和液/汽相密度。

### engine.py — 路由增强

- 新增 `quality: float = 1.0` 参数到 `calculate_case()` 签名

- 检测湿蒸汽：`is_water and phase=='saturated' and 0<quality<1`

- 湿蒸汽路由到 `calculate_cv_twophase(method='singleton')`

  - mass\_flow\_gas = mass\_flow \* quality

  - mass\_flow\_liquid = mass\_flow \* (1 - quality)

  - density\_gas/liquid 从 `water_saturation_phase_densities()` 获取

- quality=1.0（默认）时行为不变，饱和蒸汽仍走气体路径

***

## 4. P2-1: 噪音 5 级 Regime 判定 (noise.py + engine.py)

### noise.py 改动

**NoiseResult 新增字段**：`regime_index`, `regime_label`, `jet_diameter_m`, `vc_mach`, `critical_mach`, `vc_sound_speed`, `aeta`, `alpha_recovery`, `pressure_ratios(dict)`

**`predict_gas_noise()`** **新增可选参数**：

- `flp: Optional[float] = None`

- `fd: float = 0.46`

- `aeta_db: Optional[float] = None` (声效率因子 10^Aeta)

- `enhanced: bool = False`

**路由逻辑**：`enhanced and flp and aeta_db` → 调用 `_predict_gas_noise_5regime()`；否则走现有简化路径（重命名为 `_predict_gas_noise_simplified()`）。

**`_predict_gas_noise_5regime()`** **五步法**：

1. 压力比与 Regime 判定 (Eq.1-7)：x/xC/xB/xCE/xvcc → Regime I\~V
2. 射流直径 Dj (Eq.9)
3. 缩脉条件 Mvc/cvc/Mj (Eq.32)
4. 声功率：按 Regime 分别计算 η×Wm
5. 声压级：Lpi(Eq.18/31) + Lg(Eq.16) + TL + Lpe1m

### engine.py 调用增强

```python
nr = predict_gas_noise(
    ...,
    flp=res.cv.fl_eff if res.cv.fl_eff else valve_coeffs.fl,
    fd=valve_coeffs.fd,
    aeta_db=fluid.get("aeta_db"),
    enhanced=True,  # 有 aeta_db 时自动走 5-regime，否则降级
)
```

### 降级策略

aeta\_db 为 None 时，`enhanced=True` 仍自动降级到简化路径。后续可从 valve\_types 表补充 aeta\_db 字段。

***

## 5. P2-2: 噪音倍频程分析 (noise.py)

### 新增 `predict_gas_noise_octave()` 函数

- 14 个 1/3 倍频程频带（500 Hz \~ 10 kHz，IEC 61672 A 计权曲线）

- 每频带计算：TL(f) 含环频率/内部重合/外部重合/阻尼因子(Eq.20b-23)

- 频带声压级 → A 计权 → 能量叠加求总 dBA

- 返回 dict：`{"bands": [...], "total_dba": float, "intermediate": {...}}`

### 集成方式

`predict_gas_noise()` 新增 `octave: bool = False` 参数，为 True 时调用 `predict_gas_noise_octave()` 并存入 `detail["octave_bands"]`。

***

## 6. 文档更新 (docs/计算引擎迭代.html)

- §6: Fp/Flp/xTP 差异标记 → "完全一致 (2026-09-04)"

- §8: 噪音 Regime/频谱差异标记 → "已实现 (2026-09-04)"

- §12.1: 5 项 P1-P2 状态 → "已完成 2026-09-04"

- §12.2: 新增 5 条变更记录

- §12.3: 新增 5 条已完成项

***

## 验证方式

| 项    | 验证方法                                          |
| ---- | --------------------------------------------- |
| P1-2 | Pv≥Pc 近临界工况 → Ff=0.68（非负值）                    |
| P1-1 | 缩径阀 β=0.6 → Fp/Flp/xTP 与 Excel 参考值对比          |
| P2-3 | 湿蒸汽 Q=0.5 → Singleton Cv 与 Annex C 对比         |
| P2-1 | 空气阻塞工况 → Regime I\~V 分类与 Excel 一致，LpA 误差 ≤2dB |
| P2-2 | 倍频程总 dBA 与单频带结果差异 ≤0.5dB                      |

后端启动后通过 `/docs` Swagger 或 Python REPL 跑验证用例。

## 关键文件清单

- `backend/app/calc/cv_core.py` — P1-1 核心

- `backend/app/calc/cv_liquid.py` — P1-2 + P1-1 调用方

- `backend/app/calc/cv_gas.py` — P1-1 调用方

- `backend/app/calc/cv_twophase.py` — P2-3 Singleton

- `backend/app/calc/noise.py` — P2-1 五级 Regime + P2-2 倍频程

- `backend/app/calc/engine.py` — P2-3 路由 + P2-1 调用增强

- `backend/app/calc/properties.py` — P2-3 饱和相密度

- `docs/计算引擎迭代.html` — 文档更新

