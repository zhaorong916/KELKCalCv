"""生成系统测试数据

生成内容:
  项目1: 某化工厂锅炉给水系统 (3个位号)
    TV-1001 给水调节阀 - 水(液) 5组工况 + V2版本
    TV-1002 减温水调节阀 - 水(液) 3组工况
    PV-2001 主蒸汽压力调节阀 - 过热蒸汽 4组工况
  项目2: 某炼油厂常减压装置 (3个位号)
    FV-301 常压炉燃料气调节阀 - 天然气 5组工况
    LCV-302 回流罐液位调节阀 - 汽油(液) 4组工况
    FV-303 原料油流量调节阀 - 两相流 3组工况
  项目3: 某电厂空分装置 (2个位号)
    TV-401 空气流量调节阀 - 空气 5组工况
    PV-402 氮气压力调节阀 - 氮气 3组工况

用法: python seed_test_data.py
"""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000/api/v1"


def req(method, path, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, {"_raw": raw}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"_raw": raw}


def get_fluid_map():
    """获取介质库，返回 {名称: id}"""
    s, fluids = req("GET", "/fluids")
    if s != 200:
        print(f"获取介质库失败: {s}")
        sys.exit(1)
    return {f["fluid_name"]: f["id"] for f in fluids}


def create_project(code, name, client, desc):
    s, r = req("POST", "/projects", {
        "project_code": code,
        "project_name": name,
        "client": client,
        "description": desc,
        "status": "进行中",
    })
    if s == 200:
        print(f"  [项目] 创建 {code} {name} (id={r['id']})")
        return r
    elif s == 400:
        # 已存在，查询
        s2, lst = req("GET", f"/projects?keyword={code}")
        for p in lst:
            if p["project_code"] == code:
                print(f"  [项目] 已存在 {code} (id={p['id']})")
                return p
    print(f"  [项目] 创建失败 {code}: {s} {r}")
    return None


def create_valve(pid, tag, name, service, line_size, vtype, reduced=False):
    s, r = req("POST", f"/projects/{pid}/valves", {
        "tag_no": tag,
        "valve_name": name,
        "service": service,
        "line_size": line_size,
        "valve_type": vtype,
        "reduced_port": reduced,
        "status": "设计中",
    })
    if s == 200:
        print(f"    [位号] 创建 {tag} {name} (id={r['id']})")
        return r
    elif s == 400:
        s2, lst = req("GET", f"/projects/{pid}/valves")
        for v in lst:
            if v["tag_no"] == tag:
                print(f"    [位号] 已存在 {tag} (id={v['id']})")
                return v
    print(f"    [位号] 创建失败 {tag}: {s} {r}")
    return None


def create_version(vid, label, standard="IEC60534"):
    s, r = req("POST", f"/valves/{vid}/calculations", {
        "version_label": label,
        "calc_standard": standard,
        "remark": "",
    })
    if s == 200:
        print(f"      [版本] 创建 V{r['version_no']} {label} (id={r['id']})")
        return r
    print(f"      [版本] 创建失败: {s} {r}")
    return None


def save_config_run(vid, cid, config, cases):
    """保存配置+工况+执行计算"""
    s, _ = req("PUT", f"/valves/{vid}/calculations/{cid}/config", config)
    if s != 200:
        print(f"      [配置] 保存失败: {s}")
        return False
    s, _ = req("PUT", f"/valves/{vid}/calculations/{cid}/cases", cases)
    if s != 200:
        print(f"      [工况] 保存失败: {s}")
        return False
    s, results = req("POST", f"/valves/{vid}/calculations/{cid}/run")
    if s != 200:
        print(f"      [计算] 执行失败: {s} {results}")
        return False
    for r in results:
        cv = (r.get("cv") or {}).get("cv_required")
        noise = (r.get("noise") or {}).get("noise_dba")
        cv_str = f"{cv:.2f}" if cv is not None else "N/A"
        nz_str = f"{noise:.1f}" if noise is not None else "N/A"
        print(f"        工况{r['case_no']} {r.get('case_name','')}: "
              f"{r.get('phase','')} Cv={cv_str} 噪音={nz_str}dB(A) [{r.get('status','')}]")
    return True


