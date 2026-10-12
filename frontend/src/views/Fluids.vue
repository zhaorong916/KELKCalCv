<template>
  <div>
    <div class="page-card">
      <div class="page-title">
        <el-icon><Coffee /></el-icon> 介质物性表
        <el-button type="primary" style="margin-left:auto" @click="openDialog()"><el-icon><Plus /></el-icon>新增介质</el-button>
      </div>
      <el-form inline>
        <el-form-item label="关键词"><el-input v-model="keyword" clearable style="width:220px" @keyup.enter="load" @clear="load" /></el-form-item>
        <el-button type="primary" @click="load">查询</el-button>
      </el-form>
      <el-table :data="list" v-loading="loading" border stripe>
        <el-table-column prop="fluid_name" label="英文名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="fluid_name_cn" label="中文名称" min-width="120" show-overflow-tooltip>
          <template #default="{row}">{{ row.fluid_name_cn || '-' }}</template>
        </el-table-column>
        <el-table-column prop="formula" label="分子式" width="110" />
        <el-table-column prop="default_state" label="相态" width="80">
          <template #default="{row}"><el-tag :type="row.default_state==='liquid'?'':'warning'" size="small">{{ row.default_state==='liquid'?'液态':'气态' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="molecular_weight" label="摩尔质量" width="100" align="right" />
        <el-table-column prop="cp_cv_ratio" label="比热比γ" width="90" align="right" />
        <el-table-column prop="critical_pressure" label="临界压力kPa" width="120" align="right" />
        <el-table-column prop="vapor_pressure" label="饱和蒸汽压kPa" width="130" align="right" />
        <el-table-column prop="viscosity" label="粘度cP" width="90" align="right" />
        <el-table-column prop="is_water" label="水/自动判定" width="110" align="center">
          <template #default="{row}"><el-tag v-if="row.is_water" type="success" size="small">是</el-tag><span v-else class="muted">否</span></template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="page-card">
      <div class="page-title"><el-icon><Drizzling /></el-icon> 水/水蒸汽相态自动判定(验证)</div>
      <el-form inline>
        <el-form-item label="温度℃"><el-input-number v-model="wT" :step="1" controls-position="right" /></el-form-item>
        <el-form-item label="压力kPa(abs)"><el-input-number v-model="wP" :step="10" controls-position="right" /></el-form-item>
        <el-button type="primary" @click="resolveWater">解析</el-button>
      </el-form>
      <el-descriptions v-if="water" :column="4" border size="small">
        <el-descriptions-item label="相态"><el-tag :type="phaseTag">{{ phaseText }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="密度 kg/m³">{{ water.density?.toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="粘度 cP">{{ water.viscosity_cp?.toFixed(4) }}</el-descriptions-item>
        <el-descriptions-item label="比热比 γ">{{ water.gamma?.toFixed(3) }}</el-descriptions-item>
        <el-descriptions-item label="饱和蒸汽压 kPa">{{ water.vapor_pressure_kpa?.toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="声速 m/s">{{ water.speed_of_sound?.toFixed(1) }}</el-descriptions-item>
        <el-descriptions-item label="摩尔质量">{{ water.molecular_weight }}</el-descriptions-item>
        <el-descriptions-item label="临界压力 kPa">{{ water.critical_pressure_kpa }}</el-descriptions-item>
      </el-descriptions>
      <p class="muted" v-else>输入温度与压力后点击"解析"，系统按 IAPWS-IF97 饱和曲线自动判定液态/饱和/蒸汽。</p>
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id?'编辑介质':'新增介质'" width="600px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="介质名称" required><el-input v-model="form.fluid_name" /></el-form-item>
        <el-form-item label="中文名称"><el-input v-model="form.fluid_name_cn" /></el-form-item>
        <el-form-item label="分子式"><el-input v-model="form.formula" /></el-form-item>
        <el-form-item label="默认相态">
          <el-radio-group v-model="form.default_state"><el-radio value="liquid">液态</el-radio><el-radio value="gas">气态</el-radio><el-radio value="twophase">两相</el-radio></el-radio-group>
        </el-form-item>
        <el-form-item label="水(自动判定)"><el-switch v-model="form.is_water" /></el-form-item>
        <el-row :gutter="10">
          <el-col :span="12"><el-form-item label="摩尔质量"><el-input-number v-model="form.molecular_weight" :precision="3" controls-position="right" style="width:100%"/></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="比热比γ"><el-input-number v-model="form.cp_cv_ratio" :precision="3" controls-position="right" style="width:100%"/></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="液态密度"><el-input-number v-model="form.density_liquid" :precision="2" controls-position="right" style="width:100%"/></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="气态密度(标况)"><el-input-number v-model="form.density_gas" :precision="3" controls-position="right" style="width:100%"/></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="临界压力kPa"><el-input-number v-model="form.critical_pressure" :precision="1" controls-position="right" style="width:100%"/></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="饱和蒸汽压kPa"><el-input-number v-model="form.vapor_pressure" :precision="2" controls-position="right" style="width:100%"/></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="粘度cP"><el-input-number v-model="form.viscosity" :precision="4" controls-position="right" style="width:100%"/></el-form-item></el-col>
        </el-row>
      </el-form>
      <template #footer><el-button @click="dialogVisible=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fluidsApi } from '@/api'

const list = ref([])
const loading = ref(false)
const keyword = ref('')
const dialogVisible = ref(false)
const form = ref({})
const wT = ref(120)
const wP = ref(200)
const water = ref(null)

const phaseText = computed(() => ({liquid:'液态',gas:'蒸汽',saturated:'饱和'}[water.value?.phase]||water.value?.phase))
const phaseTag = computed(() => ({liquid:'primary',gas:'warning',saturated:'success'}[water.value?.phase]||'info'))

async function load() {
  loading.value = true
  try { list.value = await fluidsApi.list(keyword.value) }
  catch (e) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

function openDialog(row) {
  form.value = row ? { ...row } : { fluid_name:'', formula:'', default_state:'liquid', is_water:false, molecular_weight:28.97, cp_cv_ratio:1.4, density_liquid:1000, density_gas:1.293, critical_pressure:3785, vapor_pressure:0, viscosity:1.0 }
  dialogVisible.value = true
}

async function save() {
  try {
    if (form.value.id) await fluidsApi.update(form.value.id, form.value)
    else await fluidsApi.create(form.value)
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } catch (e) { ElMessage.error(e.message) }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除介质「${row.fluid_name}」?`, '警告', { type:'warning' })
  await fluidsApi.remove(row.id)
  ElMessage.success('已删除')
  load()
}

async function resolveWater() {
  try { water.value = await fluidsApi.resolveWater(wT.value, wP.value) }
  catch (e) { ElMessage.error(e.message) }
}

onMounted(load)
</script>
