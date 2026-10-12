"""调试: 打印每个 Sheet 的 Table 1 区域原始单元格值"""
import openpyxl

path = r'd:\KELK办公\信息化工作\207 自研系统\KELKCalCv\参考文件\KELK CalcCv Valve & Trim Factors.xlsm'
wb = openpyxl.load_workbook(path, data_only=True, keep_vba=True)

for sn in ['GC120', 'GC210', 'BT120', 'BT210', 'BC110', 'BE120', 'GV120']:
    if sn not in wb.sheetnames:
        continue
    ws = wb[sn]
    print(f'\n{"="*60}')
    print(f'=== {sn} ===')
    # 扫描所有行，找 Table 1 相关区域
    for r in range(1, 80):
        row_vals = []
        for c in range(1, 12):
            v = ws.cell(row=r, column=c).value
            if v is not None and str(v).strip():
                row_vals.append(f'[{c}]={str(v)[:30]}')
        if row_vals:
            print(f'R{r:02d}: ' + '  '.join(row_vals))
    print(f'  (max_row={ws.max_row}, max_col={ws.max_column})')

wb.close()
