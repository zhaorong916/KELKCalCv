/**
 * 选型模块 API 封装
 * 依据: docs/选型模块前端界面设计.md §11
 *
 * 后端 /api/v1/selection/* 路由在 P3.1~3.2 实现。
 * 当前阶段后端未就绪时, 自动降级为 mock 数据, 便于前端独立调试。
 */
import { http } from './index'

// 后端 selection 路由是否就绪(就绪后置 false)
const USE_MOCK = false

// ---------------------------------------------------------------------------
// Mock 数据(供前端独立调试, 与 CandidateOut schema 完全对齐)
// ---------------------------------------------------------------------------
const MOCK_CANDIDATES = [
  {
    rank: 1, series_code: 'GC210', series_name: '多孔套筒调节阀',
    dn_label: '100A', trim_label: '80A', flow_char: 'EQ%',
    rated_cv: 100, cv_min: 1.6, opening: 72.5, rangeability: 62.5, score: 95,
    applied_rules: ['R-SCOPE-001', 'R-CON-GC210-001', 'R-PRE-GC210-001'],
    flags: { fd_mode: 'gc210_eqn', flow_regime: 'cavitation', stroke_mode: 'eq_index' },
    actuator_recommend: null,
  },
  {
    rank: 2, series_code: 'GC120', series_name: '套筒调节阀',
    dn_label: '100A', trim_label: '80A', flow_char: 'EQ%',
    rated_cv: 120, cv_min: 2.4, opening: 58.3, rangeability: 50.0, score: 78,
    applied_rules: ['R-SCOPE-001', 'R-CON-GC120-001'],
    flags: { fd_mode: 'eqn', stroke_mode: 'eq_index' },
    actuator_recommend: null,
  },
  {
    rank: 3, series_code: 'GV120', series_name: '直通单座调节阀',
    dn_label: '80A', trim_label: '65A', flow_char: 'Linear',
    rated_cv: 95, cv_min: 1.9, opening: 76.8, rangeability: 50.0, score: 72,
    applied_rules: ['R-SCOPE-001', 'R-CON-GV120-001'],
    flags: { fd_mode: 'eqn', stroke_mode: 'linear' },
    actuator_recommend: null,
  },
  {
    rank: 4, series_code: 'BT210', series_name: '蝶阀',
    dn_label: '150A', trim_label: '150A', flow_char: 'EQ%',
    rated_cv: 320, cv_min: null, opening: 18.5, rangeability: null, score: 45,
    applied_rules: ['R-SCOPE-001'],
    flags: { stroke_mode: 'poly_cv_div_angle', no_cv_min: true },
    actuator_recommend: null,
  },
]

const MOCK_WARNINGS = [
  'GC120 最小口径 DN40，当前 DN25 已排除',
  'BT210 缺少 cv_min 数据，可调比未知',
  '未匹配到介质物性，采用通用兜底',
]

// 模拟网络延迟
const delay = (ms = 300) => new Promise(r => setTimeout(r, ms))

// ---------------------------------------------------------------------------
// API 封装
// ---------------------------------------------------------------------------
export const selectionApi = {
  /** 运行选型 */
  run: async (input) => {
    if (USE_MOCK) {
      await delay(600)
      // 简单根据 cv_required 调整 opening, 模拟真实引擎行为
      const list = MOCK_CANDIDATES.map(c => ({ ...c }))
      return {
        candidates: list,
        applied_rule_count: 12,
        warnings: [...MOCK_WARNINGS],
      }
    }
    return http.post('/selection/run', input)
  },

  /** 历史记录列表 */
  records: async (vid) => {
    if (USE_MOCK) {
      await delay(200)
      return []
    }
    return http.get('/selection/records', { params: { valve_id: vid } })
  },

  /** 单条记录详情 */
  recordDetail: async (id) => {
    if (USE_MOCK) {
      await delay(200)
      return null
    }
    return http.get(`/selection/records/${id}`)
  },

  /** 创建记录(保存快照) */
  createRecord: async (d) => {
    if (USE_MOCK) {
      await delay(200)
      return { id: Date.now(), ...d, created_at: new Date().toISOString(), created_by: '工程师' }
    }
    return http.post('/selection/records', d)
  },

  /** 应用记录(回填 ValveConfig + ProcessCase) */
  apply: async (id, payload) => {
    if (USE_MOCK) {
      await delay(400)
      return { ok: true, id, ...payload }
    }
    return http.post(`/selection/records/${id}/apply`, payload)
  },

  /** 规则库列表(只读) */
  rules: async (params) => {
    if (USE_MOCK) {
      await delay(200)
      return MOCK_RULES
    }
    return http.get('/selection/rules', { params })
  },
}

