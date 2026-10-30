<template>
  <div class="page-card">
    <div class="page-head">
      <div class="page-title"><el-icon><Reading /></el-icon>选型规则库</div>
      <el-button type="primary" size="small" @click="openCreate">+ 新建规则</el-button>
    </div>

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
          <el-switch :model-value="row.is_active" size="small"
                     :loading="toggleLoadingId === row.id"
                     @change="v => toggleActive(row, v)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="110" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="removeRule(row)">删除</el-button>
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

    <!-- 新建 / 编辑规则 -->
    <el-dialog v-model="dialog.visible" :title="dialog.isEdit ? '编辑规则' : '新建规则'"
               width="780px" :close-on-click-modal="false">
      <el-alert v-if="dialog.error" :title="dialog.error" type="error" show-icon
                :closable="false" style="margin-bottom:12px" />
      <el-form label-width="110px" size="small" class="rule-form">
        <div class="form-grid-2">
          <el-form-item label="规则编号" required>
            <el-input v-model="dialog.form.rule_code" :disabled="dialog.isEdit"
                      maxlength="64" placeholder="如 R-GV120-001" />
          </el-form-item>
          <el-form-item label="规则名称" required>
            <el-input v-model="dialog.form.rule_name" maxlength="128" placeholder="一句话说明规则作用" />
          </el-form-item>
          <el-form-item label="类别" required>
            <el-select v-model="dialog.form.category" style="width:100%" @change="onCategoryChange">
              <el-option label="适用范围 scope" value="scope" />
              <el-option label="硬约束 constraint" value="constraint" />
              <el-option label="工况偏好 preference" value="preference" />
              <el-option label="后处理 post_filter" value="post_filter" />
            </el-select>
          </el-form-item>
          <el-form-item label="目标系列">
            <el-select v-model="dialog.form.target_series" filterable allow-create default-first-option
                       placeholder="* 表示全局" style="width:100%">
              <el-option label="*（全局）" value="*" />
              <el-option v-for="s in seriesOptions" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="动作" required>
            <el-select v-model="dialog.form.action" style="width:100%">
              <el-option label="exclude - 排除候选" value="exclude" />
              <el-option label="require - 硬性要求" value="require" />
              <el-option label="boost - 加权加分" value="boost" />
              <el-option label="penalty - 扣分" value="penalty" />
              <el-option label="set_field - 补字段" value="set_field" />
              <el-option label="flag - 标记" value="flag" />
            </el-select>
          </el-form-item>
          <el-form-item label="优先级">
            <el-input-number v-model="dialog.form.priority" :min="1" :max="99" :controls="false"
                             style="width:100%" />
          </el-form-item>
          <el-form-item label="条件组合">
            <el-radio-group v-model="dialog.form.condition_op">
              <el-radio value="and">and（全部满足）</el-radio>
              <el-radio value="or">or（任一满足）</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="启用">
            <el-switch v-model="dialog.form.is_active" />
          </el-form-item>
        </div>
        <el-form-item label="来源参考">
          <el-input v-model="dialog.form.source_ref" maxlength="128" placeholder="如 GC120_210:p4" />
        </el-form-item>

        <!-- 辅助录入：自然语言 / 条件行，写入下方 JSON -->
        <el-form-item label="辅助录入">
          <el-radio-group v-model="dialog.form.mode" size="small" @change="onModeChange">
            <el-radio-button value="nl">自然语言</el-radio-button>
            <el-radio-button value="rows">条件行</el-radio-button>
            <el-radio-button value="json">关闭辅助</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="dialog.form.mode === 'nl'" label="规则描述">
          <div class="nl-field">
            <el-input v-model="dialog.form.nl_text" type="textarea" :rows="3" spellcheck="false"
                      placeholder="例：BT110 在设计温度低于 -5℃ 时排除；空化或闪蒸时 GC210 加 30 分" />
            <div class="nl-bar">
              <el-button size="small" type="primary" plain @click="applyNl">解析并填充</el-button>
              <span class="json-hint">
                支持：低于/高于/不低于/不高于/等于/不等于、区间「-20 到 200」、以上/以下；
                介质/流态/泄漏等级等枚举；排除/要求/加分/扣分/标记/回填
              </span>
            </div>
            <el-alert v-if="dialog.form.nl_error" :title="dialog.form.nl_error" type="error"
                      :closable="false" show-icon style="margin-top:6px" />
            <el-alert v-for="(n, i) in dialog.form.nl_notes" :key="i" :title="n" type="warning"
                      :closable="false" show-icon style="margin-top:6px" />
            <div v-if="dialog.form.nl_preview" class="nl-preview">
              <div class="nl-title">解析结果</div>
              <div class="nl-line">
                目标系列 <code>{{ dialog.form.nl_preview.series }}</code>
                <el-divider direction="vertical" />
                类别 <code>{{ dialog.form.category }}</code>
                <el-divider direction="vertical" />
                动作 <code>{{ dialog.form.action }}</code>
                <span v-if="dialog.form.nl_preview.score != null">（分值 {{ dialog.form.nl_preview.score }}）</span>
              </div>
              <div class="nl-line">条件：{{ dialog.form.nl_preview.desc }}</div>
              <el-alert v-for="(er, i) in dialog.form.nl_preview.errors" :key="'e' + i" :title="er"
                        type="error" :closable="false" show-icon style="margin-top:6px" />
              <div v-if="dialog.form.nl_preview.branches.length > 1" class="nl-branches">
                <div class="nl-title">
                  识别到 {{ dialog.form.nl_preview.branches.length }} 个分支（动作或目标系列不同），点击「采用」切换
                </div>
                <div v-for="(b, i) in dialog.form.nl_preview.branches" :key="'b' + i" class="nl-branch">
                  <span class="nl-branch-idx">{{ i + 1 }}</span>
                  <code>{{ b.target_series || '*' }}</code>
                  <el-tag size="small" effect="plain">{{ b.action || '未识别动作' }}</el-tag>
                  <span class="nl-branch-desc">{{ b.desc }}</span>
                  <el-tag v-if="i === dialog.form.nl_preview.index" size="small" type="success">当前</el-tag>
                  <el-button v-else link type="primary" size="small" @click="applyBranch(i)">采用</el-button>
                </div>
              </div>
            </div>
          </div>
        </el-form-item>

        <el-form-item v-if="dialog.form.mode === 'rows'" label="条件行">
          <div class="rows-field">
            <div v-for="(row, i) in dialog.form.rows" :key="i" class="cond-row">
              <el-select v-model="row.key" size="small" filterable placeholder="字段" style="width:180px"
                         @change="syncRows">
                <el-option-group v-for="grp in fieldGroups" :key="grp.label" :label="grp.label">
                  <el-option v-for="o in grp.options" :key="o.key" :label="o.label" :value="o.key" />
                </el-option-group>
              </el-select>
              <el-select v-model="row.op" size="small" style="width:120px" @change="syncRows">
                <el-option v-for="o in opOptions" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
              <el-input v-model="row.value" size="small" placeholder="值（枚举填 liquid / 空化 / VI）"
                        style="width:200px" @change="syncRows" />
              <el-button link type="danger" size="small" @click="removeRow(i)">删除</el-button>
            </div>
            <div class="nl-bar">
              <el-button size="small" @click="addRow">+ 添加条件</el-button>
              <span class="json-hint">含等号用 ≥ / ≤，严格比较用 &gt; / &lt;；枚举填数据库取值</span>
              <el-button link type="primary" size="small" @click="syncRows">同步到 JSON</el-button>
            </div>
            <el-alert v-if="dialog.form.rows_error" :title="dialog.form.rows_error" type="error"
                      :closable="false" show-icon style="margin-top:6px" />
          </div>
        </el-form-item>

        <el-form-item label="条件表达式 JSON">
          <div class="json-field">
            <el-input v-model="dialog.form.condition_expr_text" type="textarea" :rows="7" spellcheck="false"
                      placeholder='{"media":"liquid","p1_max":{"_min":0}}' />
            <div class="json-hint">
              可用键：media / flow_regime / temp / p1 / dp / dp_ratio / cv_required / rated_cv / opening /
              pipe_size / rangeability / leakage_class / nace 等；
              算子：_eq _ne _min _max _gt _lt _required _or
              <el-button link type="primary" size="small" @click="formatJsonField('condition_expr_text')">格式化</el-button>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="动作参数 JSON">
          <div class="json-field">
            <el-input v-model="dialog.form.action_payload_text" type="textarea" :rows="4" spellcheck="false"
                      placeholder='boost/penalty 用 {"score": 90}；set_field 用 {"field": "fd_mode"}' />
            <div class="json-hint">
              boost/penalty 用 {"score": n}；set_field 用 {"field": "字段名"}；其余动作可留空 {}
              <el-button link type="primary" size="small" @click="formatJsonField('action_payload_text')">格式化</el-button>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="dialog.visible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="dialog.saving" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { selectionApi } from '@/api/selection'
