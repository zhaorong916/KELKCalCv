"""端到端 API 联调验证脚本

流程: 健康检查 -> 列介质 -> 建项目 -> 建位号 -> 建版本 -> 提交计算(5组工况) -> 查结果 -> 清理
"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def req(method, path, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
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


def main():
    print("=" * 60)
    print("端到端 API 联调验证")
    print("=" * 60)

    # 清理上次失败残留
    s, plist = req("GET", "/projects?keyword=VERIFY-2026-001")
    for p in plist:
        req("DELETE", f"/projects/{p['id']}")
        print(f"[清理] 删除残留项目 id={p['id']}")

    # 0. 健康检查
    s, _ = req("GET", "/health")
    print(f"[1/8] 健康检查: {s}")
    assert s == 200

    # 1. 列介质
    s, fluids = req("GET", "/fluids")
    print(f"[2/8] 介质库: HTTP {s}, 共 {len(fluids)} 种")
    water = next((f for f in fluids if f["fluid_name"] == "水"), None)
    air = next((f for f in fluids if f["fluid_name"] == "空气"), None)
    assert water and air, "缺少水或空气介质"
    water_id, air_id = water["id"], air["id"]
    print(f"      水 id={water_id}, 空气 id={air_id}")

    # 2. 建项目
    s, proj = req("POST", "/projects", {
        "project_code": "VERIFY-2026-001",
        "project_name": "联调验证项目",
        "client": "验证客户",
        "description": "端到端API联调",
    })
    print(f"[3/8] 创建项目: HTTP {s}, id={proj.get('id')}")
    if s != 200:
        # 可能已存在，尝试列出
        s, plist = req("GET", "/projects?keyword=VERIFY-2026-001")
        proj = plist[0] if plist else {}
        print(f"      已存在, id={proj.get('id')}")
    pid = proj["id"]

    # 3. 建位号
    s, valve = req("POST", f"/projects/{pid}/valves", {
        "tag_no": "TV-1001",
        "valve_name": "给水调节阀",
        "service": "锅炉给水",
        "line_size": "DN80",
        "valve_type": "单座柱塞阀",
    })
    print(f"[4/8] 创建位号: HTTP {s}, id={valve.get('id')}")
    if s != 200:
        s, vlist = req("GET", f"/projects/{pid}/valves")
        valve = vlist[0] if vlist else {}
        print(f"      已存在, id={valve.get('id')}")
    vid = valve["id"]

    # 4. 建计算版本
    s, calc = req("POST", f"/valves/{vid}/calculations", {
        "version_label": "初始版本",
        "calc_standard": "IEC60534",
    })
    print(f"[5/8] 创建版本: HTTP {s}, version={calc.get('version_no')}")
    if s != 200:
        s, clist = req("GET", f"/valves/{vid}/calculations")
        calc = clist[0] if clist else {}
        print(f"      已存在, version={calc.get('version_no')}")
    cid = calc["id"]

    # 5. 保存阀门配置
    config = {
        "valve_style": "单座柱塞阀",
        "flow_characteristic": "等百分比",
        "port_diameter": 50,
        "rated_cv": 80,
        "fl": 0.9,
        "xt": 0.72,
        "fd": 0.46,
    }
    s, _ = req("PUT", f"/valves/{vid}/calculations/{cid}/config", config)
    print(f"[6/9] 保存阀门配置: HTTP {s}")

    # 6. 保存工艺工况(5组: 水3组 + 空气2组)
    cases = [
        {
            "case_no": 1, "case_name": "水-正常", "fluid_id": water_id,
            "flow_mass": 120000, "flow_unit": "mass",
            "p1": 680, "p2": 220, "t1": 25,
            "pipe_diameter": 80, "pipe_wall": 4, "distance": 1.0,
        },
        {
            "case_no": 2, "case_name": "水-最大", "fluid_id": water_id,
            "flow_mass": 150000, "flow_unit": "mass",
            "p1": 700, "p2": 200, "t1": 40,
            "pipe_diameter": 80, "pipe_wall": 4, "distance": 1.0,
        },
        {
            "case_no": 3, "case_name": "水蒸汽", "fluid_id": water_id,
            "flow_mass": 5000, "flow_unit": "mass",
            "p1": 1500, "p2": 800, "t1": 200,
            "pipe_diameter": 100, "pipe_wall": 5, "distance": 1.0,
        },
        {
            "case_no": 4, "case_name": "空气-正常", "fluid_id": air_id,
            "flow_mass": 8627, "flow_unit": "mass",
            "p1": 600, "p2": 400, "t1": 27,
            "pipe_diameter": 80, "pipe_wall": 4, "distance": 1.0,
        },
        {
            "case_no": 5, "case_name": "空气-最小", "fluid_id": air_id,
            "flow_mass": 4000, "flow_unit": "mass",
            "p1": 550, "p2": 450, "t1": 20,
            "pipe_diameter": 80, "pipe_wall": 4, "distance": 1.0,
        },
    ]
    s, saved_cases = req("PUT", f"/valves/{vid}/calculations/{cid}/cases", cases)
    print(f"[7/9] 保存工艺工况(5组): HTTP {s}")

    # 7. 执行计算
    s, results = req("POST", f"/valves/{vid}/calculations/{cid}/run")
    print(f"[8/9] 执行计算: HTTP {s}")
    if s == 200:
        for r in results:
            cv = (r.get("cv") or {}).get("cv_required")
            noise = (r.get("noise") or {}).get("noise_dba")
            print(f"      工况{r['case_no']} {r.get('case_name','')}: "
                  f"相态={r.get('phase')} Cv={cv} 噪音={noise}dB(A) 状态={r.get('status')}")
    else:
        print(f"      错误: {json.dumps(results, ensure_ascii=False)}")
        return 1

    # 8. 查询计算详情(含落库结果)
    s, detail = req("GET", f"/valves/{vid}/calculations/{cid}")
    rcount = len(detail.get("results", {})) if isinstance(detail, dict) else 0
    print(f"[9/9] 查询计算详情: HTTP {s}, 落库结果 {rcount} 条")

    # 9. 清理(删除验证项目,级联删除位号/版本/工况/结果)
    s, _ = req("DELETE", f"/projects/{pid}")
    print(f"[清理] 删除验证项目: HTTP {s}")

    print("\n端到端 API 联调验证完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
