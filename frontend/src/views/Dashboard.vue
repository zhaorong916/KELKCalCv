<template>
  <div>
    <div class="page-card">
      <div class="page-title"><el-icon><Odometer /></el-icon> 工作台</div>
      <el-row :gutter="16">
        <el-col :span="6" v-for="s in stats" :key="s.label">
          <div class="stat-card" :style="{background: s.bg}">
            <el-icon :size="28"><component :is="s.icon" /></el-icon>
            <div>
              <div class="num">{{ s.value }}</div>
              <div class="lbl">{{ s.label }}</div>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <div class="page-card">
      <div class="page-title"><el-icon><Bell /></el-icon> 计算标准与依据</div>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="流量系数计算">IEC 60534-2-1 / GB/T 17213.2 / ISA-75.01.01</el-descriptions-item>
        <el-descriptions-item label="气体气动噪音">IEC 60534-8-3</el-descriptions-item>
        <el-descriptions-item label="液体水动力噪音">IEC 60534-8-4</el-descriptions-item>
        <el-descriptions-item label="水/蒸汽物性">IAPWS-IF97 工业公式</el-descriptions-item>
        <el-descriptions-item label="相态自动判定">水按温度/压力经饱和曲线自动判定液态或蒸汽</el-descriptions-item>
        <el-descriptions-item label="工况组数">单台阀门最多 5 组工艺参数同时计算</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="page-card">
      <div class="page-title"><el-icon><Guide /></el-icon> 快速入口</div>
      <el-space wrap>
        <el-button type="primary" @click="$router.push('/projects')"><el-icon><FolderAdd /></el-icon>新建/进入项目</el-button>
        <el-button @click="$router.push('/fluids')"><el-icon><Coffee /></el-icon>维护介质物性表</el-button>
      </el-space>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { projectsApi, valvesApi, fluidsApi } from '@/api'

const stats = ref([
  { label: '项目数', value: '-', icon: 'Folder', bg: 'linear-gradient(135deg,#409eff,#337ecc)' },
  { label: '调节阀(位号)', value: '-', icon: 'Switch', bg: 'linear-gradient(135deg,#67c23a,#4e8c2a)' },
  { label: '介质种类', value: '-', icon: 'Coffee', bg: 'linear-gradient(135deg,#e6a23c,#a8741e)' },
  { label: '计算版本数', value: '-', icon: 'Document', bg: 'linear-gradient(135deg,#f56c6c,#b34b4b)' },
])

onMounted(async () => {
  try {
    const [projects, fluids] = await Promise.all([projectsApi.list(), fluidsApi.list()])
    let valveCnt = 0
    for (const p of projects) {
      const vs = await valvesApi.list(p.id)
      valveCnt += vs.length
    }
    stats.value[0].value = projects.length
    stats.value[1].value = valveCnt
    stats.value[2].value = fluids.length
    stats.value[3].value = '—'
  } catch (e) { /* ignore on first run */ }
})
</script>

<style scoped>
.stat-card { color: #fff; border-radius: 8px; padding: 18px; display: flex; align-items: center; gap: 14px; }
.stat-card .num { font-size: 26px; font-weight: 700; }
.stat-card .lbl { font-size: 13px; opacity: .9; }
</style>