import {
  parseNaturalRule, describeCondition, conditionToRows, rowsToCondition, FIELD_OPTIONS,
} from '@/utils/ruleNl'

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

// ---------------------------------------------------------------------------
// 规则维护：新增 / 编辑 / 启用停用 / 删除
// ---------------------------------------------------------------------------
const CATEGORY_PRIORITY = { scope: 10, constraint: 20, preference: 30, post_filter: 40 }
const toggleLoadingId = ref(null)

// 辅助录入（自然语言 / 条件行）可选项
const fieldGroups = FIELD_OPTIONS
const opOptions = [
  { label: '= 等于', value: '_eq' },
  { label: '≠ 不等于', value: '_ne' },
  { label: '≥ 不低于', value: '_min' },
  { label: '≤ 不高于', value: '_max' },
  { label: '> 高于', value: '_gt' },
  { label: '< 低于', value: '_lt' },
  { label: '属于其一', value: '_or' },
]

const dialog = ref({
  visible: false, isEdit: false, id: null, error: '', saving: false,
  form: emptyForm(),
})

function emptyForm() {
  return {
    rule_code: '', rule_name: '', category: 'scope', target_series: '*',
    action: 'require', priority: 10, condition_op: 'and', source_ref: '',
    is_active: true, condition_expr_text: '{}', action_payload_text: '{}',
    mode: 'nl', nl_text: '', nl_error: '', nl_notes: [], nl_preview: null, nl_result: null,
    nl_auto_name: false,
    rows: [{ key: '', op: '_eq', value: '' }], rows_error: '',
  }
}

