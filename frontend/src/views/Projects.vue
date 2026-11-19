<template>
  <div>
    <div class="page-card">
      <div class="page-title">
        <el-icon><Folder /></el-icon> 项目管理
        <el-button type="primary" style="margin-left:auto" @click="openDialog()">
          <el-icon><Plus /></el-icon>新建项目
        </el-button>
      </div>
      <el-form inline>
        <el-form-item label="关键词">
          <el-input v-model="keyword" placeholder="编号/名称/客户" clearable style="width:240px" @keyup.enter="load" @clear="load" />
        </el-form-item>
        <el-button type="primary" @click="load">查询</el-button>
        <el-form-item label="显示已停用" style="margin-left:12px">
          <el-switch v-model="includeDisabled" @change="load" />
        </el-form-item>
      </el-form>
      <el-table :data="list" v-loading="loading" border stripe @row-click="rowClick" style="cursor:pointer">
        <el-table-column prop="project_code" label="项目编号" width="140" />
        <el-table-column prop="project_name" label="项目名称" min-width="200" />
        <el-table-column prop="client" label="客户" width="160" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{row}">
            <el-tag :type="row.status==='停用'?'danger':(row.status==='进行中'?'warning':'info')">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="valve_count" label="位号数" width="80" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{row}">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{row}">
            <el-button link type="primary" @click.stop="rowClick(row)">进入</el-button>
            <el-button link type="primary" @click.stop="openDialog(row)">编辑</el-button>
            <el-button link type="danger" @click.stop="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id?'编辑项目':'新建项目'" width="520px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="项目编号" required><el-input v-model="form.project_code" /></el-form-item>
        <el-form-item label="项目名称" required><el-input v-model="form.project_name" /></el-form-item>
        <el-form-item label="客户"><el-input v-model="form.client" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width:100%">
            <el-option label="进行中" value="进行中" /><el-option label="已完成" value="已完成" /><el-option label="已归档" value="已归档" /><el-option label="停用" value="停用" />
          </el-select>
          <div class="muted" style="font-size:12px;line-height:1.4">停用后默认隐藏，且仅停用项目允许删除</div>
        </el-form-item>
        <el-form-item label="说明"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { projectsApi } from '@/api'

const router = useRouter()
const list = ref([])
const loading = ref(false)
const keyword = ref('')
const includeDisabled = ref(false)
const dialogVisible = ref(false)
const form = ref({})

function fmt(d) { return d ? new Date(d).toLocaleString('zh-CN') : '' }

async function load() {
  loading.value = true
  try { list.value = await projectsApi.list(keyword.value, includeDisabled.value) }
  catch (e) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

function openDialog(row) {
  form.value = row ? { ...row } : { project_code: '', project_name: '', client: '', status: '进行中', description: '' }
  dialogVisible.value = true
}

async function save() {
  try {
    if (form.value.id) await projectsApi.update(form.value.id, form.value)
    else await projectsApi.create(form.value)
    ElMessage.success('保存成功')
    dialogVisible.value = false
    load()
  } catch (e) { ElMessage.error(e.message) }
}

async function remove(row) {
  if (row.status !== '停用') {
    ElMessage.warning('仅可删除已停用项目，请先编辑项目并将状态改为「停用」')
    return
  }
  try {
    await ElMessageBox.confirm(`确认删除已停用项目「${row.project_name}」及其所有位号与计算?`, '警告', { type: 'warning' })
  } catch { return }
  let force = false
  if (row.selection_record_count > 0) {
    try {
      await ElMessageBox.confirm(
        `该项目存在 ${row.selection_record_count} 条选型记录，删除项目将一并删除这些记录且不可恢复，是否继续?`,
        '再次确认',
        { type: 'warning', confirmButtonText: '一并删除', cancelButtonText: '取消' },
      )
      force = true
    } catch { return }
  }
  try {
    await projectsApi.remove(row.id, force)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

function rowClick(row) { router.push({ name: 'project-detail', params: { pid: row.id } }) }

onMounted(load)
</script>
