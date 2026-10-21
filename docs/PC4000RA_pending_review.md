# PC4000RA 选型样本数据提取 — 待人工确认项

核对日期：2026-10-14

## 待确认项：1 处（已闭环）

### 1. 同缸径尺寸 E 列跨表取值不一致（原文档内部矛盾）

- **位置**：p10 双作用尺寸表 PC4250RA 行 E 列；p11 单作用尺寸表 PC4150RA 行 E 列（同为 Ø500 缸径）。
- **候选值**：PC4250RA `E = 350`；PC4150RA `E = Φ300`。同 Ø400 缸径（PC4240RA/PC4140RA）两表均为 350/Φ300 一致，仅 Ø500 二者不同。
- **截图路径**：
  - `C:\Users\zhaorong\AppData\Local\Temp\kelk_pipe\PC4000RA_crops\p10_rows.png`（双作用 p10 全行）
  - `C:\Users\zhaorong\AppData\Local\Temp\kelk_pipe\PC4000RA_crops\p11_rows.png`（单作用 p11 末三行）
  - 原始页：`...\PC4000RA_pages\page_10.png`、`page_11.png`
- **处置建议**：以 PDF 各自表原值如实保留（structured_data 已按 p10=E350、p11=EΦ300 记录）；是否属原文档排版/设计差异，请业务方确认。
- **人工复核意见（2026-10-14）**：统一取 350。**已执行**：`PC4000RA_structured_data.json` 中 `dimensions.spring_return` 表 PC4150RA 行 E 由 `Φ300` 改为 `350`（D 同步记为 `400`），与 PC4250RA 一致；`document_anomalies_preserved` 注记同步更新。**本样本待确认项已闭环。**

## 已按 PDF 裁决、无需人工确认（备查）

1. **docx 表7/表8/表9（p9/p10/p11 尺寸表）全空**：已按渲染图（p10 表放大 3 倍）逐格重提，数值见 `PC4000RA_structured_data.json`。
2. **docx 漏表：p6 表1-2（单作用输出力矩/容量/重量）**：docx 完全缺失，已按 p6 渲染图（放大 2.4 倍）重建 8 型号×2 行。
3. **p10 双作用续表缺 B 列**：渲染图确认原文档 p10 表仅 15 列（无 B），非 OCR 丢列，已按原样记录。

## 原文档自身瑕疵（非提取问题，保留原样并标注）

- 表1-1/1-2 英文标题 `STORKE`（应为 STROKE）。
- 表1-2 中文标题“输出力”与英文“OUTPUT TORQUE”/表1-1“输出力矩”不一致。
- 图1-1/1-2 图题标注 `PC3200LA / PC3100LA`（应为 PC4200RA/PC4100RA），图1-1 英文序号印作 `Fig. I-1`。
- p3 英文 `preu-matic cylinder` 拼写瑕疵。
