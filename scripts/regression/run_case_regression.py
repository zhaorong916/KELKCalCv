"""按产品计算链路重算脱敏样本，用于 1df041a(旧) 与 b74aea0(新) 回归对比。

用法:
  python run_case_regression.py <backend_dir> <out.json> <old|new> [csv] [limit]

链路: CSV 原始值+原始单位 -> app.calc.units.convert_process_case -> app.calc.engine.calculate_case
开度: old = Cv/Cv_rated 线性（旧版引擎 opening_pct）
      new = app.calc.opening.compute_opening 特性曲线反算（曲线系数取自 DB）
介质: media -> 基础物性（空气/氮气/污氮气/氧气 为气体，其余按液体）；密度用样本值（KG/NM3 按 P1/T1 修正）
系列曲线: 严格按 series_code 取 valve_series_curve_config；无配置时按产品前端 404 分支回落 linear。
          注意：BT310D/GV120D/GC210D/GC120D 在库中无曲线配置，需另行补数据或别名。
"""
import sys, os, json, csv
sys.path.insert(0, sys.argv[1])
from app.core.database import SessionLocal
from app.calc.units import convert_process_case
from app.calc.cv_core import ValveCoeffs, FactorCurves, FactorCurve
from app.calc.engine import calculate_case
from app.models import ValveSeriesCurveConfig, ValveFactorCurve

BACKEND, OUT, VERSION = sys.argv[1], sys.argv[2], sys.argv[3]
CSV = sys.argv[4] if len(sys.argv) > 4 else os.path.join(os.path.dirname(__file__), 'regression_cases_sample.csv')
LIMIT = int(sys.argv[5]) if len(sys.argv) > 5 else 10 ** 6
if VERSION == 'new':
    from app.calc.opening import compute_opening

FLUID = {
    '空气':   {'mw': 28.97, 'gamma': 1.40},
    '氮气':   {'mw': 28.01, 'gamma': 1.40},
    '污氮气': {'mw': 28.16, 'gamma': 1.40},
    '氧气':   {'mw': 32.00, 'gamma': 1.395},
}
PMAP = {'MPA(A)': 'MPaA', 'MPA(G)': 'MPaG', 'BAR(A)': 'barA', 'BAR(G)': 'barG',
        'KPA(A)': 'kPaA', 'KPA(G)': 'kPaG', 'KPA': 'kPa', 'MPA': 'MPa'}


def fnum(v):
    try:
        return float(v)
    except Exception:
        return None


def curve_dict(row):
    return {f'a{i}': getattr(row, f'a{i}') for i in range(7)} if row else None


def factor_curve(rows, ftype, idx):
    r = rows.get((ftype, int(idx))) if idx is not None else None
    if not r:
        return None
    return FactorCurve(p0=r.p0 or 0, p1=r.p1 or 0, p2=r.p2 or 0, p3=r.p3 or 0, p4=r.p4 or 0,
                       value_min=r.value_min, value_max=r.value_max)


db = SessionLocal()
fc_rows = {(r.factor_type, r.eq_index): r for r in db.query(ValveFactorCurve).all()}
cfg_rows = {r.series_code: r for r in db.query(ValveSeriesCurveConfig).all()}
meta_cache = {}


def series_meta(code):
    if code in meta_cache:
        return meta_cache[code]
    cfg = cfg_rows.get(code)
    meta = {'curve_src': code if cfg else None, 'stroke_mode': 'linear', 'eqcv': None,
            'fstk': None, 'curves': None}
    if cfg:
        meta['stroke_mode'] = cfg.stroke_mode
        meta['fstk'] = cfg.stroke_fstk
        if cfg.stroke_mode == 'eq_index' and cfg.stroke_eq_index:
            meta['eqcv'] = curve_dict(fc_rows.get(('eqcv', int(cfg.stroke_eq_index))))
        fl = factor_curve(fc_rows, 'fl', cfg.fl_eq_index)
        kc = factor_curve(fc_rows, 'kc', cfg.kc_eq_index)
        fd = factor_curve(fc_rows, 'fd', cfg.fd_eq_index) if cfg.fd_mode == 'table' else None
        if fl or kc or fd:
            meta['curves'] = FactorCurves(fl=fl, kc=kc, fd=fd)
    meta_cache[code] = meta
    return meta


out = []
with open(CSV, encoding='utf-8-sig') as f:
    cases = list(csv.DictReader(f))
