<template>
  <div class="page-card">
    <div class="page-title"><el-icon><Reading /></el-icon>选型规则库（只读）</div>

    <!-- 筛选条 -->
    <el-form inline size="small" class="filter-bar">
      <el-form-item label="类别">
        <el-select v-model="filters.category" clearable placeholder="全部" style="width:140px">
          <el-option label="适用范围" value="scope" />
          <el-option label="硬约束" value="constraint" />
          <el-option label="工况偏好" value="preference" />
          <el-option label="后处理" value="post_filter" />
        </el-select>
      </el-form-item>
      <el-form-item label="目标系列">
        <el-select v-model="filters.target_series" clearable filterable placeholder="全部" style="width:160px">
          <el-option label="* (全局)" value="*" />
          <el-option v-for="s in seriesOptions" :key="s" :label="s" :value="s" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="filters.is_active" clearable placeholder="全部" style="width:100px">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="filters.keyword" clearable placeholder="rule_code / 名称 / source_ref" style="width:200px" />
      </el-form-item>
      <el-form-item>
        <el-button size="small" @click="resetFilters">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 规则表格 -->
    <el-table :data="filteredRules" border size="small" v-loading="loading" style="width:100%">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="rule-detail">
            <div class="rule-row"><span class="lbl">rule_code</span><code>{{ row.rule_code }}</code></div>
            <div class="rule-row"><span class="lbl">condition_expr</span><pre class="json-view">{{ formatJson(row.condition_expr) }}</pre></div>
            <div class="rule-row"><span class="lbl">action_payload</span><pre class="json-view">{{ formatJson(row.action_payload) }}</pre></div>
            <div class="rule-row"><span class="lbl">source_ref</span><span>{{ row.source_ref || '—' }}</span></div>
            <div class="rule-row"><span class="lbl">创建时间</span><span>{{ formatTime(row.created_at) }}</span></div>
            <div class="rule-row"><span class="lbl">更新时间</span><span>{{ formatTime(row.updated_at) }}</span></div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="rule_code" prop="rule_code" width="180">
        <template #default="{ row }"><code class="rule-code">{{ row.rule_code }}</code></template>
      </el-table-column>
      <el-table-column label="rule_name" prop="rule_name" min-width="200" show-overflow-tooltip />
      <el-table-column label="类别" prop="category" width="100" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="categoryTagType(row.category)">{{ categoryLabel(row.category) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="目标系列" prop="target_series" width="110" align="center">
        <template #default="{ row }"><code>{{ row.target_series }}</code></template>
      </el-table-column>
      <el-table-column label="动作" prop="action" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="actionTagType(row.action)" effect="plain">{{ row.action }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="优先级" prop="priority" width="70" align="center" />
      <el-table-column label="来源" prop="source_ref" width="180" show-overflow-tooltip>
        <template #default="{ row }"><span class="muted">{{ row.source_ref || '—' }}</span></template>
      </el-table-column>
      <el-table-column label="启用" prop="is_active" width="70" align="center">
        <template #default="{ row }">
          <el-switch :model-value="row.is_active" disabled size="small" />
        </template>
      </el-table-column>
      <template #empty><span class="muted">无匹配规则</span></template>
    </el-table>

    <!-- 底部统计 -->
    <div class="section-footer">
      <span>共 <b>{{ rules.length }}</b> 条规则</span>
      <el-divider direction="vertical" />
      <span>scope <b>{{ stats.scope }}</b></span>
      <el-divider direction="vertical" />
      <span>constraint <b>{{ stats.constraint }}</b></span>
      <el-divider direction="vertical" />
      <span>preference <b>{{ stats.preference }}</b></span>
      <el-divider direction="vertical" />
      <span>post_filter <b>{{ stats.post_filter }}</b></span>
      <el-divider direction="vertical" />
      <span class="muted">当前筛选匹配 <b>{{ filteredRules.length }}</b> 条</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { selectionApi } from '@/api/selection'

const rules = ref([])
const loading = ref(false)
const filters = ref({ category: null, target_series: null, is_active: null, keyword: null })

const seriesOptions = computed(() => {
  const s = new Set()
  rules.value.forEach(r => { if (r.target_series && r.target_series !== '*') s.add(r.target_series) })
  return Array.from(s).sort()
})

const stats = computed(() => {
  const r = rules.value
  return {
    scope: r.filter(x => x.category === 'scope').length,
    constraint: r.filter(x => x.category === 'constraint').length,
    preference: r.filter(x => x.category === 'preference').length,
    post_filter: r.filter(x => x.category === 'post_filter').length,
  }
})

const filteredRules = computed(() => {
  let list = rules.value
  const f = filters.value
  if (f.category) list = list.filter(r => r.category === f.category)
  if (f.target_series) list = list.filter(r => r.target_series === f.target_series)
  if (f.is_active !== null && f.is_active !== undefined) list = list.filter(r => r.is_active === f.is_active)
  if (f.keyword) {
    const kw = f.keyword.toLowerCase()
    list = list.filter(r =>
      (r.rule_code || '').toLowerCase().includes(kw) ||
      (r.rule_name || '').toLowerCase().includes(kw) ||
      (r.source_ref || '').toLowerCase().includes(kw)
    )
  }
  return list
})

function categoryLabel(c) {
  return { scope: '适用范围', constraint: '硬约束', preference: '工况偏好', post_filter: '后处理' }[c] || c
}
function categoryTagType(c) {
  return { scope: 'primary', constraint: 'success', preference: 'warning', post_filter: 'info' }[c] || 'info'
}
function actionTagType(a) {
  return { exclude: 'danger', require: 'warning', boost: 'success', penalty: 'danger', set_field: 'info', flag: 'info' }[a] || 'info'
}
function formatJson(v) {
  if (v == null) return '—'
  try { return JSON.stringify(v, null, 2) } catch { return String(v) }
}
function formatTime(t) { if (!t) return '—'; try { return new Date(t).toLocaleString('zh-CN', { hour12: false }) } catch { return t } }
function resetFilters() { filters.value = { category: null, target_series: null, is_active: null, keyword: null } }

async function loadRules() {
  loading.value = true
  try { rules.value = await selectionApi.rules({}) } catch (e) { rules.value = [] } finally { loading.value = false }
}

onMounted(loadRules)
</script>

<style scoped>
.filter-bar { margin-bottom: 12px; padding: 8px 12px; background: #fafbfc; border-radius: 4px; }
.rule-code { font-family: Consolas, Monaco, monospace; font-size: 12px; color: #409eff; }
.muted { color: #909399; font-size: 12px; }
.rule-detail { padding: 12px; background: #fafbfc; border-radius: 4px; display: flex; flex-direction: column; gap: 10px; }
.rule-row { display: flex; align-items: flex-start; gap: 12px; }
.rule-row .lbl { min-width: 130px; font-size: 12px; color: #909399; text-align: right; flex-shrink: 0; }
.json-view { flex: 1; background: #fff; padding: 8px 12px; border-radius: 4px; font-size: 11px; font-family: Consolas, Monaco, monospace; margin: 0; border: 1px solid #ebeef5; max-height: 200px; overflow: auto; }
.section-footer { margin-top: 12px; padding-top: 12px; border-top: 1px solid #ebeef5; font-size: 13px; color: #606266; display: flex; align-items: center; gap: 4px; }
</style>
