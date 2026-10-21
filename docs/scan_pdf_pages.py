# -*- coding: utf-8 -*-
"""Scan all PDF pages with pdfplumber: text length, table count, table preview.
Output a JSON report for deciding which pages to extract via text vs. image.
"""
import json
import os
import sys
import pdfplumber

PDF = r"c:\Users\zhaorong\.trae-cn\attachments\5eb67545-4885-4a50-bc23-d7461d41d634_19adb4e7-3072-4985-b7f3-f32ead53553a_GC320(压缩).pdf"
OUT = r"d:\KELK办公\信息化工作\207 自研系统\KELKCalCv\docs\GC320_pdf_page_scan.json"


def first_row_preview(tbl):
    """Return first row cells joined by ' | '."""
    if not tbl:
        return ""
    row = tbl[0]
    return " | ".join((c or "").strip() if c else "" for c in row)[:200]


def main():
    report = []
    with pdfplumber.open(PDF) as pdf:
        n_pages = len(pdf.pages)
        print(f"PDF total pages: {n_pages}")
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            text_len = len(text.strip())
            tables = page.find_tables() or []
            tbl_infos = []
            for t in tables:
                try:
                    extracted = t.extract()
                except Exception as e:
                    extracted = None
                n_rows = len(extracted) if extracted else 0
                n_cols = len(extracted[0]) if (extracted and extracted[0]) else 0
                tbl_infos.append({
                    "n_rows": n_rows,
                    "n_cols": n_cols,
                    "first_row": first_row_preview(extracted),
                })
            report.append({
                "page_index_0": i,
                "page_index_1": i + 1,
                "text_len": text_len,
                "table_count": len(tables),
                "tables": tbl_infos,
                "text_preview": text[:300].replace("\n", " | ") if text_len else "",
            })
            print(f"Page {i+1}: text_len={text_len}, tables={len(tables)}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report saved: {OUT}")


if __name__ == "__main__":
    main()
