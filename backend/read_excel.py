import openpyxl
import os

path = r'd:\KELK办公\信息化工作\207 自研系统\KELKCalCv\参考文件\KELK CalcCv Valve & Trim Factors.xlsm'
wb = openpyxl.load_workbook(path, data_only=True, keep_vba=True)

print('=== Sheet 列表 ===')
for sn in wb.sheetnames:
    print(f'  {sn}')

# 看 GC120 sheet 的 Table 1 区域
ws = wb['GC120']
print('\n=== GC120 Sheet 前 60 行 x 10 列 (A-J) ===')
for r in range(1, 60):
    row_vals = []
    for c in range(1, 11):
        v = ws.cell(row=r, column=c).value
        row_vals.append(str(v) if v is not None else '')
    if any(row_vals):
        print(f'R{r:02d}: ' + ' | '.join(row_vals))

wb.close()
