<template>
  <div class="selection-page">
    <!-- Header -->
    <div class="calc-header">
      <div class="header-left">
        <template v-if="isValveContext">
          <el-tag type="primary" effect="dark" class="tag-tag">{{ valve?.tag_no || `位号 #${valveId}` }}</el-tag>
          <span class="valve-name">{{ valve?.valve_name || valve?.service || '阀门选型' }}</span>
          <span class="muted">{{ valve?.valve_type }} {{ valve?.line_size }}</span>
        </template>
        <template v-else>
          <el-select v-model="projectId" size="small" filterable placeholder="选择项目" style="width:200px" @change="onProjectChange">
            <el-option v-for="p in projects" :key="p.id" :label="`${p.project_code} ${p.project_name||''}`" :value="p.id" />
          </el-select>
          <el-select v-model="valveId" size="small" filterable placeholder="选择位号" style="width:200px" :disabled="!projectId">
            <el-option v-for="v in valves" :key="v.id" :label="v.tag_no" :value="v.id" />
          </el-select>
        </template>
      </div>
      <div class="header-right">
        <el-button size="small" @click="historyDrawer = true" :disabled="!valveId" plain>
          <el-icon><Clock /></el-icon>历史记录
        </el-button>
        <el-button size="small" @click="$router.push('/selection-rules')" plain>
          <el-icon><Reading /></el-icon>规则库
        </el-button>
        <el-divider direction="vertical" />
        <el-button type="success" size="small" @click="runSelection" :loading="running" :disabled="!canRun">
          <el-icon><VideoPlay /></el-icon>运行选型
        </el-button>
      </div>
    </div>

    <!-- 主体双栏 -->
    <div class="calc-body">
      <!-- 左栏：工艺条件输入 -->
      <div class="col-form">
        <!-- 卡片 0：多工况 tab -->
        <div class="section-card">
          <el-tabs v-model="activeCaseIdx" type="card" class="case-tabs" closable @tab-remove="removeCase" @tab-click="onCaseTabClick">
            <el-tab-pane v-for="(c, i) in cases" :key="i" :name="i">
              <template #label>
                <span v-if="i===0">★ 主工况</span>
                <span v-else>工况 {{ i+1 }}</span>
              </template>
            </el-tab-pane>
            <template #add-icon>
              <el-icon v-if="cases.length < MAX_CASES" @click.stop="addCase"><Plus /></el-icon>
            </template>
          </el-tabs>
          <div class="case-tab-footer">
            <el-button size="small" text type="primary" :disabled="cases.length>=MAX_CASES" @click="addCase">
              <el-icon><Plus /></el-icon>添加工况 ({{ cases.length }}/{{ MAX_CASES }})
            </el-button>
            <span class="muted">仅主工况参与选型，其余工况仅归档</span>
          </div>
        </div>

        <!-- 卡片 1：介质与流态 -->
        <div class="section-card">
          <div class="section-title">
            介质与流态
            <el-tag size="small" class="title-tag">当前: {{ activeCaseIdx===0 ? '主工况' : `工况 ${activeCaseIdx+1}` }}</el-tag>
          </div>
          <div class="form-grid">
            <div class="form-row full-width">
              <label>介质</label>
              <el-select v-model="curCase.fluid_id" size="small" filterable allow-create default-first-option placeholder="选择或输入自定义介质" style="width:100%">
                <el-option v-for="f in fluids" :key="f.id" :label="(f.fluid_name_cn || f.fluid_name) + (f.formula ? ' (' + f.formula + ')' : '') + (f.is_water?' ⚡':'')" :value="f.id" />
              </el-select>
            </div>
            <div class="form-row full-width">
              <label>相态</label>
              <el-radio-group v-model="curCase.media" size="small">
                <el-radio-button value="liquid">液态</el-radio-button>
                <el-radio-button value="gas">气态</el-radio-button>
                <el-radio-button value="twophase">两相</el-radio-button>
                <el-radio-button value="steam">蒸汽</el-radio-button>
              </el-radio-group>
              <el-tag v-if="curCase.flow_regime" size="small" :type="regimeTagType(curCase.flow_regime)" style="margin-left:10px">{{ curCase.flow_regime }}</el-tag>
              <span v-else class="muted" style="margin-left:10px">流态 —</span>
            </div>
          </div>
        </div>

        <!-- 卡片 2：工艺参数 -->
        <div class="section-card">
          <div class="section-title">
            工艺参数
            <el-tag size="small" class="title-tag">当前: {{ activeCaseIdx===0 ? '主工况' : `工况 ${activeCaseIdx+1}` }}</el-tag>
          </div>
          <div class="form-col">
            <div class="form-row">
              <div class="label-with-unit">
                <span class="lbl">P1 阀前压力</span>
                <el-select v-model="caseUnits.p1" size="small" class="unit-select">
                  <el-option-group label="公制"><el-option v-for="u in unitsByGroup.pressure?.metric||[]" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" /></el-option-group>
                  <el-option-group label="英制"><el-option v-for="u in unitsByGroup.pressure?.imperial||[]" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" /></el-option-group>
                </el-select>
              </div>
              <el-input-number v-model="curCase.p1" :min="0" :precision="2" size="small" :controls="false" style="flex:1" />
            </div>
            <div class="form-row">
              <div class="label-with-unit">
                <span class="lbl">P2 阀后压力</span>
                <el-select v-model="caseUnits.p2" size="small" class="unit-select">
                  <el-option-group label="公制"><el-option v-for="u in unitsByGroup.pressure?.metric||[]" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" /></el-option-group>
                  <el-option-group label="英制"><el-option v-for="u in unitsByGroup.pressure?.imperial||[]" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" /></el-option-group>
                </el-select>
              </div>
              <el-input-number v-model="curCase.p2" :min="0" :precision="2" size="small" :controls="false" style="flex:1" />
            </div>
            <div class="form-row">
              <label>ΔP 压差</label>
              <span class="delta-val">{{ deltaP != null ? deltaP.toFixed(2) : '—' }}</span>
              <span class="unit-badge">kPa</span>
            </div>
            <div class="form-row">
              <div class="label-with-unit">
                <span class="lbl">T1 阀前温度</span>
                <el-select v-model="caseUnits.t1" size="small" class="unit-select">
                  <el-option-group label="公制"><el-option v-for="u in unitsByGroup.temperature?.metric||[]" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" /></el-option-group>
                  <el-option-group label="英制"><el-option v-for="u in unitsByGroup.temperature?.imperial||[]" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" /></el-option-group>
                </el-select>
              </div>
              <el-input-number v-model="curCase.t1" :precision="1" size="small" :controls="false" style="flex:1" />
            </div>
            <div class="form-row">
              <div class="label-with-unit">
                <span class="lbl">流量</span>
                <el-select v-model="caseUnits.flow" size="small" class="unit-select">
                  <el-option-group label="质量流量"><el-option v-for="u in unitsByGroup.mass_flow?.metric||[]" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" /></el-option-group>
                  <el-option-group label="体积流量(液)"><el-option v-for="u in unitsByGroup.vol_flow_liquid?.metric||[]" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" /></el-option-group>
                  <el-option-group label="体积流量(气标况)"><el-option v-for="u in unitsByGroup.vol_flow_gas?.metric||[]" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" /></el-option-group>
                </el-select>
              </div>
              <el-input-number v-model="curCase.flow_rate" :min="0" :precision="2" size="small" :controls="false" style="flex:1" />
            </div>
            <div class="form-row">
              <div class="label-with-unit">
                <span class="lbl">管道尺寸</span>
                <el-select v-model="caseUnits.pipe_size" size="small" class="unit-select">
                  <el-option-group label="公制"><el-option v-for="u in unitsByGroup.diameter?.metric||[]" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" /></el-option-group>
                  <el-option-group label="英制"><el-option v-for="u in unitsByGroup.diameter?.imperial||[]" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" /></el-option-group>
                </el-select>
              </div>
              <el-input-number v-model="curCase.pipe_size" :min="0" :precision="1" size="small" :controls="false" style="flex:1" />
            </div>
          </div>
        </div>

        <!-- 卡片 3：阀门动作与泄漏（位号级） -->
        <div class="section-card">
          <div class="section-title">
            阀门动作与泄漏
            <el-tag size="small" type="info" class="title-tag">位号级</el-tag>
          </div>
          <div class="form-grid">
            <div class="form-row full-width">
              <label>阀门动作</label>
              <el-radio-group v-model="form.valve_action" size="small">
                <el-radio-button value="modulating">调节</el-radio-button>
                <el-radio-button value="on_off">开关</el-radio-button>
              </el-radio-group>
            </div>
            <div class="form-row">
              <label>泄漏等级</label>
              <el-select v-model="form.leakage_class" size="small" placeholder="选择" style="width:100%">
                <el-option label="IV" value="IV" /><el-option label="V" value="V" /><el-option label="VI" value="VI" />
              </el-select>
            </div>
            <div class="form-row">
              <label>可调比要求</label>
              <el-input-number v-model="form.rangeability_required" :min="10" :max="200" :step="5" size="small" :controls="false" style="width:100%" />
            </div>
            <div class="form-row full-width">
              <label>已知 Cv (可选)</label>
              <el-input-number v-model="form.cv_required" :min="0" :precision="2" size="small" :controls="false" style="width:100%" placeholder="填写后跳过 Cv 反算" />
            </div>
          </div>
        </div>

        <!-- 卡片 4：特殊要求（位号级） -->
        <div class="section-card">
          <div class="section-title">
            特殊要求
            <el-tag size="small" type="info" class="title-tag">位号级</el-tag>
          </div>
          <div class="form-grid">
            <div class="form-row full-width">
              <el-checkbox v-model="form.special.nace" size="small">NACE MR0175</el-checkbox>
              <el-checkbox v-model="form.special.fire_safe" size="small">防火安全</el-checkbox>
              <el-checkbox v-model="form.special.copper_free" size="small">禁铜</el-checkbox>
              <el-checkbox v-model="form.special.low_temp" size="small">低温 (&lt;-45℃)</el-checkbox>
              <el-checkbox v-model="form.special.high_temp" size="small">高温 (&gt;230℃)</el-checkbox>
            </div>
            <div class="form-row">
              <label>阀体材质</label>
              <el-select v-model="form.special.body_material" size="small" filterable clearable placeholder="选择" style="width:100%">
                <el-option v-for="m in BODY_MATERIALS" :key="m" :label="m" :value="m" />
              </el-select>
            </div>
            <div class="form-row">
              <label>压力等级</label>
              <el-select v-model="form.special.pressure_class" size="small" filterable clearable placeholder="选择" style="width:100%">
                <el-option v-for="p in PRESSURE_CLASSES" :key="p" :label="p" :value="p" />
              </el-select>
            </div>
          </div>
        </div>
      </div>

      <!-- 右栏：候选清单 -->
      <div class="col-result">
        <!-- 概览条 -->
        <div class="section-card" v-if="candidates.length || ran">
          <div class="summary-bar">
            <span>共 <b>{{ candidates.length }}</b> 个候选 · 命中 <b>{{ appliedRuleCount }}</b> 条规则</span>
            <div class="summary-badges">
              <span class="badge">P1={{ cases[0].p1 ?? '—' }}kPa</span>
              <span class="badge">Q={{ cases[0].flow_rate ?? '—' }}{{ caseUnits.flow }}</span>
              <span class="badge">T={{ cases[0].t1 ?? '—' }}℃</span>
            </div>
            <el-tag v-if="mainFlowRegime" :type="regimeTagType(mainFlowRegime)" size="small">{{ mainFlowRegime }}</el-tag>
          </div>
        </div>

        <!-- 候选清单表 -->
        <div class="section-card">
          <div class="section-title">
            候选清单
            <div class="title-actions">
              <el-button size="small" text type="primary" @click="sortBy='score'">按评分</el-button>
              <el-button size="small" text type="primary" @click="sortBy='opening'">按开度</el-button>
              <el-button size="small" text type="primary" @click="sortBy='rank'">按排名</el-button>
            </div>
          </div>
          <div v-if="!candidates.length" class="empty-hint">
            <el-icon :size="48" color="#c0c4cc"><Aim /></el-icon>
            <span>{{ ran ? '无满足条件的阀型，请检查工艺条件或查看警告' : '请录入工艺条件后点击「运行选型」' }}</span>
          </div>
          <el-table v-else :data="sortedCandidates" border size="small" style="width:100%" :row-key="r => r.rank">
            <el-table-column type="expand">
              <template #default="{ row }">
                <div class="candidate-detail-grid">
                  <div class="metric">
                    <div class="label">评分构成</div>
                    <div class="value">{{ scoreFormula(row) }}</div>
                  </div>
                  <div class="metric">
                    <div class="label">命中规则 ({{ row.applied_rules?.length || 0 }})</div>
                    <div class="value rules-list">
                      <el-tag v-for="r in row.applied_rules||[]" :key="r" size="small" effect="plain" style="margin:2px 4px 2px 0">{{ r }}</el-tag>
                    </div>
                  </div>
                  <div class="metric">
                    <div class="label">关键约束</div>
                    <div class="value">{{ keyConstraints(row) }}</div>
                  </div>
                  <div class="metric">
                    <div class="label">物理量</div>
                    <div class="value physical">
                      <div v-if="row.flags?.fd_mode">fd_mode: {{ row.flags.fd_mode }}</div>
                      <div v-if="row.flags?.stroke_mode">stroke_mode: {{ row.flags.stroke_mode }}</div>
                      <div v-if="row.flags?.flow_regime">flow_regime: {{ row.flags.flow_regime }}</div>
                    </div>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="Rank" width="70" align="center">
              <template #default="{ row }">
                <span class="rank-badge" :class="rankClass(row.rank)">#{{ row.rank }}</span>
              </template>
            </el-table-column>
            <el-table-column label="系列" width="140">
              <template #default="{ row }">
                <div class="series-cell">
                  <div class="series-code">{{ row.series_code }}</div>
                  <div class="series-name">{{ row.series_name }}</div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="口径/阀芯" width="110" align="center">
              <template #default="{ row }">{{ row.dn_label }} / {{ row.trim_label }}</template>
            </el-table-column>
            <el-table-column label="流量特性" width="100" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="flowCharTagType(row.flow_char)">{{ row.flow_char }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="额定 Cv" width="90" align="right" prop="rated_cv">
              <template #default="{ row }"><span class="cv-rated">{{ row.rated_cv ?? '—' }}</span></template>
            </el-table-column>
            <el-table-column label="最小 Cv" width="90" align="right">
              <template #default="{ row }">
                <span v-if="row.cv_min != null">{{ row.cv_min }}</span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="开度" width="150" align="center">
              <template #default="{ row }">
                <div v-if="row.opening != null" class="opening-cell">
                  <el-progress :percentage="row.opening" :stroke-width="10" :color="openingColor(row.opening)" :show-text="false" style="flex:1" />
                  <span class="opening-text">{{ row.opening.toFixed(1) }}%</span>
                </div>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="可调比" width="90" align="right">
              <template #default="{ row }">
                <span v-if="row.rangeability != null">
                  {{ row.rangeability }}
                  <span v-if="form.rangeability_required" :style="{color: row.rangeability >= form.rangeability_required ? '#67c23a' : '#f56c6c'}">
                    {{ row.rangeability >= form.rangeability_required ? '✓' : '✗' }}
                  </span>
                </span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="评分" width="90" align="center">
              <template #default="{ row }">
                <span class="score-stars">{{ scoreStars(row.score) }}</span>
                <div class="muted" style="font-size:11px">{{ row.score }}</div>
              </template>
            </el-table-column>
            <el-table-column label="flags" min-width="120">
              <template #default="{ row }">
                <el-tag v-if="row.flags?.fd_mode" size="small" type="info" effect="plain" style="margin-right:4px">Fd:{{ row.flags.fd_mode }}</el-tag>
                <el-tag v-if="row.flags?.flow_regime" size="small" :type="regimeTagType(row.flags.flow_regime)" effect="plain" style="margin-right:4px">{{ row.flags.flow_regime }}</el-tag>
                <el-tag v-if="row.flags?.no_cv_min" size="small" type="warning" effect="plain">缺cv_min</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center" fixed="right">
              <template #default="{ row }">
                <el-button link size="small" type="primary" @click="applyCandidate(row)">应用</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 警告列表 -->
        <div class="section-card" v-if="warnings.length">
          <div class="section-title">警告与提示</div>
          <div class="warnings-list">
            <div v-for="(w, i) in warnings" :key="i" class="warning-item" :class="warningLevel(w)">{{ w }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="calc-header">
      <div class="header-left">
        <el-button size="small" @click="saveRecord" :disabled="!candidates.length" plain>
          <el-icon><Document /></el-icon>保存记录
        </el-button>
        <el-button type="success" size="small" @click="applyTop1" :disabled="!candidates.length">
          <el-icon><Top /></el-icon>应用 Top1 并跳转精细计算
        </el-button>
        <el-button type="primary" size="small" @click="applySelected" :disabled="!selectedRow">
          <el-icon><Check /></el-icon>应用选中项
        </el-button>
      </div>
      <div class="header-right">
        <el-button size="small" text @click="reset">
          <el-icon><RefreshLeft /></el-icon>清空
        </el-button>
      </div>
    </div>

    <!-- 历史记录抽屉 -->
    <el-drawer v-model="historyDrawer" :title="`位号 ${valve?.tag_no || valveId || ''} 的选型历史`" size="600px" direction="rtl">
      <el-table :data="historyRecords" border size="small" v-loading="historyLoading">
        <el-table-column label="时间" prop="created_at" width="130">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作人" prop="created_by" width="70">
          <template #default="{ row }">{{ row.created_by || '工程师' }}</template>
        </el-table-column>
        <el-table-column label="Top1 候选" width="130">
          <template #default="{ row }">
            <div v-if="row.selected_series" class="series-cell">
              <div class="series-code">{{ row.selected_series }}</div>
              <div class="series-name">{{ row.selected_config?.dn_label || '' }}</div>
            </div>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="候选数" width="70" align="center">
          <template #default="{ row }">{{ row.candidates_json?.length || 0 }}</template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.selected_series ? 'success' : 'info'">{{ row.selected_series ? '已应用' : '未应用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" align="center">
          <template #default="{ row }">
            <el-button link size="small" type="primary" @click="viewSnapshot(row)">查看</el-button>
            <el-button link size="small" type="warning" @click="fillFromSnapshot(row)">回填</el-button>
          </template>
        </el-table-column>
        <template #empty><span class="muted">暂无选型历史</span></template>
      </el-table>

      <!-- 快照详情子抽屉 -->
      <el-drawer v-model="snapshotDrawer" title="快照详情" size="500px" append-to-body>
        <div v-if="currentSnapshot" class="snapshot-detail">
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="时间">{{ formatTime(currentSnapshot.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="操作人">{{ currentSnapshot.created_by || '工程师' }}</el-descriptions-item>
          </el-descriptions>
          <h4>输入快照</h4>
          <pre class="json-view">{{ JSON.stringify(currentSnapshot.input_snapshot, null, 2) }}</pre>
          <h4>候选 Top5</h4>
          <el-table :data="(currentSnapshot.candidates_json||[]).slice(0,5)" border size="small">
            <el-table-column label="Rank" prop="rank" width="60" align="center" />
            <el-table-column label="系列" prop="series_code" width="90" />
            <el-table-column label="口径/阀芯" width="100">
              <template #default="{ row }">{{ row.dn_label }}/{{ row.trim_label }}</template>
            </el-table-column>
            <el-table-column label="评分" prop="score" width="70" align="center" />
          </el-table>
          <h4>命中规则</h4>
          <div class="rules-list">
            <el-tag v-for="r in (currentSnapshot.applied_rule_ids||'').split(',').filter(Boolean)" :key="r" size="small" effect="plain" style="margin:2px 4px 2px 0">{{ r }}</el-tag>
          </div>
        </div>
      </el-drawer>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { projectsApi, valvesApi, fluidsApi, unitsApi, calcApi } from '@/api'
import { selectionApi } from '@/api/selection'

const route = useRoute()
const router = useRouter()

const MAX_CASES = 5
const BODY_MATERIALS = ['A216-WCB', 'A352-LCB', 'A351-CF8', 'A351-CF8M', 'ZG230-450', '304', '316', '316L']
const PRESSURE_CLASSES = ['150#', '300#', '600#', '900#', '1500#', '2500#', 'PN16', 'PN25', 'PN40', 'PN63', 'PN100']

// ---- 上下文 ----
const isValveContext = computed(() => !!(route.params.pid && route.params.vid))
const projectId = ref(route.params.pid ? Number(route.params.pid) : null)
const valveId = ref(route.params.vid ? Number(route.params.vid) : null)
const valve = ref(null)
const projects = ref([])
const valves = ref([])

// ---- 表单数据 ----
const defaultCase = () => ({
  fluid_id: null, fluid_name: null, media: 'liquid', flow_regime: null,
  p1: null, p2: null, t1: null, flow_rate: null, flow_rate_unit: null, pipe_size: null,
})
const cases = ref([defaultCase()])
const activeCaseIdx = ref(0)
const curCase = computed(() => cases.value[activeCaseIdx.value])

const form = ref({
  valve_action: 'modulating', leakage_class: null, rangeability_required: null, cv_required: null,
  special: { nace: false, fire_safe: false, copper_free: false, low_temp: false, high_temp: false, body_material: null, pressure_class: null },
})

const caseUnits = ref({ p1: 'kPa', p2: 'kPa', t1: '℃', flow: 'kg/h', pipe_size: 'mm' })

// ---- 结果数据 ----
const candidates = ref([])
const appliedRuleCount = ref(0)
const warnings = ref([])
const running = ref(false)
const ran = ref(false)
const selectedRow = ref(null)
const sortBy = ref('rank')
const historyDrawer = ref(false)
const snapshotDrawer = ref(false)
const historyRecords = ref([])
const historyLoading = ref(false)
const currentSnapshot = ref(null)

// ---- 选项数据 ----
const fluids = ref([])
const unitsByGroup = ref({})

// ---- 计算属性 ----
function convUnit(val, code, cat) {
  if (val == null) return null
  const u = (unitsByGroup.value[cat]?.all || []).find(x => x.unit_code === code)
  return u ? val * u.factor + (u.offset || 0) : val
}

const deltaP = computed(() => {
  const c = curCase.value
  if (c.p1 == null || c.p2 == null) return null
  return convUnit(c.p1, caseUnits.value.p1, 'pressure') - convUnit(c.p2, caseUnits.value.p2, 'pressure')
})

const canRun = computed(() => {
  const c = cases.value[0]
  return !!(valveId.value && (c.fluid_id || c.fluid_name) && c.flow_rate > 0 && c.p1 != null && c.p2 != null && c.t1 != null && c.p1 > c.p2)
})

const mainFlowRegime = computed(() => candidates.value[0]?.flags?.flow_regime || null)

const sortedCandidates = computed(() => {
  const list = [...candidates.value]
  if (sortBy.value === 'score') list.sort((a, b) => b.score - a.score)
  else if (sortBy.value === 'opening') list.sort((a, b) => Math.abs((a.opening||70) - 70) - Math.abs((b.opening||70) - 70))
  else list.sort((a, b) => a.rank - b.rank)
  return list
})

// ---- 数据加载 ----
async function loadProjects() { try { projects.value = await projectsApi.list() } catch (e) { /* ignore */ } }
async function loadValves(pid) { if (!pid) { valves.value = []; return } try { valves.value = await valvesApi.list(pid) } catch (e) { valves.value = [] } }
async function loadValve() {
  if (!projectId.value || !valveId.value) return
  try { valve.value = await valvesApi.get(projectId.value, valveId.value) } catch (e) { /* ignore */ }
}

// 从该位号当前计算版本加载工况数据 (与计算页保持一致)
async function loadValveCases() {
  if (!valveId.value) return
  try {
    const list = await calcApi.list(valveId.value)
    if (!Array.isArray(list) || !list.length) return
    const cur = list.find(c => c.is_current) || list[0]
    const data = await calcApi.get(valveId.value, cur.id)
    const src = data?.cases || []
    if (!src.length) return
    cases.value = src.slice(0, MAX_CASES).map(mapCaseFromCalc)
    activeCaseIdx.value = 0
    applyCaseUnits(src[0])
  } catch (e) { /* ignore */ }
}

// 计算工况 → 选型工况字段映射
function mapCaseFromCalc(c) {
  const isVol = c.flow_unit === 'vol'
  const fid = c.fluid_id ?? null
  const f = fid ? fluids.value.find(x => x.id === fid) : null
  return {
    fluid_id: fid,
    fluid_name: c.fluid_name_custom || f?.fluid_name || null,
    media: c.fluid_state_override || f?.default_state || 'liquid',
    flow_regime: null,
    p1: c.p1 ?? null,
    p2: c.p2 ?? null,
    t1: c.t1 ?? null,
    flow_rate: (isVol ? c.flow_vol : c.flow_mass) ?? null,
    flow_rate_unit: isVol ? (c.flow_vol_unit || null) : (c.flow_mass_unit || null),
    pipe_size: c.pipe_diameter ?? null,
  }
}

// 把计算工况保存的单位同步到选型的公共单位选择器
function applyCaseUnits(c0) {
  if (!c0) return
  if (c0.p1_unit) caseUnits.value.p1 = c0.p1_unit
  if (c0.p2_unit) caseUnits.value.p2 = c0.p2_unit
  if (c0.t1_unit) caseUnits.value.t1 = c0.t1_unit
  if (c0.flow_unit === 'vol' && c0.flow_vol_unit) caseUnits.value.flow = c0.flow_vol_unit
  else if (c0.flow_mass_unit) caseUnits.value.flow = c0.flow_mass_unit
  if (c0.pipe_diameter_unit) caseUnits.value.pipe_size = c0.pipe_diameter_unit
}
async function loadFluids() { try { fluids.value = await fluidsApi.list() } catch (e) { /* ignore */ } }
async function loadUnits() {
  try {
    const res = await unitsApi.list()
    const cats = res?.categories || {}
    const groups = {}
    for (const [cat, items] of Object.entries(cats)) {
      groups[cat] = {
        all: items,
        metric: items.filter(u => (u.unit_group || 'metric') === 'metric'),
        imperial: items.filter(u => u.unit_group === 'imperial'),
      }
    }
    unitsByGroup.value = groups
    const d = res?.defaults || {}
    caseUnits.value = {
      p1: d.pressure || 'kPaA', p2: d.pressure || 'kPaA',
      t1: d.temperature || 'C', flow: d.mass_flow || 'kg_h',
      pipe_size: d.diameter || 'mm',
    }
  } catch (e) { /* ignore */ }
}
async function loadHistory() {
  if (!valveId.value) return
  historyLoading.value = true
  try { historyRecords.value = await selectionApi.records(valveId.value) } catch (e) { historyRecords.value = [] } finally { historyLoading.value = false }
}

function onProjectChange(pid) { valveId.value = null; loadValves(pid) }

// ---- 工况 tab ----
function addCase() { if (cases.value.length < MAX_CASES) { cases.value.push({ ...defaultCase(), ...cases.value[0] }); activeCaseIdx.value = cases.value.length - 1 } }
function removeCase(idx) { if (idx === 0) { ElMessage.warning('主工况不可删除'); return } cases.value.splice(idx, 1); if (activeCaseIdx.value >= cases.value.length) activeCaseIdx.value = 0 }
function onCaseTabClick() { /* 切换时无需特殊处理, 字段已通过 computed 联动 */ }

// ---- T1 联动 low_temp / high_temp ----
watch(() => cases.value[0].t1, (t) => {
  if (t == null) return
  if (t < -45) form.value.special.low_temp = true
  if (t > 230) form.value.special.high_temp = true
})

// ---- 运行选型 ----
async function runSelection() {
  if (!canRun.value) { ElMessage.warning('请完整填写主工况必填项（介质/流量/P1/P2/T1）'); return }
  running.value = true
  try {
    const main = cases.value[0]
    const fluid = fluids.value.find(f => f.id === main.fluid_id)
    const input = {
      project_id: projectId.value,
      valve_id: valveId.value,
      media: main.media,
      fluid_name: fluid?.fluid_name || main.fluid_name || null,
      flow_rate: main.flow_rate,
      flow_rate_unit: caseUnits.value.flow,
      p1: main.p1, p1_unit: caseUnits.value.p1,
      p2: main.p2, p2_unit: caseUnits.value.p2,
      dp: convUnit(main.p1, caseUnits.value.p1, 'pressure') != null
        ? convUnit(main.p1, caseUnits.value.p1, 'pressure') - convUnit(main.p2, caseUnits.value.p2, 'pressure')
        : null,
      t1: main.t1, t1_unit: caseUnits.value.t1,
      pipe_size: main.pipe_size, pipe_size_unit: caseUnits.value.pipe_size,
      leakage_class: form.value.leakage_class,
      valve_action: form.value.valve_action,
      rangeability_required: form.value.rangeability_required,
      cv_required: form.value.cv_required,
      special_req: { fluid_id: main.fluid_id, ...form.value.special },
    }
    const result = await selectionApi.run(input)
    candidates.value = result.candidates || []
    appliedRuleCount.value = result.applied_rule_count || 0
    warnings.value = result.warnings || []
    ran.value = true
    if (!candidates.value.length) ElMessage.info('无满足条件的阀型')
  } catch (e) {
    ElMessage.error(e.message || '选型运行失败')
  } finally { running.value = false }
}

// ---- 保存记录 ----
async function saveRecord() {
  if (!candidates.value.length) return
  try {
    const main = cases.value[0]
    const payload = {
      valve_id: valveId.value, project_id: projectId.value,
      input_snapshot: { main, cases: cases.value, form: form.value, units: caseUnits.value },
      candidates_json: candidates.value,
      applied_rule_ids: collectRuleIds(),
    }
    await selectionApi.createRecord(payload)
    ElMessage.success('已保存到历史记录')
    loadHistory()
  } catch (e) { ElMessage.error(e.message || '保存失败') }
}

function collectRuleIds() {
  const s = new Set()
  candidates.value.forEach(c => (c.applied_rules||[]).forEach(r => s.add(r)))
  return Array.from(s).join(',')
}

// ---- 应用并跳转 ----
async function applyTop1() { if (candidates.value.length) applyCandidate(candidates.value[0]) }
async function applySelected() { if (selectedRow.value) applyCandidate(selectedRow.value); else ElMessage.warning('请先点击表格行选中候选') }

async function applyCandidate(row) {
  try {
    if (valve.value?.valve_type) {
      await ElMessageBox.confirm('当前位号已有手工配置，应用选型将覆盖阀门配置与工况 1，是否继续？', '确认应用', { type: 'warning' })
    }
  } catch { return }
  try {
    const rec = await selectionApi.createRecord({
      valve_id: valveId.value, project_id: projectId.value,
      input_snapshot: { main: cases.value[0], cases: cases.value, form: form.value, units: caseUnits.value },
      candidates_json: candidates.value,
      selected_series: row.series_code,
      selected_config: row,
      applied_rule_ids: collectRuleIds(),
    })
    await selectionApi.apply(rec.id, { selected_series: row.series_code, selected_config: row })
    ElMessage.success('已应用并跳转精细计算')
    router.push({ path: `/projects/${projectId.value}/valves/${valveId.value}`, query: { from: 'selection', record_id: rec.id } })
  } catch (e) { ElMessage.error(e.message || '应用失败') }
}

// ---- 历史记录 ----
function viewSnapshot(row) { currentSnapshot.value = row; snapshotDrawer.value = true }
async function fillFromSnapshot(row) {
  try { await ElMessageBox.confirm('回填将覆盖当前录入的工艺条件，是否继续？', '确认回填', { type: 'warning' }) } catch { return }
  const snap = row.input_snapshot
  if (snap?.main) {
    cases.value[0] = { ...defaultCase(), ...snap.main }
    if (snap.cases?.length) cases.value = snap.cases.map((c, i) => i === 0 ? cases.value[0] : { ...defaultCase(), ...c })
    if (snap.form) form.value = { ...form.value, ...snap.form }
    if (snap.units) caseUnits.value = { ...caseUnits.value, ...snap.units }
    activeCaseIdx.value = 0
  }
  historyDrawer.value = false
  ElMessage.success('已回填，请确认后点击「运行选型」')
}

// ---- 渲染辅助 ----
function rankClass(r) { return r === 1 ? 'r1' : r === 2 ? 'r2' : r === 3 ? 'r3' : 'rn' }
function flowCharTagType(fc) {
  if (!fc) return 'info'
  if (fc.includes('EQ')) return 'primary'
  if (fc.toLowerCase().includes('linear')) return 'success'
  return 'info'
}
function regimeTagType(r) {
  if (r === 'choked') return 'warning'
  if (r === 'cavitation' || r === 'flash') return 'danger'
  return 'success'
}
function openingColor(o) {
  if (o == null) return '#909399'
  if (o >= 60 && o <= 80) return '#1a73e8'
  if (o >= 20 && o <= 90) return '#67c23a'
  return '#f56c6c'
}
function scoreStars(s) { return s >= 80 ? '★★★' : s >= 50 ? '★★' : '★' }
function warningLevel(w) {
  if (/排除|最小|不满足/.test(w)) return 'danger'
  if (/超过|缺少|未知/.test(w)) return 'warn'
  return 'info'
}
function scoreFormula(row) {
  const boost = (row.applied_rules||[]).length * 30   // mock 估算
  return `基础 0 + boost ${row.score > 0 ? row.score : 0} - penalty 0 = ${row.score}`
}
function keyConstraints(row) {
  const map = {
    GC120: '最小口径 DN40', GC210: '最小口径 DN25 / 空化优先',
    GV120: 'Large Cv P-port', BT210: '蝶阀 60°/90°',
  }
  return map[row.series_code] || '—'
}
function formatTime(t) { if (!t) return '—'; try { return new Date(t).toLocaleString('zh-CN', { hour12: false }) } catch { return t } }

function reset() {
  cases.value = [defaultCase()]
  form.value = { valve_action: 'modulating', leakage_class: null, rangeability_required: null, cv_required: null, special: { nace: false, fire_safe: false, copper_free: false, low_temp: false, high_temp: false, body_material: null, pressure_class: null } }
  candidates.value = []; warnings.value = []; ran.value = false; activeCaseIdx.value = 0; selectedRow.value = null
}

// ---- 初始化 ----
onMounted(async () => {
  await Promise.all([loadProjects(), loadFluids(), loadUnits()])
  if (projectId.value) await loadValves(projectId.value)
  if (isValveContext.value) {
    await loadValve()
    await loadValveCases()
  }
  if (valveId.value) loadHistory()
})

// 切换位号后重新加载阀门信息、工况数据与选型历史
watch(valveId, async (vid) => {
  if (!vid) { valve.value = null; return }
  await loadValve()
  await loadValveCases()
  loadHistory()
})
watch(historyDrawer, (v) => { if (v) loadHistory() })
</script>

<style scoped>
.selection-page { display: flex; flex-direction: column; height: 100%; gap: 12px; }
.calc-header { display: flex; align-items: center; justify-content: space-between; background: #fff; border-radius: 6px; padding: 10px 16px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.header-left { display: flex; align-items: center; gap: 10px; }
.header-right { display: flex; align-items: center; gap: 8px; }
.tag-tag { font-weight: 700; letter-spacing: 0.5px; }
.valve-name { font-size: 16px; font-weight: 600; }
.muted { color: #909399; font-size: 12px; }

.calc-body { flex: 1; display: grid; grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr); gap: 12px; overflow: hidden; }
.col-form, .col-result { overflow-y: auto; display: flex; flex-direction: column; gap: 12px; padding-right: 4px; }

.section-card { background: #fff; border-radius: 6px; padding: 14px 18px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
.section-title { font-size: 14px; font-weight: 600; margin: 0 0 12px; color: #303133; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid #ebeef5; padding-bottom: 8px; }
.title-actions { margin-left: auto; display: flex; gap: 6px; }
.title-tag { margin-left: auto; }
.empty-hint { text-align: center; padding: 30px 0; color: #909399; display: flex; flex-direction: column; gap: 10px; align-items: center; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 20px; }
.form-grid .form-row.full-width { grid-column: 1 / -1; }
.form-col { display: flex; flex-direction: column; gap: 8px; }
.form-row { display: flex; align-items: center; gap: 10px; }
.form-row label { min-width: 110px; font-size: 12px; color: #606266; text-align: right; flex-shrink: 0; }
.unit-badge { font-size: 11px; color: #909399; margin-left: 4px; }
.delta-val { flex: 1; text-align: center; background: #f0f9ff; color: #409eff; font-weight: 600; padding: 4px 8px; border-radius: 3px; }

.label-with-unit { display: flex; flex-direction: row; align-items: center; justify-content: flex-end; gap: 4px; min-width: 200px; }
.label-with-unit .lbl { font-size: 12px; flex: 0 0 auto; margin-right: auto; color: #606266; }
.label-with-unit .unit-select { width: 84px !important; flex-shrink: 0; }

.case-tabs { margin-bottom: 8px; }
.case-tabs :deep(.el-tabs__header) { margin-bottom: 0; }
.case-tabs :deep(.el-tabs__item) { font-size: 12px; }
.case-tabs :deep(.el-tabs__item.is-active) { font-weight: 600; }
.case-tab-footer { display: flex; align-items: center; gap: 10px; margin-top: 8px; padding-top: 8px; border-top: 1px dashed #ebeef5; }

.summary-bar { display: flex; align-items: center; gap: 12px; font-size: 13px; }
.summary-badges { display: flex; gap: 8px; align-items: center; font-size: 12px; color: #606266; margin-left: auto; }
.summary-badges .badge { padding: 2px 8px; background: #f0f9ff; border-radius: 3px; }

.rank-badge { width: 28px; height: 28px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; color: #fff; }
.rank-badge.r1 { background: #f5a623; }
.rank-badge.r2 { background: #9b9b9b; }
.rank-badge.r3 { background: #b87333; }
.rank-badge.rn { background: #f4f4f5; color: #606266; }

.series-cell .series-code { font-weight: 700; font-size: 13px; color: #303133; }
.series-cell .series-name { font-size: 11px; color: #909399; }

.cv-rated { color: #f56c6c; font-weight: 700; }
.opening-cell { display: flex; align-items: center; gap: 6px; }
.opening-cell .opening-text { min-width: 44px; font-size: 12px; font-weight: 600; text-align: right; }
.score-stars { color: #f5a623; font-size: 14px; letter-spacing: 1px; }

.candidate-detail-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px 12px; padding: 12px; background: #fafbfc; border-radius: 4px; }
.candidate-detail-grid .rules-list { display: flex; flex-wrap: wrap; }
.candidate-detail-grid .physical { font-size: 12px; line-height: 1.8; }

.warnings-list { display: flex; flex-direction: column; gap: 6px; }
.warning-item { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 4px; font-size: 13px; }
.warning-item.danger { background: #fef0f0; color: #f56c6c; border-left: 3px solid #f56c6c; }
.warning-item.warn { background: #fdf6ec; color: #e6a23c; border-left: 3px solid #e6a23c; }
.warning-item.info { background: #f4f4f5; color: #909399; border-left: 3px solid #909399; }

.snapshot-detail h4 { margin: 16px 0 8px; font-size: 13px; color: #303133; }
.json-view { background: #f5f7fa; padding: 10px; border-radius: 4px; font-size: 11px; max-height: 200px; overflow: auto; }

.col-form::-webkit-scrollbar, .col-result::-webkit-scrollbar { width: 8px; }
.col-form::-webkit-scrollbar-thumb, .col-result::-webkit-scrollbar-thumb { background: #dcdfe6; border-radius: 4px; }
.col-form::-webkit-scrollbar-track, .col-result::-webkit-scrollbar-track { background: transparent; }
</style>
