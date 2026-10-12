import pyodbc
conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=192.168.1.112;DATABASE=KELKCalCv;UID=Sa;PWD=QraLBZngRU0PipBmIun4')
cur = conn.cursor()

# 查看实际列
cur.execute("SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'valve_trim_sizes' ORDER BY ORDINAL_POSITION")
print('=== 实际列 ===')
for r in cur.fetchall():
    print(f'  {r[0]:20s} {r[1]:15s} max={r[2]}')

# 统计行数
cur.execute('SELECT series_code, COUNT(*) FROM valve_trim_sizes GROUP BY series_code ORDER BY series_code')
print('\n=== 各系列行数 ===')
for r in cur.fetchall():
    print(f'  {r[0]:20s} {r[1]}')

# 查看 GC120 前 30 行
cur.execute("SELECT TOP 30 * FROM valve_trim_sizes WHERE series_code='GC120' ORDER BY asme_class, dn_mm, trim_code, characteristic")
cols = [d[0] for d in cur.description]
print('\n=== GC120 示例数据 ===')
print(' | '.join(cols))
for r in cur.fetchall():
    print(' | '.join(str(v) for v in r))

# 查看 characteristic 分布
cur.execute("SELECT series_code, characteristic, COUNT(*) FROM valve_trim_sizes GROUP BY series_code, characteristic ORDER BY series_code, characteristic")
print('\n=== characteristic 分布 ===')
for r in cur.fetchall():
    print(f'  {r[0]:10s} char={r[1]:15s} {r[2]}')

conn.close()