for c in cases:
    if len(out) >= LIMIT:
        break
    model = c['model']
    media = c['media']
    meta = series_meta(model)
    is_liquid = media not in FLUID
    if is_liquid:
        fluid = {'fluid_name': media, 'is_water': False, 'default_state': 'liquid',
                 'density_liquid': None, 'density_gas': None, 'molecular_weight': 18.015,
                 'cp_cv_ratio': 1.3, 'critical_pressure': None, 'vapor_pressure': None,
                 'viscosity': None}
    else:
        fdef = FLUID[media]
        fluid = {'fluid_name': media, 'is_water': False, 'default_state': 'gas',
                 'density_liquid': None, 'density_gas': None, 'molecular_weight': fdef['mw'],
                 'cp_cv_ratio': fdef['gamma'],
                 'critical_pressure': 3786.0 if media == '空气' else None,
                 'vapor_pressure': 0.0, 'viscosity': None}
    du = c['density_unit'].upper().replace(' ', '')
    fu = c['flow_unit'].upper()
    raw = {
        'case_no': int(c['slot']), 'case_name': f"工况{c['slot']}",
        'flow_mass': None, 'flow_vol': None, 'flow_mass_unit': None, 'flow_vol_unit': None,
        'p1': fnum(c['p1']), 'p1_unit': PMAP.get(c['p1_unit'].upper().strip()),
        'p2': fnum(c['p2']), 'p2_unit': PMAP.get(c['p2_unit'].upper().strip()),
        't1': fnum(c['t1']), 't1_unit': '℃',
        'density_override': None, 'density_override_unit': None,
        'pipe_diameter': fnum(c['pipe_id_mm']), 'pipe_diameter_unit': 'mm',
        'pipe_wall': 4.5, 'pipe_wall_unit': 'mm',
        'fluid_name_custom': media, 'fluid_name': None,
    }
    if 'NM3' in du:
        raw['density_override'], raw['density_override_unit'] = fnum(c['density']), 'kg_Nm3'
    elif 'KG/M3' in du:
        raw['density_override'], raw['density_override_unit'] = fnum(c['density']), 'kg_m3'
    if 'NM3' in fu:
        raw['flow_vol'], raw['flow_vol_unit'], raw['flow_unit'] = fnum(c['flow']), 'Nm3_h', 'vol'
    elif 'KG' in fu:
        raw['flow_mass'], raw['flow_mass_unit'], raw['flow_unit'] = fnum(c['flow']), 'kg_h', 'mass'
    else:
        raw['flow_vol'], raw['flow_vol_unit'], raw['flow_unit'] = fnum(c['flow']), 'm3_h', 'vol'
    try:
        conv = convert_process_case(raw, db_session=db)
    except Exception as e:
        out.append({'case_id': c['case_id'], 'error': f'convert {type(e).__name__}: {e}'})
        continue
    kw = {k: v for k, v in conv.items() if k in (
        'p1', 'p2', 't1', 'density_override', 'density_gas', 'density_liquid',
        'pipe_diameter', 'pipe_wall', 'distance')}
    kw['mass_flow'] = conv.get('flow_mass') or 0.0
    kw['vol_flow'] = conv.get('flow_vol') or 0.0
    kw['flow_unit'] = conv.get('flow_unit') or 'mass'
    rated = fnum(c['rated_cv']) or 0.0
    d, D = fnum(c['dn_mm']), fnum(c['pipe_id_mm'])
    butterfly = model.upper().startswith('BT')
    base = dict(rated_cv=rated, fl=0.55 if butterfly else 0.9, xt=0.35 if butterfly else 0.72,
                fd=0.46, port_diameter=d or 0.0, pipe_diameter=D or 0.0, reduced_port=False,
                factor_curves=meta['curves'])
    rec = {'case_id': c['case_id'], 'valve_id': c['valve_id'], 'slot': int(c['slot']),
           'model': model, 'media': media, 'dn': d, 'pipe_id': D,
           'p1_kpa': conv.get('p1'), 'p2_kpa': conv.get('p2'), 't1': conv.get('t1'),
           'rho': conv.get('density_override'),
           'rated_cv': rated, 'sample_cv': fnum(c['sample_cv']), 'sample_open': fnum(c['sample_open']),
           'curve_src': meta['curve_src'], 'stroke_mode': meta['stroke_mode']}
    try:
        res = calculate_case(case_no=int(c['slot']), case_name=f"工况{c['slot']}", fluid=fluid,
                             valve_coeffs=ValveCoeffs(**base), rated_cv_select=rated, **kw)
        cv = res.cv
        rec.update({'cv': getattr(cv, 'cv_required', None), 'fp': getattr(cv, 'fp', None),
                    'fl_eff': getattr(cv, 'fl_eff', None), 'xt_eff': getattr(cv, 'x_t_eff', None),
                    'full_dp': (cv.detail or {}).get('Cv_full_dp') if getattr(cv, 'detail', None) else None,
                    'regime': getattr(cv, 'flow_regime', None), 'status': res.status})
        if VERSION == 'old':
            rec['open'] = getattr(cv, 'opening_pct', None)
        else:
            rec['open'] = compute_opening(getattr(cv, 'cv_required', 0) or 0, rated,
                                          stroke_mode=meta['stroke_mode'], eqcv=meta['eqcv'],
                                          fstk=meta['fstk'], characteristic='', rangeability=None)
            b2 = dict(base, port_diameter=D or d or 0.0)
            res2 = calculate_case(case_no=int(c['slot']), case_name=f"工况{c['slot']}", fluid=fluid,
                                  valve_coeffs=ValveCoeffs(**b2), rated_cv_select=rated, **kw)
            rec['cv_norp'] = getattr(res2.cv, 'cv_required', None)
    except Exception as e:
        rec['error'] = f'calc {type(e).__name__}: {e}'
    out.append(rec)
json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('写入', OUT, 'cases', len(out), 'errors', sum(1 for x in out if 'error' in x), 'ver', VERSION)
db.close()