def main():
    print("=" * 70)
    print("生成系统测试数据")
    print("=" * 70)

    fm = get_fluid_map()
    print(f"介质库: {len(fm)} 种")
    print()

    # ================================================================
    # 项目1: 某化工厂锅炉给水系统
    # ================================================================
    print("━" * 70)
    print("项目1: 某化工厂锅炉给水系统")
    print("━" * 70)
    p1 = create_project("BF-2026-001", "锅炉给水调节阀选型项目", "某化工有限公司",
                        "2×130t/h 锅炉给水及主蒸汽系统调节阀 Cv 计算与噪音分析")
    if not p1:
        return 1
    pid1 = p1["id"]

    # --- 位号1: TV-1001 给水调节阀 (水, 5组工况) ---
    print("\n  ▶ TV-1001 给水调节阀")
    v1 = create_valve(pid1, "TV-1001", "给水主调节阀", "锅炉给水", "DN80", "单座柱塞阀")
    vid1 = v1["id"]
    c1 = create_version(vid1, "初步选型")
    cid1 = c1["id"]
    cfg1 = {
        "valve_style": "单座柱塞阀", "flow_characteristic": "等百分比",
        "port_diameter": 50, "rated_cv": 80, "fl": 0.9, "xt": 0.72, "fd": 0.46,
    }
    cases1 = [
        {"case_no":1,"case_name":"正常工况","fluid_id":fm["水"],"flow_mass":120000,"flow_unit":"mass",
         "p1":680,"p2":220,"t1":25,"pipe_diameter":80,"pipe_wall":4,"distance":1.0},
        {"case_no":2,"case_name":"最大工况","fluid_id":fm["水"],"flow_mass":150000,"flow_unit":"mass",
         "p1":700,"p2":200,"t1":40,"pipe_diameter":80,"pipe_wall":4,"distance":1.0},
        {"case_no":3,"case_name":"最小工况","fluid_id":fm["水"],"flow_mass":60000,"flow_unit":"mass",
         "p1":650,"p2":250,"t1":20,"pipe_diameter":80,"pipe_wall":4,"distance":1.0},
        {"case_no":4,"case_name":"开工工况","fluid_id":fm["水"],"flow_mass":80000,"flow_unit":"mass",
         "p1":660,"p2":240,"t1":30,"pipe_diameter":80,"pipe_wall":4,"distance":1.0},
        {"case_no":5,"case_name":"事故工况","fluid_id":fm["水"],"flow_mass":100000,"flow_unit":"mass",
         "p1":690,"p2":210,"t1":35,"pipe_diameter":80,"pipe_wall":4,"distance":1.0},
    ]
    save_config_run(vid1, cid1, cfg1, cases1)

    # TV-1001 V2 版本(更改阀门参数)
    print("\n  ▶ TV-1001 V2 (阀门参数调整)")
    c1v2 = create_version(vid1, "阀门选型优化(改用套筒阀)")
    cfg1v2 = {
        "valve_style": "套筒阀", "flow_characteristic": "等百分比",
        "port_diameter": 55, "rated_cv": 100, "fl": 0.9, "xt": 0.75, "fd": 0.42,
    }
    save_config_run(vid1, c1v2["id"], cfg1v2, cases1)

    # --- 位号2: TV-1002 减温水调节阀 (水, 3组工况) ---
    print("\n  ▶ TV-1002 减温水调节阀")
    v2 = create_valve(pid1, "TV-1002", "减温水调节阀", "过热器减温水", "DN25", "单座柱塞阀")
    vid2 = v2["id"]
    c2 = create_version(vid2, "初步选型")
    cfg2 = {
        "valve_style": "单座柱塞阀", "flow_characteristic": "线性",
        "port_diameter": 20, "rated_cv": 12, "fl": 0.9, "xt": 0.72, "fd": 0.46,
    }
    cases2 = [
        {"case_no":1,"case_name":"正常","fluid_id":fm["水"],"flow_mass":5000,"flow_unit":"mass",
         "p1":1500,"p2":500,"t1":30,"pipe_diameter":25,"pipe_wall":3,"distance":1.0},
        {"case_no":2,"case_name":"最大","fluid_id":fm["水"],"flow_mass":8000,"flow_unit":"mass",
         "p1":1600,"p2":450,"t1":40,"pipe_diameter":25,"pipe_wall":3,"distance":1.0},
        {"case_no":3,"case_name":"最小","fluid_id":fm["水"],"flow_mass":2000,"flow_unit":"mass",
         "p1":1400,"p2":600,"t1":25,"pipe_diameter":25,"pipe_wall":3,"distance":1.0},
    ]
    save_config_run(vid2, c2["id"], cfg2, cases2)

    # --- 位号3: PV-2001 主蒸汽压力调节阀 (过热蒸汽, 4组工况) ---
    print("\n  ▶ PV-2001 主蒸汽压力调节阀")
    v3 = create_valve(pid1, "PV-2001", "主蒸汽压力调节阀", "主蒸汽压力控制", "DN100", "套筒阀")
    vid3 = v3["id"]
    c3 = create_version(vid3, "初步选型")
    cfg3 = {
        "valve_style": "套筒阀", "flow_characteristic": "等百分比",
        "port_diameter": 80, "rated_cv": 200, "fl": 0.88, "xt": 0.75, "fd": 0.42,
    }
    cases3 = [
        {"case_no":1,"case_name":"正常","fluid_id":fm["过热蒸汽"],"flow_mass":100000,"flow_unit":"mass",
         "p1":5500,"p2":4500,"t1":485,"pipe_diameter":150,"pipe_wall":8,"distance":1.0},
        {"case_no":2,"case_name":"最大","fluid_id":fm["过热蒸汽"],"flow_mass":130000,"flow_unit":"mass",
         "p1":5600,"p2":4400,"t1":490,"pipe_diameter":150,"pipe_wall":8,"distance":1.0},
        {"case_no":3,"case_name":"最小","fluid_id":fm["过热蒸汽"],"flow_mass":60000,"flow_unit":"mass",
         "p1":5400,"p2":4800,"t1":480,"pipe_diameter":150,"pipe_wall":8,"distance":1.0},
        {"case_no":4,"case_name":"启动","fluid_id":fm["饱和蒸汽"],"flow_mass":40000,"flow_unit":"mass",
         "p1":4500,"p2":3500,"t1":257,"pipe_diameter":150,"pipe_wall":8,"distance":1.0},
    ]
    save_config_run(vid3, c3["id"], cfg3, cases3)

    # ================================================================
    # 项目2: 某炼油厂常减压装置
    # ================================================================
    print("\n" + "━" * 70)
    print("项目2: 某炼油厂常减压装置")
    print("━" * 70)
    p2 = create_project("CDU-2026-002", "常减压装置调节阀选型项目", "某炼化股份有限公司",
                        "500万吨/年常减压装置关键调节阀 Cv 计算与噪音评估")
    if not p2:
        return 1
    pid2 = p2["id"]

    # --- 位号4: FV-301 常压炉燃料气调节阀 (天然气, 5组工况) ---
    print("\n  ▶ FV-301 常压炉燃料气调节阀")
    v4 = create_valve(pid2, "FV-301", "常压炉燃料气调节阀", "燃料天然气", "DN50", "单座柱塞阀")
    vid4 = v4["id"]
    c4 = create_version(vid4, "初步选型")
    cfg4 = {
        "valve_style": "单座柱塞阀", "flow_characteristic": "等百分比",
        "port_diameter": 35, "rated_cv": 40, "fl": 0.9, "xt": 0.72, "fd": 0.46,
    }
    cases4 = [
        {"case_no":1,"case_name":"正常","fluid_id":fm["天然气(典型)"],"flow_mass":3000,"flow_unit":"mass",
         "p1":400,"p2":120,"t1":20,"pipe_diameter":50,"pipe_wall":4,"distance":1.0},
        {"case_no":2,"case_name":"最大","fluid_id":fm["天然气(典型)"],"flow_mass":4500,"flow_unit":"mass",
         "p1":420,"p2":110,"t1":25,"pipe_diameter":50,"pipe_wall":4,"distance":1.0},
        {"case_no":3,"case_name":"最小","fluid_id":fm["天然气(典型)"],"flow_mass":1200,"flow_unit":"mass",
         "p1":380,"p2":150,"t1":15,"pipe_diameter":50,"pipe_wall":4,"distance":1.0},
        {"case_no":4,"case_name":"开工","fluid_id":fm["天然气(典型)"],"flow_mass":2000,"flow_unit":"mass",
         "p1":390,"p2":130,"t1":18,"pipe_diameter":50,"pipe_wall":4,"distance":1.0},
        {"case_no":5,"case_name":"事故","fluid_id":fm["天然气(典型)"],"flow_mass":3800,"flow_unit":"mass",
         "p1":410,"p2":100,"t1":22,"pipe_diameter":50,"pipe_wall":4,"distance":1.0},
    ]
    save_config_run(vid4, c4["id"], cfg4, cases4)

    # --- 位号5: LCV-302 回流罐液位调节阀 (汽油液态, 4组工况) ---
    print("\n  ▶ LCV-302 回流罐液位调节阀")
    v5 = create_valve(pid2, "LCV-302", "回流罐液位调节阀", "汽油回流", "DN40", "单座柱塞阀")
    vid5 = v5["id"]
    c5 = create_version(vid5, "初步选型")
    cfg5 = {
        "valve_style": "单座柱塞阀", "flow_characteristic": "线性",
        "port_diameter": 28, "rated_cv": 25, "fl": 0.9, "xt": 0.72, "fd": 0.46,
    }
    # 用甲醇近似汽油(液态轻烃)，覆盖密度/粘度
    cases5 = [
        {"case_no":1,"case_name":"正常","fluid_id":fm["甲醇"],"flow_mass":15000,"flow_unit":"mass",
         "p1":600,"p2":200,"t1":30,"pipe_diameter":40,"pipe_wall":4,"distance":1.0,
         "density_override":780},
        {"case_no":2,"case_name":"最大","fluid_id":fm["甲醇"],"flow_mass":20000,"flow_unit":"mass",
         "p1":650,"p2":180,"t1":35,"pipe_diameter":40,"pipe_wall":4,"distance":1.0,
         "density_override":775},
        {"case_no":3,"case_name":"最小","fluid_id":fm["甲醇"],"flow_mass":6000,"flow_unit":"mass",
         "p1":550,"p2":250,"t1":25,"pipe_diameter":40,"pipe_wall":4,"distance":1.0,
         "density_override":785},
        {"case_no":4,"case_name":"开工","fluid_id":fm["乙醇"],"flow_mass":10000,"flow_unit":"mass",
         "p1":580,"p2":220,"t1":28,"pipe_diameter":40,"pipe_wall":4,"distance":1.0},
    ]
    save_config_run(vid5, c5["id"], cfg5, cases5)

    # --- 位号6: FV-303 原料油流量调节阀 (两相流, 3组工况) ---
    print("\n  ▶ FV-303 原料油流量调节阀 (气液两相)")
    v6 = create_valve(pid2, "FV-303", "原料油流量调节阀", "原料油(气液两相)", "DN65", "套筒阀")
    vid6 = v6["id"]
    c6 = create_version(vid6, "初步选型(两相流)")
    cfg6 = {
        "valve_style": "套筒阀", "flow_characteristic": "等百分比",
        "port_diameter": 50, "rated_cv": 60, "fl": 0.88, "xt": 0.75, "fd": 0.42,
    }
    cases6 = [
        {"case_no":1,"case_name":"正常","fluid_id":fm["空气"],"flow_mass":0,"flow_unit":"mass",
         "p1":800,"p2":300,"t1":80,"pipe_diameter":65,"pipe_wall":5,"distance":1.0,
         "mass_flow_gas":5000,"mass_flow_liquid":15000,"twophase_method":"additive",
         "density_gas":4.0,"density_liquid":850},
        {"case_no":2,"case_name":"最大","fluid_id":fm["空气"],"flow_mass":0,"flow_unit":"mass",
         "p1":850,"p2":280,"t1":90,"pipe_diameter":65,"pipe_wall":5,"distance":1.0,
         "mass_flow_gas":7000,"mass_flow_liquid":20000,"twophase_method":"additive",
         "density_gas":4.2,"density_liquid":840},
        {"case_no":3,"case_name":"最小","fluid_id":fm["空气"],"flow_mass":0,"flow_unit":"mass",
         "p1":750,"p2":350,"t1":70,"pipe_diameter":65,"pipe_wall":5,"distance":1.0,
         "mass_flow_gas":2500,"mass_flow_liquid":8000,"twophase_method":"additive",
         "density_gas":3.8,"density_liquid":860},
    ]
    save_config_run(vid6, c6["id"], cfg6, cases6)

    # ================================================================
    # 项目3: 某电厂空分装置
    # ================================================================
    print("\n" + "━" * 70)
    print("项目3: 某电厂空分装置")
    print("━" * 70)
    p3 = create_project("ASU-2026-003", "空分装置调节阀选型项目", "某电力股份有限公司",
                        "60000Nm³/h 空分装置空气/氮气调节阀 Cv 计算与噪音评估")
    if not p3:
        return 1
    pid3 = p3["id"]

    # --- 位号7: TV-401 空气流量调节阀 (空气, 5组工况) ---
    print("\n  ▶ TV-401 空气流量调节阀")
    v7 = create_valve(pid3, "TV-401", "空气流量调节阀", "压缩空气流量控制", "DN80", "套筒阀")
    vid7 = v7["id"]
    c7 = create_version(vid7, "初步选型")
    cfg7 = {
        "valve_style": "套筒阀", "flow_characteristic": "等百分比",
        "port_diameter": 55, "rated_cv": 100, "fl": 0.88, "xt": 0.75, "fd": 0.42,
    }
    cases7 = [
        {"case_no":1,"case_name":"正常","fluid_id":fm["空气"],"flow_mass":8627,"flow_unit":"mass",
         "p1":600,"p2":400,"t1":27,"pipe_diameter":80,"pipe_wall":4,"distance":1.0},
        {"case_no":2,"case_name":"最大","fluid_id":fm["空气"],"flow_mass":11000,"flow_unit":"mass",
         "p1":650,"p2":380,"t1":30,"pipe_diameter":80,"pipe_wall":4,"distance":1.0},
        {"case_no":3,"case_name":"最小","fluid_id":fm["空气"],"flow_mass":4000,"flow_unit":"mass",
         "p1":550,"p2":450,"t1":20,"pipe_diameter":80,"pipe_wall":4,"distance":1.0},
        {"case_no":4,"case_name":"开工","fluid_id":fm["空气"],"flow_mass":5000,"flow_unit":"mass",
         "p1":570,"p2":430,"t1":22,"pipe_diameter":80,"pipe_wall":4,"distance":1.0},
        {"case_no":5,"case_name":"事故","fluid_id":fm["空气"],"flow_mass":9000,"flow_unit":"mass",
         "p1":620,"p2":390,"t1":28,"pipe_diameter":80,"pipe_wall":4,"distance":1.0},
    ]
    save_config_run(vid7, c7["id"], cfg7, cases7)

    # --- 位号8: PV-402 氮气压力调节阀 (氮气, 3组工况) ---
    print("\n  ▶ PV-402 氮气压力调节阀")
    v8 = create_valve(pid3, "PV-402", "氮气压力调节阀", "氮气压力控制", "DN40", "单座柱塞阀")
    vid8 = v8["id"]
    c8 = create_version(vid8, "初步选型")
    cfg8 = {
        "valve_style": "单座柱塞阀", "flow_characteristic": "等百分比",
        "port_diameter": 25, "rated_cv": 30, "fl": 0.9, "xt": 0.72, "fd": 0.46,
    }
    cases8 = [
        {"case_no":1,"case_name":"正常","fluid_id":fm["氮气"],"flow_mass":2500,"flow_unit":"mass",
         "p1":500,"p2":150,"t1":20,"pipe_diameter":40,"pipe_wall":4,"distance":1.0},
        {"case_no":2,"case_name":"最大","fluid_id":fm["氮气"],"flow_mass":3500,"flow_unit":"mass",
         "p1":550,"p2":120,"t1":25,"pipe_diameter":40,"pipe_wall":4,"distance":1.0},
        {"case_no":3,"case_name":"最小","fluid_id":fm["氮气"],"flow_mass":1000,"flow_unit":"mass",
         "p1":450,"p2":200,"t1":15,"pipe_diameter":40,"pipe_wall":4,"distance":1.0},
    ]
    save_config_run(vid8, c8["id"], cfg8, cases8)

    # ================================================================
    # 汇总
    # ================================================================
    print("\n" + "=" * 70)
    print("测试数据生成完成")
    print("=" * 70)
    print(f"  项目: 3 个")
    print(f"    1. BF-2026-001  锅炉给水调节阀选型项目 (3台阀门, TV-1001含2版本)")
    print(f"    2. CDU-2026-002 常减压装置调节阀选型项目 (3台阀门, 含两相流)")
    print(f"    3. ASU-2026-003 空分装置调节阀选型项目 (2台阀门)")
    print(f"  位号: 8 台 (水/蒸汽/天然气/空气/氮气/两相流 多种介质)")
    print(f"  计算版本: 9 个")
    print(f"  工况: 30+ 组")
    print(f"\n访问前端查看: http://localhost:5173")
    print(f"Swagger 文档: http://localhost:8000/docs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
