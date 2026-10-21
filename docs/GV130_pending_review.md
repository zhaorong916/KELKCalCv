# GV130 待人工确认项

- 核对日期：2026-10-14
- 依据：`docs/GV130_pdf_docx_compare.md`、`docs/GV130_structured_data.json`

## 结论

**全部已确认，无待确认项。**

## 说明

1. PDF 20 页全部核对完成：文字层页（p1/p2/p19/p20）由 `pdfplumber` 直接提取；文字转曲页（p3~p18）由渲染 PNG 图像识别。高密度表（表3 额定Cv、表4-1/4-2 允许压差、表5 重量、p13~p18 六张尺寸表）区域均在临时目录裁剪放大 2.0 倍复核，字体清晰、数值可辨。
2. docx 26 表与 PDF 逐格比对，**未发现任何数值差异**；仅存的文字差异为 OCR 错字（见 `GV130_pdf_docx_compare.md` 第三节「OCR 错字清单」），不影响数值。
3. docx 结构缺漏 3 处均已从 PDF 完整读出并补入结构化数据：
   - 表1-1 结构清单 PARTS LIST（23 项，p6）；
   - 表2 顶部注释 ①~⑤ 与材质处理图例（R.TFE/PH/SS/SF，p7）；
   - 306SLA-R 尺寸表（p16，2 行，数值与 306SLA-D 相同）。
4. 原文档自身问题 2 处保留原样并在报告中标注，不属待确认范畴：
   - p4 软阀座泄漏等级中英文矛盾（英文 Class IV / 中文 Class VI），以中文 **Class VI** 为准；
   - 附表三 中国标准牌号 `ZG0Cr18nI9` 系原文档错别字（应为 ZG0Cr18Ni9），按 PDF 原样保留。
5. 图2/图3/图4/图5/图6 及图1-1/1-2 为图形表达，样本中本无表格数值，不需提取。

如后续对上述裁决有异议，可直接复查渲染图 `C:\Users\zhaorong\AppData\Local\Temp\kelk_pipe\GV130_pages\page_13.png`~`page_18.png`（尺寸表）、`page_09.png`（表3）、`page_10.png`（表4）、`page_06.png`（表1-1）。