function openCreate() {
  dialog.value = { visible: true, isEdit: false, id: null, error: '', saving: false, form: emptyForm() }
}

function openEdit(row) {
  dialog.value = {
    visible: true, isEdit: true, id: row.id, error: '', saving: false,
    form: {
      rule_code: row.rule_code,
      rule_name: row.rule_name,
      category: row.category,
      target_series: row.target_series || '*',
      action: row.action,
      priority: row.priority ?? CATEGORY_PRIORITY[row.category] ?? 10,
      condition_op: row.condition_op || 'and',
      source_ref: row.source_ref || '',
      is_active: row.is_active,
      condition_expr_text: row.condition_expr ? JSON.stringify(row.condition_expr, null, 2) : '{}',
      action_payload_text: row.action_payload ? JSON.stringify(row.action_payload, null, 2) : '{}',
      // 编辑时把已有条件翻译成中文回显，可直接改写后再解析
      mode: 'nl',
      nl_text: describeCondition(row.condition_expr, row.condition_op),
      nl_error: '', nl_notes: [], nl_preview: null, nl_result: null, nl_auto_name: false,
      rows: conditionToRows(row.condition_expr, row.condition_op),
      rows_error: '',
    },
  }
}

function onCategoryChange(c) {
  dialog.value.form.priority = CATEGORY_PRIORITY[c] ?? dialog.value.form.priority
}

