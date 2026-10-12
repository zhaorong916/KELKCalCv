"""调试: BT120/BT210 的 Laminar Sizing Factor 行位置 + GV120 实际 Table 1 结构"""
import openpyxl

path = r'd:\KELK办公\信息化工作\207 自研系统\KELKCalCv\参考文件\KELK CalcCv Valve & Trim Factors.xlsm'
wb = openpyxl.load_workbook(path, data_only=True, keep_vba=True)

for sn in ['BT120', 'GV120', 'GV110']:
    ws = wb[sn]
    print(f'\n=== {sn} ===')
    for r in range(1, 100):
        row_vals = []
        for c in range(1, 12):
            v = ws.cell(row=r, column=c).value
            if v is not None and str(v).strip():
                row_vals.append(f'[{c}]={str(v)[:40]}')
        if row_vals:
            print(f'R{r:02d}: ' + '  '.join(row_vals))

wb.close()