// ---------------------------------------------------------------------------
// Mock 规则库(供 SelectionRules.vue 调试)
// ---------------------------------------------------------------------------
const MOCK_RULES = [
  { id: 1, rule_code: 'R-SCOPE-001', rule_name: '调节阀适用范围', category: 'scope', target_series: '*', condition_op: 'and', action: 'require', action_payload: {}, priority: 10, source_ref: '选型思路.pdf:p2', is_active: true, condition_expr: { valve_action: 'modulating' }, created_at: '2026-10-15 10:00', updated_at: '2026-10-15 10:00' },
  { id: 2, rule_code: 'R-SCOPE-002', rule_name: '开关阀排除调节工况', category: 'scope', target_series: 'BV*', condition_op: 'and', action: 'exclude', action_payload: {}, priority: 10, source_ref: '选型思路.pdf:p3', is_active: true, condition_expr: { valve_action: 'modulating' }, created_at: '2026-10-15 10:00', updated_at: '2026-10-15 10:00' },
  { id: 3, rule_code: 'R-CON-GC120-001', rule_name: 'GC120 最小口径', category: 'constraint', target_series: 'GC120', condition_op: 'and', action: 'require', action_payload: {}, priority: 20, source_ref: 'GC120_210:p4', is_active: true, condition_expr: { pipe_size: { _min: 40 } }, created_at: '2026-10-15 10:00', updated_at: '2026-10-15 10:00' },
  { id: 4, rule_code: 'R-CON-GC210-001', rule_name: 'GC210 最小口径', category: 'constraint', target_series: 'GC210', condition_op: 'and', action: 'require', action_payload: {}, priority: 20, source_ref: 'GC120_210:p5', is_active: true, condition_expr: { pipe_size: { _min: 25 } }, created_at: '2026-10-15 10:00', updated_at: '2026-10-15 10:00' },
  { id: 5, rule_code: 'R-PRE-GC210-001', rule_name: '空化工况 GC210 优先', category: 'preference', target_series: 'GC210', condition_op: 'and', action: 'boost', action_payload: { score: 90 }, priority: 30, source_ref: '选型思路.pdf:p7', is_active: true, condition_expr: { flow_regime: 'cavitation' }, created_at: '2026-10-15 10:00', updated_at: '2026-10-15 10:00' },
  { id: 6, rule_code: 'R-PRE-GC120-001', rule_name: '普通液体 GC120 加权', category: 'preference', target_series: 'GC120', condition_op: 'and', action: 'boost', action_payload: { score: 30 }, priority: 30, source_ref: 'GC120_210:p6', is_active: true, condition_expr: { media: 'liquid' }, created_at: '2026-10-15 10:00', updated_at: '2026-10-15 10:00' },
  { id: 7, rule_code: 'R-POST-001', rule_name: '开度窗口扣分(>90%)', category: 'post_filter', target_series: '*', condition_op: 'and', action: 'penalty', action_payload: { score: 20 }, priority: 40, source_ref: '选型思路.pdf:p9', is_active: true, condition_expr: { opening: { _gt: 90 } }, created_at: '2026-10-15 10:00', updated_at: '2026-10-15 10:00' },
  { id: 8, rule_code: 'R-POST-002', rule_name: 'fd_mode 标记', category: 'post_filter', target_series: 'GC210', condition_op: 'and', action: 'set_field', action_payload: { field: 'fd_mode' }, priority: 40, source_ref: 'GC120_210:p8', is_active: true, condition_expr: {}, created_at: '2026-10-15 10:00', updated_at: '2026-10-15 10:00' },
]
