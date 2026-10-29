<template>
  <el-container class="layout">
    <!-- 左侧导航 -->
    <el-aside :width="collapsed ? '56px' : '240px'" class="aside">
      <div class="logo">
        <el-icon :size="20" color="#fff"><Tools /></el-icon>
        <span v-show="!collapsed" class="logo-text">KELK Cv 计算</span>
      </div>

      <!-- 快捷入口 -->
      <div class="quick-links" v-show="!collapsed">
        <div class="ql-item" :class="{active: route.path === '/'}" @click="$router.push('/')">
          <el-icon><DataAnalysis /></el-icon><span>工作台</span>
        </div>
        <div class="ql-item" :class="{active: route.path.startsWith('/fluids')}" @click="$router.push('/fluids')">
          <el-icon><Coffee /></el-icon><span>介质物性表</span>
        </div>
        <div class="ql-item" :class="{active: route.path.startsWith('/valve-types')}" @click="$router.push('/valve-types')">
          <el-icon><Operation /></el-icon><span>Cv计算因数</span>
        </div>
        <div class="ql-item" :class="{active: route.path === '/selection' || route.name === 'valve-selection'}" @click="$router.push('/selection')">
          <el-icon><Aim /></el-icon><span>阀门选型</span>
        </div>
        <div class="ql-item" :class="{active: route.path.startsWith('/selection-rules')}" @click="$router.push('/selection-rules')">
          <el-icon><Reading /></el-icon><span>选型规则库</span>
        </div>
        <div class="ql-item" :class="{active: route.path.startsWith('/about')}" @click="$router.push('/about')">
          <el-icon><InfoFilled /></el-icon><span>关于</span>
        </div>
      </div>

      <!-- 项目树导航 -->
      <div class="tree-panel" v-show="!collapsed">
        <div class="tree-title">
          <span>项目 · 位号</span>
          <div class="title-btns">
            <el-icon class="refresh" @click="loadTree" title="刷新"><Refresh /></el-icon>
            <el-icon class="add" @click="$router.push('/projects')" title="管理项目"><Setting /></el-icon>
          </div>
        </div>
        <el-tree
          ref="treeRef"
          :data="treeData"
          :props="treeProps"
          node-key="key"
          :expand-on-click-node="false"
          :current-node-key="currentKey"
          :default-expand-all="true"
          @node-click="onNodeClick"
          class="nav-tree"
          empty-text="暂无项目"
        >
          <template #default="{ node, data }">
            <span class="tree-node" :class="data.type">
              <span class="dot-indicator" :style="{background: data.status_color || '#909399'}"></span>
              <span class="tree-label" :title="node.label">{{ node.label }}</span>
              <el-tag v-if="data.type==='valve' && data.current_version" size="small" type="success" effect="plain" class="ver-tag">V{{ data.current_version }}</el-tag>
              <el-tag v-else-if="data.type==='valve' && !data.current_version" size="small" type="info" effect="plain" class="ver-tag">—</el-tag>
            </span>
          </template>
        </el-tree>
      </div>

      <!-- 折叠态图标 -->
      <div class="quick-links coll" v-show="collapsed">
        <div class="ql-item" :class="{active: route.path === '/'}" @click="$router.push('/')">
          <el-icon :size="18"><DataAnalysis /></el-icon>
        </div>
        <div class="ql-item" @click="collapsed=false; loadTree()">
          <el-icon :size="18"><Folder /></el-icon>
        </div>
        <div class="ql-item" :class="{active: route.path.startsWith('/fluids')}" @click="$router.push('/fluids')">
          <el-icon size="18"><Coffee /></el-icon>
        </div>
        <div class="ql-item" :class="{active: route.path.startsWith('/valve-types')}" @click="$router.push('/valve-types')">
          <el-icon size="18"><Operation /></el-icon>
        </div>
        <div class="ql-item" :class="{active: route.path === '/selection' || route.name === 'valve-selection'}" @click="$router.push('/selection')">
          <el-icon size="18"><Aim /></el-icon>
        </div>
        <div class="ql-item" :class="{active: route.path.startsWith('/selection-rules')}" @click="$router.push('/selection-rules')">
          <el-icon size="18"><Reading /></el-icon>
        </div>
      </div>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="collapsed = !collapsed"><Fold v-if="!collapsed"/><Expand v-else/></el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-for="(c, i) in crumbs" :key="i" :to="c.to">{{ c.text }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tag type="info" effect="plain" size="small">IEC 60534 · GB/T 17213 · ISA-75.01</el-tag>
          <span class="user"><el-icon><User /></el-icon> 工程师</span>
        </div>
      </el-header>

      <el-main class="main">
        <router-view v-slot="{ Component }">
          <keep-alive include="ProjectDetail,Calculation">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { projectsApi, valvesApi, calcApi } from '@/api'

const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const treeData = ref([])

const treeProps = { label: 'label', children: 'children' }

const crumbs = computed(() => {
  const c = []
  if (route.name === 'projects') c.push({ text: '项目管理' })
  else if (route.name === 'project-detail') {
    c.push({ text: '项目管理', to: { path: '/projects' } })
    c.push({ text: `项目 #${route.params.pid}` })
  } else if (route.name === 'valve-calc') {
    c.push({ text: '项目管理', to: { path: '/projects' } })
    c.push({ text: `位号 ${route.params.vid}` })
  } else if (route.name === 'selection') c.push({ text: '阀门选型' })
  else if (route.name === 'valve-selection') {
    c.push({ text: '项目管理', to: { path: '/projects' } })
    c.push({ text: `位号 ${route.params.vid}`, to: { path: `/projects/${route.params.pid}/valves/${route.params.vid}` } })
    c.push({ text: '阀门选型' })
  } else if (route.name === 'selection-rules') c.push({ text: '选型规则库' })
  else if (route.name === 'fluids') c.push({ text: '介质物性表' })
  else if (route.name === 'valve-types') c.push({ text: 'Cv计算因数' })
  return c
})

const currentKey = computed(() => {
  if (route.name === 'project-detail') return `p-${route.params.pid}`
  if (route.name === 'valve-calc') return `v-${route.params.vid}`
  return ''
})

async function loadTree() {
  try {
    const projects = await projectsApi.list()
    const nodes = []
    for (const p of projects) {
      const valves = await valvesApi.list(p.id)
      for (const v of valves) {
        const calcs = await calcApi.list(v.id)
        const cur = calcs.find(c => c.is_current) || calcs[0]
        let status_color = '#909399'
        if (cur) {
          if (cur.status === '已计算') status_color = '#67c23a'
          else status_color = '#e6a23c'
        }
        v.current_version = cur ? cur.version_no : null
        v.status_color = status_color
      }
      nodes.push({
        key: `p-${p.id}`, label: `${p.project_code}`, type: 'project', id: p.id,
        status_color: '#409eff',
        children: valves.map(v => ({
          key: `v-${v.id}`, label: v.tag_no, type: 'valve', id: v.id, pid: p.id,
          current_version: v.current_version, status_color: v.status_color,
        }))
      })
    }
    treeData.value = nodes
  } catch (e) { /* ignore */ }
}

function onNodeClick(data) {
  if (data.type === 'project') router.push({ name: 'project-detail', params: { pid: data.id } })
  else if (data.type === 'valve') router.push({ name: 'valve-calc', params: { pid: data.pid, vid: data.id } })
}

onMounted(loadTree)
watch(() => route.fullPath, loadTree)
defineExpose({ loadTree })
</script>

<style scoped>
.layout { height: 100vh; }
.aside { background: #2c3e50; transition: width .25s; overflow: hidden; display: flex; flex-direction: column; border-right: 1px solid #1a252f; }

.logo {
  height: 52px; display: flex; align-items: center; gap: 10px;
  padding: 0 16px; background: #1a252f; color: #fff; flex-shrink: 0;
  border-bottom: 1px solid #34495e;
}
.logo-text { font-size: 14px; font-weight: 700; white-space: nowrap; letter-spacing: 1px; }

.quick-links {
  padding: 8px; border-bottom: 1px solid #34495e; flex-shrink: 0;
}
.quick-links.coll { padding: 8px 6px; }
.ql-item {
  display: flex; align-items: center; gap: 10px; padding: 8px 12px;
  color: #bdc3c7; cursor: pointer; border-radius: 4px; font-size: 13px;
  transition: background .15s; margin-bottom: 2px;
}
.ql-item:hover { background: #34495e; color: #fff; }
.ql-item.active { background: #3498db; color: #fff; }
.ql-item.coll { justify-content: center; padding: 8px 0; }

.tree-panel {
  flex: 1; overflow-y: auto; padding: 4px 6px 10px;
}
.tree-title {
  color: #7f8c8d; font-size: 11px; padding: 10px 10px 6px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 1px; display: flex; justify-content: space-between; align-items: center;
}
.title-btns { display: flex; gap: 6px; }
.tree-title .refresh, .tree-title .add { cursor: pointer; padding: 2px; border-radius: 3px; }
.tree-title .refresh:hover, .tree-title .add:hover { background: #34495e; color: #fff; }

.nav-tree { background: transparent; --el-tree-node-hover-bg-color: #34495e; }
.nav-tree :deep(.el-tree-node__content) { height: 30px; border-radius: 3px; }
.nav-tree :deep(.el-tree-node__content:hover) { background: #34495e; }
.nav-tree :deep(.el-tree-node.is-current > .el-tree-node__content) {
  background: #3498db !important; color: #fff;
}
.tree-node {
  display: flex; align-items: center; gap: 6px; color: #bdc3c7; font-size: 12px; flex: 1; overflow: hidden;
}
.tree-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.tree-node.project { font-weight: 600; color: #ecf0f1; }
.tree-node.valve { font-weight: 500; }
.dot-indicator { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.ver-tag { transform: scale(.8); margin-left: 2px; }

/* 折叠态滚动条 */
.aside::-webkit-scrollbar { width: 6px; }
.aside::-webkit-scrollbar-thumb { background: #34495e; border-radius: 3px; }

.header {
  background: #fff; border-bottom: 1px solid #e6e8eb;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px; height: 48px;
}
.header-left { display: flex; align-items: center; gap: 14px; }
.collapse-btn { cursor: pointer; font-size: 18px; color: #5a6a7a; }
.header-right { display: flex; align-items: center; gap: 16px; }
.user { display: flex; align-items: center; gap: 4px; cursor: pointer; color: #5a6a7a; font-size: 13px; }

.main { padding: 12px; overflow: auto; background: #f0f2f5; }
</style>
