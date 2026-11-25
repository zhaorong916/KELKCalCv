"""对比旧/新两版重算结果，输出变好/持平/变差计数与逐条明细。

用法: python compare_results.py <old.json> <new.json> [detail.csv]
判定阈值: Cv 相对偏差 0.5%；开度绝对偏差 0.5 个百分点。
"""
import sys, json, csv, statistics

OLD, NEW = sys.argv[1], sys.argv[2]
DETAIL = sys.argv[3] if len(sys.argv) > 3 else 'regression_detail.csv'
old = json.load(open(OLD, encoding='utf-8'))
new = json.load(open(NEW, encoding='utf-8'))
om = {x['case_id']: x for x in old}


def relerr(v, s):
    return abs(v - s) / s if (v and s) else None


def judge(en, eo, tol):
    if en is None or eo is None:
        return None
    return '变好' if en < eo - tol else ('变差' if en > eo + tol else '持平')


cnt_cv = {'变好': 0, '持平': 0, '变差': 0, '无样本': 0}
cnt_op = {'变好': 0, '持平': 0, '变差': 0, '无样本': 0}
rows, eo_cv, en_cv, eo_op, en_op = [], [], [], [], []
for n in new:
    o = om.get(n['case_id'], {})
    sc, so = n.get('sample_cv'), n.get('sample_open')
    ecvo, ecvn = relerr(o.get('cv'), sc), relerr(n.get('cv'), sc)
    jc = judge(ecvn, ecvo, 0.005)
    cnt_cv[jc or '无样本'] += 1
    if jc:
        eo_cv.append(ecvo)
        en_cv.append(ecvn)
    eoo = abs(o['open'] - so) if (o.get('open') is not None and so) else None
    eon = abs(n['open'] - so) if (n.get('open') is not None and so) else None
    jo = judge(eon, eoo, 0.5)
    cnt_op[jo or '无样本'] += 1
    if jo:
        eo_op.append(eoo)
        en_op.append(eon)
    rp = None
    if n.get('cv') and n.get('cv_norp'):
        rp = (n['cv'] - n['cv_norp']) / n['cv_norp'] * 100
    rows.append({
        'case_id': n['case_id'], 'valve_id': n['valve_id'], 'slot': n['slot'],
        'model': n['model'], 'media': n['media'], 'dn': n['dn'], 'pipe_id': n['pipe_id'],
        'curve_src': n.get('curve_src'), 'stroke_mode': n.get('stroke_mode'),
        'sample_cv': sc, 'cv_old': o.get('cv'), 'cv_new': n.get('cv'),
        'cv_rel_old': ecvo, 'cv_rel_new': ecvn, 'judge_cv': jc,
        'sample_open': so, 'open_old': o.get('open'), 'open_new': n.get('open'),
        'open_err_old': eoo, 'open_err_new': eon, 'judge_open': jo,
        'full_dp': n.get('full_dp'), 'cv_norp': n.get('cv_norp'), 'reduced_port_pct': rp,
        'fp': n.get('fp'), 'status_new': n.get('status'),
    })
with open(DETAIL, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print('cases', len(rows))
print('Cv  :', cnt_cv, '中位相对偏差 old/new %%: %.2f / %.2f' % (
    statistics.median(eo_cv) * 100 if eo_cv else 0, statistics.median(en_cv) * 100 if en_cv else 0))
print('开度:', cnt_op, '中位绝对误差 old/new pt: %.2f / %.2f' % (
    statistics.median(eo_op) if eo_op else 0, statistics.median(en_op) if en_op else 0))
rp = [r for r in rows if r['reduced_port_pct'] is not None and abs(r['reduced_port_pct']) > 0.01]
print('缩径影响>0.01%%:', len(rp), '最大 %.3f%%' % (max(abs(r['reduced_port_pct']) for r in rp) if rp else 0))
fd = [r for r in rows if r['full_dp']]
print('全压差参考Cv:', len(fd), '与设计Cv不同的条数:',
      sum(1 for r in fd if r['cv_new'] and abs(r['full_dp'] - r['cv_new']) > 0.01))
