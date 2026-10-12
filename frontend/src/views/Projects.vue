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
      </el-form>
      <el-table :data="list" v-loading="loading" border stripe @row-click="rowClick" style="cursor:pointer">
        <el-table-column prop="project_code" label="项目编号" width="140" />
        <el-table-column prop="project_name" label="项目名称" min-width="200" />
        <el-table-column prop="client" label="客户" width="160" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{row}"><el-tag :type="row.status==='进行中'?'warning':'info'">{{ row.status }}</el-tag></template>
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
            <el-option label="进行中" value="进行中" /><el-option label="已完成" value="已完成" /><el-option label="已归档" value="已归档" />
          </el-select>
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
const dialogVisible = ref(false)
const form = ref({})

function fmt(d) { return d ? new Date(d).toLocaleString('zh-CN') : '' }

async function load() {
  loading.value = true
  try { list.value = await projectsApi.list(keyword.value) }
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
  await ElMessageBox.confirm(`确认删除项目「${row.project_name}」及其所有位号与计算?`, '警告', { type: 'warning' })
  await projectsApi.remove(row.id)
  ElMessage.success('已删除')
  load()
}

function rowClick(row) { router.push({ name: 'project-detail', params: { pid: row.id } }) }

onMounted(load)
</script>