// ---------------------------------------------------------------------------
// 辅助录入：自然语言解析 / 条件行 ⇄ JSON
// ---------------------------------------------------------------------------
function onModeChange(m) {
  const f = dialog.value.form
  f.nl_error = ''
  f.rows_error = ''
  if (m === 'rows') {
    let expr = {}
    try { expr = parseJsonObject(f.condition_expr_text, '条件表达式') || {} } catch { expr = {} }
    f.rows = conditionToRows(expr, f.condition_op)
    if (!f.rows.length) f.rows = [{ key: '', op: '_eq', value: '' }]
  }
}

function syncRows() {
  const f = dialog.value.form
  const { expr, errors } = rowsToCondition(f.rows)
  f.rows_error = errors.join('；')
  if (!errors.length) f.condition_expr_text = JSON.stringify(expr, null, 2)
}

function addRow() {
  dialog.value.form.rows.push({ key: '', op: '_eq', value: '' })
}

function removeRow(i) {
  dialog.value.form.rows.splice(i, 1)
  syncRows()
}

function applyNl() {
  const f = dialog.value.form
  f.nl_error = ''
  f.nl_notes = []
  f.nl_preview = null
  f.nl_result = null

  const res = parseNaturalRule(f.nl_text)
  f.nl_notes = res.notes || []
  if (!res.ok) {
    f.nl_error = res.errors.join('；')
    return
  }
  f.nl_result = res
  f.nl_auto_name = !f.rule_name.trim()
  applyBranch(0)
}

/** 采用第 i 个分支（多分支句式时用于切换） */
function applyBranch(i) {
  const f = dialog.value.form
  const res = f.nl_result
  const b = res?.branches?.[i]
  if (!b) return

  if (b.target_series) f.target_series = b.target_series
  if (b.action) f.action = b.action
  // 只在新建时采用推断类别，避免编辑时把原有类别改掉
  if (b.categoryHint && !dialog.value.isEdit) {
    f.category = b.categoryHint
    f.priority = CATEGORY_PRIORITY[b.categoryHint] ?? f.priority
  }
  f.condition_op = b.condition_op
  f.condition_expr_text = JSON.stringify(b.condition_expr, null, 2)
  f.action_payload_text = JSON.stringify(b.action_payload || {}, null, 2)
  if (f.nl_auto_name) f.rule_name = b.suggested_name
  f.rows = conditionToRows(b.condition_expr, b.condition_op)
  f.rows_error = ''
  f.nl_preview = {
    series: f.target_series,
    desc: b.desc,
    score: b.action_payload?.score ?? null,
    errors: b.errors || [],
    branches: res.branches,
    index: i,
  }
}

function parseJsonObject(text, label) {
  if (!text || !text.trim()) return null
  let v
  try {
    v = JSON.parse(text)
  } catch (e) {
    throw new Error(`${label} 不是合法 JSON：${e.message}`)
  }
  if (v === null || Array.isArray(v) || typeof v !== 'object') {
    throw new Error(`${label} 必须是 JSON 对象（形如 {"key": value}）`)
  }
  return v
}

function formatJsonField(key) {
  try {
    dialog.value.form[key] = JSON.stringify(JSON.parse(dialog.value.form[key] || '{}'), null, 2)
    dialog.value.error = ''
  } catch (e) {
    dialog.value.error = `无法格式化：${e.message}`
  }
}

async function saveRule() {
  const f = dialog.value.form
  dialog.value.error = ''
  const missing = []
  if (!f.rule_code.trim()) missing.push('规则编号')
  if (!f.rule_name.trim()) missing.push('规则名称')
  if (!f.category) missing.push('类别')
  if (!f.action) missing.push('动作')
  if (missing.length) {
    dialog.value.error = `缺少必填项：${missing.join('、')}`
    return
  }

  // 条件行模式下先把未失焦的编辑同步进 JSON
  if (f.mode === 'rows') syncRows()
  if (f.rows_error) {
    dialog.value.error = `条件行有误：${f.rows_error}`
    return
  }

  let condition, actionPayload
  try {
    condition = parseJsonObject(f.condition_expr_text, '条件表达式')
    actionPayload = parseJsonObject(f.action_payload_text, '动作参数')
  } catch (e) {
    dialog.value.error = e.message
    return
  }

  const payload = {
    rule_code: f.rule_code.trim(),
    rule_name: f.rule_name.trim(),
    category: f.category,
    target_series: (f.target_series || '*').trim() || '*',
    condition_expr: condition,
    condition_op: f.condition_op || 'and',
    action: f.action,
    action_payload: actionPayload,
    priority: f.priority ?? 10,
    source_ref: f.source_ref || null,
    is_active: f.is_active,
  }

  dialog.value.saving = true
  try {
    if (dialog.value.isEdit) {
      const { rule_code, ...rest } = payload
      await selectionApi.updateRule(dialog.value.id, rest)
      ElMessage.success('规则已更新')
    } else {
      await selectionApi.createRule(payload)
      ElMessage.success('规则已新增')
    }
    dialog.value.visible = false
    await loadRules()
  } catch (e) {
    dialog.value.error = e.message || '保存失败'
  } finally {
    dialog.value.saving = false
  }
}

