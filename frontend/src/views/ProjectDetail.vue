<template>
  <div>
    <div class="page-card">
      <div class="page-title">
        <el-icon><FolderOpened /></el-icon>
        <span v-if="project">{{ project.project_code }} · {{ project.project_name }}</span>
        <el-button style="margin-left:auto" @click="$router.push('/projects')"><el-icon><Back /></el-icon>返回项目列表</el-button>
        <el-button type="primary" @click="openDialog()"><el-icon><Plus /></el-icon>新建位号</el-button>
      </div>
      <el-descriptions v-if="project" :column="4" border size="small" style="margin-bottom:14px">
        <el-descriptions-item label="客户">{{ project.client || '—' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ project.status }}</el-descriptions-item>
        <el-descriptions-item label="位号数">{{ project.valve_count }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ fmt(project.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="说明" :span="4">{{ project.description || '—' }}</el-descriptions-item>
      </el-descriptions>

      <el-form inline>
        <el-form-item label="关键词">
          <el-input v-model="keyword" placeholder="位号/名称/用途" clearable style="width:220px" @keyup.enter="load" @clear="load" />
        </el-form-item>
        <el-button type="primary" @click="load">查询</el-button>
      </el-form>

      <el-table :data="list" v-loading="loading" border stripe @row-click="rowClick" style="cursor:pointer">
        <el-table-column prop="tag_no" label="位号" width="130">
          <template #default="{row}"><strong>{{ row.tag_no }}</strong></template>
        </el-table-column>
        <el-table-column prop="valve_name" label="名称" min-width="160" />
        <el-table-column prop="service" label="用途/介质" min-width="160" />
        <el-table-column prop="valve_type" label="阀门类型" width="120" />
        <el-table-column prop="line_size" label="管道" width="100" />
        <el-table-column prop="current_version" label="当前版本" width="100" align="center">
          <template #default="{row}"><el-tag v-if="row.current_version" type="success">V{{ row.current_version }}</el-tag><span v-else class="muted">—</span></template>
        </el-table-column>
        <el-table-column prop="calc_count" label="版本数" width="80" align="center" />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" @click.stop="rowClick(row)">计算</el-button>
            <el-button link type="warning" @click.stop="goSelection(row)">选型</el-button>
            <el-button link type="primary" @click.stop="openDialog(row)">编辑</el-button>
            <el-button link type="danger" @click.stop="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id?'编辑位号':'新建位号'" width="560px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="位号" required><el-input v-model="form.tag_no" placeholder="如 TV-201" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="form.valve_name" /></el-form-item>
        <el-form-item label="用途/介质"><el-input v-model="form.service" /></el-form-item>
        <el-form-item label="阀门类型">
          <el-select v-model="form.valve_type" style="width:100%" filterable :disabled="true" placeholder="请先在计算页选型">
            <el-option v-for="t in valveTypes" :key="t" :label="t" :value="t" />
          </el-select>
          <div class="form-hint">从计算页「阀门选型配置」自动读取</div>
        </el-form-item>
        <el-form-item label="管道规格"><el-input v-model="form.line_size" disabled placeholder="如 DN150" /><div class="form-hint">从计算参数读取</div></el-form-item>
        <el-form-item label="壁厚等级"><el-input v-model="form.line_schedule" disabled placeholder="如 Sch40" /><div class="form-hint">从计算参数读取</div></el-form-item>
        <el-form-item label="缩径">
          <el-switch v-model="form.reduced_port" disabled />
          <div class="form-hint">从计算参数读取</div>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { projectsApi, valvesApi } from '@/api'

const route = useRoute()
const router = useRouter()
const pid = ref(route.params.pid)
const project = ref(null)
const list = ref([])
const loading = ref(false)
const keyword = ref('')
const dialogVisible = ref(false)
const form = ref({})
const valveTypes = ['单座柱塞阀','套筒阀','双座阀','角阀','偏心旋转阀','V型球阀','球阀','蝶阀','隔膜阀','低噪音阀','多级降压阀']

function fmt(d) { return d ? new Date(d).toLocaleString('zh-CN') : '' }

async function load() {
  loading.value = true
  try {
    project.value = await projectsApi.get(pid.value)
    list.value = await valvesApi.list(pid.value, keyword.value)
  } catch (e) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

function openDialog(row) {
  form.value = row ? { ...row } : { tag_no:'', valve_name:'', service:'', valve_type:'', line_size:'', line_schedule:'', reduced_port:false, status:'设计中', remark:'' }
  dialogVisible.value = true
}

async function save() {
  try {
    if (form.value.id) await valvesApi.update(pid.value, form.value.id, form.value)
    else await valvesApi.create(pid.value, form.value)
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } catch (e) { ElMessage.error(e.message) }
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除位号「${row.tag_no}」及其所有计算版本?`, '警告', { type:'warning' })
  await valvesApi.remove(pid.value, row.id)
  ElMessage.success('已删除')
  load()
}

function rowClick(row) { router.push({ name:'valve-calc', params:{ pid: pid.value, vid: row.id } }) }
function goSelection(row) { router.push({ name:'valve-selection', params:{ pid: pid.value, vid: row.id } }) }

watch(() => route.params.pid, (v) => { if (v) { pid.value = v; load() } })
onMounted(load)
</script>

<style scoped>
.form-hint {
  font-size: 11px;
  color: #909399;
  line-height: 1.3;
  margin-top: 2px;
}
:deep(.el-form-item.is-disabled) {
  opacity: 0.75;
}
</style>
