<template>
  <div>
    <div class="page-card">
      <div class="page-title"><el-icon><InfoFilled /></el-icon> 关于系统</div>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="系统名称">调节阀 Cv 计算与噪音分析系统</el-descriptions-item>
        <el-descriptions-item label="版本">1.0.0 (MVP)</el-descriptions-item>
        <el-descriptions-item label="架构">B/S 架构 · 前后端分离</el-descriptions-item>
        <el-descriptions-item label="后端">Python · FastAPI · SQLAlchemy</el-descriptions-item>
        <el-descriptions-item label="前端">Vue 3 · Element Plus · Vite</el-descriptions-item>
        <el-descriptions-item label="数据库">Microsoft SQL Server</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="page-card">
      <div class="page-title">计算方法说明</div>
      <el-collapse accordion>
        <el-collapse-item title="流量系数 Cv (IEC 60534-2-1)">
          <ul>
            <li><b>液体(非阻塞)</b>：Q = K·Fp·Cv·√(ΔP/ρ)；K=2.735 (kPa 体系，已量纲验证)</li>
            <li><b>液体(阻塞流)</b>：ΔPch = FL²·(P1 − FF·Pv)，FF = 0.96 − 0.28·√(Pv/Pc)；判定闪蒸/空化</li>
            <li><b>气体/蒸汽</b>：W = K·Fp·Cv·Y·√(x·P1·ρ1)，Y=1−x/(3·Fγ·xT)；临界时 x=Fγ·xT, Y=0.667</li>
            <li><b>两相流</b>：叠加法(Cv=Cv气+Cv液) 或 均相膨胀系数法</li>
          </ul>
        </el-collapse-item>
        <el-collapse-item title="噪音预测 (IEC 60534-8-3 / 8-4)">
          <ul>
            <li>五步物理法：喉部机械功率 → 声效率 → 内部声功率级 → 管壁传声损失 → 距管壁1m A计权声压级</li>
            <li>气体采用 IEC 60534-8-3；液体采用 IEC 60534-8-4(含空化/闪蒸强化)</li>
            <li>注：当前为基于标准方法的工程估算(单峰频带简化整体法)，完整倍频程法为后续增强</li>
          </ul>
        </el-collapse-item>
        <el-collapse-item title="水/蒸汽物性与相态自动判定">
          <ul>
            <li>采用 IAPWS-IF97 工业公式，按温度/压力经饱和曲线自动判定液态/饱和/蒸汽</li>
            <li>密度、粘度、比热比、声速均由 IF97 精确给出(若环境未安装 iapws 库则使用工程近似)</li>
          </ul>
        </el-collapse-item>
        <el-collapse-item title="项目管理与版本">
          <ul>
            <li>项目 → 位号(以 tag_no 为索引) → 计算版本(version_no 自动递增)</li>
            <li>同一台阀门多次计算以版本号区分，支持设置当前生效版本</li>
            <li>单台阀门最多录入 5 组工艺参数同时计算</li>
          </ul>
        </el-collapse-item>
      </el-collapse>
    </div>

    <div class="page-card">
      <div class="page-title">运行环境与启动</div>
      <pre style="background:#1e1e1e;color:#d4d4d4;padding:14px;border-radius:6px;overflow:auto;font-size:13px">
# 1. 后端初始化数据库(需 ODBC Driver 17 for SQL Server)
cd backend
pip install -r requirements.txt
python init_db.py
uvicorn app.main:app --reload --port 8000

# 2. 前端启动
cd frontend
npm install
npm run dev
# 浏览器打开 http://localhost:5173
      </pre>
    </div>
  </div>
</template>

<script setup>
</script>