async function toggleActive(row, val) {
  toggleLoadingId.value = row.id
  try {
    const updated = await selectionApi.updateRule(row.id, { is_active: val })
    Object.assign(row, updated)
    ElMessage.success(val ? '规则已启用' : '规则已停用')
  } catch (e) {
    ElMessage.error(`切换失败：${e.message}`)
  } finally {
    toggleLoadingId.value = null
  }
}

async function removeRule(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除规则「${row.rule_code}」？已被选型记录引用的规则不允许删除，可改为停用。`,
      '删除规则',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch { return }

  try {
    await selectionApi.deleteRule(row.id)
    ElMessage.success('规则已删除')
    await loadRules()
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

async function loadRules() {
  loading.value = true
  try { rules.value = await selectionApi.rules({}) } catch (e) { rules.value = [] } finally { loading.value = false }
}

onMounted(loadRules)
</script>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.filter-bar { margin-bottom: 12px; padding: 8px 12px; background: #fafbfc; border-radius: 4px; }
.rule-code { font-family: Consolas, Monaco, monospace; font-size: 12px; color: #409eff; }
.muted { color: #909399; font-size: 12px; }
.rule-detail { padding: 12px; background: #fafbfc; border-radius: 4px; display: flex; flex-direction: column; gap: 10px; }
.rule-row { display: flex; align-items: flex-start; gap: 12px; }
.rule-row .lbl { min-width: 130px; font-size: 12px; color: #909399; text-align: right; flex-shrink: 0; }
.json-view { flex: 1; background: #fff; padding: 8px 12px; border-radius: 4px; font-size: 11px; font-family: Consolas, Monaco, monospace; margin: 0; border: 1px solid #ebeef5; max-height: 200px; overflow: auto; }
.section-footer { margin-top: 12px; padding-top: 12px; border-top: 1px solid #ebeef5; font-size: 13px; color: #606266; display: flex; align-items: center; gap: 4px; }
.rule-form .form-grid-2 { display: grid; grid-template-columns: 1fr 1fr; column-gap: 12px; }
.json-field { width: 100%; }
.json-field :deep(textarea) { font-family: Consolas, Monaco, monospace; font-size: 12px; }
.json-hint { font-size: 12px; color: #909399; line-height: 1.7; margin-top: 2px; }
.nl-field, .rows-field { width: 100%; }
.nl-bar { display: flex; align-items: center; gap: 8px; margin-top: 6px; flex-wrap: wrap; }
.nl-preview { margin-top: 8px; padding: 8px 12px; background: #f0f9eb; border-radius: 4px; font-size: 12px; color: #606266; }
.nl-title { font-weight: 600; margin-bottom: 4px; }
.nl-line { line-height: 1.9; }
.nl-branches { margin-top: 8px; padding-top: 6px; border-top: 1px dashed #dcdfe6; }
.nl-branch { display: flex; align-items: center; gap: 8px; line-height: 2.2; flex-wrap: wrap; }
.nl-branch-idx { display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px;
  border-radius: 50%; background: #e1f3d8; color: #529b2e; font-size: 11px; flex: 0 0 auto; }
.nl-branch-desc { flex: 1 1 160px; color: #606266; }
.cond-row { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
</style>
