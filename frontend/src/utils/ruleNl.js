/**
 * 选型规则的中文辅助录入
 *
 * 只负责把中文描述解析成后端规则结构（condition_expr / action / action_payload），
 * 不直接访问接口。条件键与算子白名单与后端 app/calc/selector.py 保持一致：
 *   _NUMERIC_KEYS / _ENUM_KEYS / _BOOL_KEYS / OPS
 */

const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// ---------------------------------------------------------------------------
// 字段词典：数值类（分成「下限键 / 上限键 / 等值键」，按比较方向自动选键）
// ---------------------------------------------------------------------------
const NUM_GROUPS = [
  { label: '设计温度', unit: '℃', low: 'temp_min', high: 'temp_max', eq: 'temp',
    aliases: ['设计温度', '操作温度', '工况温度', '温度', 'temp'] },
  { label: '阀前压力', unit: 'kPa', pressure: true, low: 'p1', high: 'p1_max', eq: 'p1',
    aliases: ['阀前压力', '进口压力', '入口压力', '前压', 'p1'] },
  { label: '压差', unit: 'kPa', pressure: true, low: 'dp', high: 'dp_max', eq: 'dp',
    aliases: ['压差', '差压', '压降', 'dp'] },
  { label: '压差比', unit: '', low: 'dp_ratio', high: 'dp_ratio_max', eq: 'dp_ratio',
    aliases: ['压差比', 'dp比'] },
  { label: '公称通径', unit: 'mm', low: 'pipe_size_min', high: 'pipe_size_max', eq: 'pipe_size',
    aliases: ['公称通径', '管道通径', '管道口径', '通径', '口径', '管径', 'dn'] },
  { label: '所需 Cv', unit: '', low: 'cv_required', high: 'cv_required', eq: 'cv_required',
    aliases: ['所需cv', '需求cv', '计算cv', 'cv需求'] },
  { label: '额定 Cv', unit: '', low: 'cv_min', high: 'cv_max', eq: 'rated_cv',
    aliases: ['额定cv', 'cv额定'] },
  { label: '开度', unit: '%', low: 'opening', high: 'opening', eq: 'opening',
    aliases: ['开度', '阀开度'] },
  { label: '可调比', unit: '', low: 'rangeability_required', high: 'rangeability', eq: 'rangeability',
    aliases: ['可调比'] },
]

// 枚举类（值为数据库真实取值，别名用于中文/缩写识别）
const ENUM_FIELDS = [
  { key: 'media', label: '介质', aliases: ['介质类型', '介质', 'media'],
    values: { liquid: ['液体', '液相', 'liquid'], gas: ['气体', '气相', 'gas'],
              steam: ['蒸汽', '水蒸汽', 'steam'], twophase: ['两相', '两相流'] } },
  { key: 'flow_regime', label: '流态', aliases: ['流动状态', '流态', 'flow_regime'],
    values: { 空化: ['空化', '气蚀'], 闪蒸: ['闪蒸'], 阻塞流: ['阻塞流', '阻塞'], 正常: ['正常'] } },
  { key: 'leakage_class', label: '泄漏等级', aliases: ['泄漏等级', '泄漏级别', '密封等级', 'class等级', 'class'],
    values: { IV: ['iv', 'iv级', '4级', '四级'], V: ['v', 'v级', '5级', '五级'],
              VI: ['vi', 'vi级', '6级', '六级'] } },
  { key: 'valve_action', label: '阀门作用', aliases: ['阀门作用', '故障位置', '作用方式', 'valve_action'],
    values: { FC: ['fc', '气关', '故障关'], FO: ['fo', '气开', '故障开'] } },
  { key: 'series_category', label: '系列类别', aliases: ['系列类别', '产品类别'], values: {} },
  { key: 'series_product_line', label: '产品线', aliases: ['产品线'], values: {} },
]

// 布尔类
const BOOL_FIELDS = [
  { key: 'nace', label: 'NACE 要求', aliases: ['nace', '酸性工况', '酸性介质'] },
  { key: 'fire_safe', label: '防火认证', aliases: ['防火认证', '防火要求', 'fire safe', '防火'] },
  { key: 'copper_free', label: '无铜要求', aliases: ['无铜', '不含铜', 'copper free'] },
  { key: 'low_temp', label: '低温工况', aliases: ['低温工况', '低温'] },
  { key: 'high_temp', label: '高温工况', aliases: ['高温工况', '高温'] },
]

// 算子：中文/符号 → 后端算子（按长度从长到短匹配，保证「不低于」不误判为「低于」）
const OP_LABELS = [
  ['不低于', '_min'], ['不小于', '_min'], ['大于等于', '_min'], ['至少', '_min'], ['>=', '_min'], ['≥', '_min'],
  ['不高于', '_max'], ['不大于', '_max'], ['小于等于', '_max'], ['最多', '_max'], ['<=', '_max'], ['≤', '_max'],
  ['不等于', '_ne'], ['不是', '_ne'], ['不为', '_ne'], ['!=', '_ne'], ['≠', '_ne'],
  ['低于', '_lt'], ['小于', '_lt'], ['不到', '_lt'], ['<', '_lt'],
  ['高于', '_gt'], ['大于', '_gt'], ['超过', '_gt'], ['>', '_gt'],
  ['等于', '_eq'], ['==', '_eq'], ['=', '_eq'], ['为', '_eq'], ['是', '_eq'],
]
const OP_MAP = Object.fromEntries(OP_LABELS)
const OP_PATTERN = OP_LABELS.map(([l]) => esc(l)).sort((a, b) => b.length - a.length).join('|')

export const OP_TEXT = {
  _eq: '=', _ne: '≠', _min: '≥', _max: '≤', _gt: '>', _lt: '<', _or: '属于', _required: '有',
}

export const ACTION_LABELS = {
  exclude: '排除', require: '要求', boost: '加分', penalty: '扣分', set_field: '回填字段', flag: '标记',
}

// 条件键 → 规格（用于校验、格式化、反向解释）
const KEY_SPECS = {}
for (const g of NUM_GROUPS) {
  for (const k of [g.low, g.high, g.eq]) {
    if (k && !KEY_SPECS[k]) KEY_SPECS[k] = { label: g.label, unit: g.unit, numeric: true, pressure: g.pressure }
  }
}
for (const f of ENUM_FIELDS) KEY_SPECS[f.key] = { label: f.label, enumValues: f.values }
for (const b of BOOL_FIELDS) KEY_SPECS[b.key] = { label: b.label, bool: true }

// 条件行编辑器的下拉分组
export const FIELD_OPTIONS = [
  { label: '数值', options: dedupe(NUM_GROUPS.flatMap(g => [g.low, g.high, g.eq]).filter(Boolean)) },
  { label: '枚举', options: ENUM_FIELDS.map(f => f.key) },
  { label: '布尔', options: BOOL_FIELDS.map(b => b.key) },
]

function dedupe(keys) {
  const seen = new Set()
  return keys.filter(k => (seen.has(k) ? false : (seen.add(k), true)))
    .map(k => ({ key: k, label: KEY_SPECS[k].label }))
}

// ---------------------------------------------------------------------------
// 文本归一化
// ---------------------------------------------------------------------------
function normalize(s) {
  return (s || '')
    .replace(/（/g, '(').replace(/）/g, ')')
    .replace(/，/g, ',').replace(/；/g, ';').replace(/：/g, ':')
    .replace(/．/g, '.').replace(/＋/g, '+').replace(/[－—]/g, '-')
    .replace(/\u3000/g, ' ')
    .toLowerCase()
}

// 跳过的连接词（注意不能吞掉「为 / 是」，它们是等值算子）
const SKIP = /^[\s在时时候达到的,、;:(]*/

const NUM_ALIASES = NUM_GROUPS.flatMap(g => g.aliases.map(alias => ({ alias: alias.toLowerCase(), g })))

/**
 * 扫描数值型条件：字段 + 算子 + 数值(+单位)
 * 返回 [{ key, op, value, group, consumedTo }]
 */
function scanNumeric(text) {
  const hits = []
  let from = 0
  while (from < text.length) {
    // 找最靠前的字段别名（同位置取更长的，避免「压差」抢「压差比」）
    let best = null
    for (const item of NUM_ALIASES) {
      const idx = text.indexOf(item.alias, from)
      if (idx < 0) continue
      if (!best || idx < best.idx || (idx === best.idx && item.alias.length > best.alias.length)) {
        best = { idx, alias: item.alias, g: item.g }
      }
    }
    if (!best) break

    const afterAlias = text.slice(best.idx + best.alias.length)
    const rest = afterAlias.replace(SKIP, '')
    const basePos = text.length - afterAlias.length + (afterAlias.length - rest.length)

    // 模式 1：字段 + 算子 + 数值
    const m1 = rest.match(new RegExp(`^(${OP_PATTERN})\\s*(?:达|到)?\\s*([-+]?\\d+(?:\\.\\d+)?)\\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?`))
    // 模式 2：字段 + 数值 + 以上/以下/以内/及以上
    const m2 = rest.match(/^([-+]?\d+(?:\.\d+)?)\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?\s*(及以上|以上|以下|以内)/)
    // 模式 3：字段 + 数值 到 数值（区间）
    const m3 = rest.match(/^在?\s*([-+]?\d+(?:\.\d+)?)\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?\s*(?:到|至|~|-)\s*([-+]?\d+(?:\.\d+)?)\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?/)

    let added = false
    if (m1) {
      const op = OP_MAP[m1[1]]
      const [num] = convertValue(best.g, m1[2], m1[3], hits)
      hits.push({ group: best.g, key: keyFor(best.g, op), op, value: num, pos: best.idx })
      from = basePos + m1[0].length
      added = true
    } else if (m3) {
      const [lo] = convertValue(best.g, m3[1], m3[2], hits)
      const [hi] = convertValue(best.g, m3[3], m3[4], hits)
      hits.push({ group: best.g, key: best.g.low, op: '_min', value: lo, pos: best.idx })
      hits.push({ group: best.g, key: best.g.high, op: '_max', value: hi, pos: best.idx })
      from = basePos + m3[0].length
      added = true
    } else if (m2) {
      const [num] = convertValue(best.g, m2[1], m2[2], hits)
      const upper = ['及以上', '以上'].includes(m2[3])
      const op = upper ? '_min' : '_max'
      hits.push({ group: best.g, key: upper ? best.g.low : best.g.high, op, value: num, pos: best.idx })
      from = basePos + m2[0].length
      added = true
    }
    if (!added) from = best.idx + best.alias.length
  }
  return hits
}

/** 数值 + 单位 → 内部单位；压力类把 MPa/bar 折算为 kPa */
function convertValue(g, numStr, unit, hits) {
  let v = Number(numStr)
  const u = (unit || '').toLowerCase()
  if (g.pressure) {
    if (u === 'mpa') v *= 1000
    else if (u === 'bar') v *= 100
  }
  return [v, u]
}

function keyFor(g, op) {
  if (op === '_lt' || op === '_min') return g.low
  if (op === '_gt' || op === '_max') return g.high
  return g.eq
}

/** 在文本中查找枚举词：纯拉丁短码（IV/V/VI）按词边界匹配，避免 'v' 命中 'iv' */
function findWord(chunk, word) {
  const w = word.toLowerCase()
  if (/^[a-z0-9]+$/.test(w)) {
    return chunk.search(new RegExp(`(?:^|[^a-z0-9])${esc(w)}(?:$|[^a-z0-9])`))
  }
  return chunk.indexOf(w)
}

/** 扫描枚举型条件（支持「或」多值 → _or） */
function scanEnum(text, skipKeys = new Set()) {
  const hits = []
  for (const f of ENUM_FIELDS) {
    if (skipKeys.has(f.key)) continue
    const alias = f.aliases.map(a => a.toLowerCase()).find(a => text.includes(a))
    if (!alias) continue
    const idx = text.indexOf(alias)
    const rest = text.slice(idx + alias.length).replace(SKIP, '')
    const opm = rest.match(new RegExp(`^(${OP_PATTERN})`))
    const after = opm ? rest.slice(opm[0].length) : rest
    const chunk = after.slice(0, 20).toLowerCase()

    const found = []
    for (const [val, words] of Object.entries(f.values || {})) {
      for (const w of words) {
        const p = findWord(chunk, w)
        if (p >= 0) { found.push({ val, p }); break }
      }
    }
    if (!found.length) continue
    found.sort((a, b) => a.p - b.p)
    const vals = found.map(x => x.val)
    let op = vals.length > 1 ? '_or' : '_eq'
    if (opm && OP_MAP[opm[1]] === '_ne') op = '_ne'
    hits.push({ key: f.key, op, value: vals.length > 1 ? vals : vals[0], pos: idx })
  }
  return hits
}

// 句中不带字段名、只写取值时的直判（如「空化或闪蒸时…」）
const DIRECT_ENUM = [
  { key: 'flow_regime', values: { 空化: ['空化', '气蚀'], 闪蒸: ['闪蒸'], 阻塞流: ['阻塞流', '阻塞'] } },
  { key: 'media', values: { liquid: ['液体', '液相'], gas: ['气体', '气相'], steam: ['蒸汽', '水蒸汽'] } },
]

function scanEnumDirect(text, skipKeys) {
  const hits = []
  for (const f of DIRECT_ENUM) {
    if (skipKeys.has(f.key)) continue
    const found = []
    for (const [val, words] of Object.entries(f.values)) {
      for (const w of words) {
        const p = findWord(text, w)
        if (p >= 0) { found.push({ val, p }); break }
      }
    }
    if (!found.length) continue
    found.sort((a, b) => a.p - b.p)
    const vals = found.map(x => x.val)
    hits.push({ key: f.key, op: vals.length > 1 ? '_or' : '_eq', value: vals.length > 1 ? vals : vals[0], pos: found[0].p })
  }
  return hits
}


/** 扫描布尔型条件（「非 / 无 / 不」前缀判 false） */
function scanBool(text) {
  const hits = []
  for (const b of BOOL_FIELDS) {
    const alias = b.aliases.map(a => a.toLowerCase()).find(a => text.includes(a))
    if (!alias) continue
    const idx = text.indexOf(alias)
    const before = text.slice(Math.max(0, idx - 3), idx)
    const neg = /(非|无|不|没有)/.test(before)
    hits.push({ key: b.key, op: '_eq', value: !neg, pos: idx })
  }
  return hits
}

const ACTION_RULES = [
  { action: 'exclude', re: /(排除|剔除|不适用|禁用|不能用于|不支持|不适于|不予考虑)/ },
  { action: 'penalty', re: /(扣分|减分|降权|降分|扣\s*\d+(?:\.\d+)?\s*分|减\s*\d+(?:\.\d+)?\s*分)/ },
  { action: 'boost', re: /(加分|加权|优选|优先|偏好|加\s*\d+(?:\.\d+)?\s*分)/ },
  { action: 'flag', re: /(标记|打标)/ },
  { action: 'set_field', re: /(回填|补字段)/ },
  { action: 'require', re: /(必须|仅限|只允许|只能用|要求|硬性)/ },
]

function detectAction(text) {
  const found = []
  for (const r of ACTION_RULES) {
    const m = text.match(r.re)
    if (!m) continue
    found.push({ idx: text.indexOf(m[0]), word: m[0], action: r.action })
  }
  // 「必须排除 / 要求排除」中 require 只是修饰，真正动作是后面的动词：
  // 动词类动作优先，require 仅在没有任何动词动作时兜底。
  const verbs = found.filter(f => f.action !== 'require')
  const pool = verbs.length ? verbs : found
  return pool.sort((a, b) => a.idx - b.idx)[0] || null
}

/** 目标系列：如 BT110 / GC210 / GV120H；「全局/所有/任意」→ * */
function detectSeries(raw) {
  if (/(全局|所有系列|全部系列|任意系列|任何系列|所有|全部|任意)/.test(raw)) return { series: '*', all: true }
  const matches = (raw.match(/\b[A-Za-z]{2,4}\d{2,4}[A-Za-z]?\b/g) || [])
    .filter(s => !/^(DN|NPS|SCH|CL|PN|ASME|ANSI|API|ISO|IEC|GB|JB|HG)$/i.test(s))
  if (!matches.length) return { series: null, all: false }
  return { series: matches[0].toUpperCase(), all: false, count: matches.length }
}

/** 根据动作推测类别 */
function guessCategory(action, keys) {
  if (action === 'boost' || action === 'penalty') return 'preference'
  if (action === 'flag' || action === 'set_field') return 'post_filter'
  if (action === 'exclude' || action === 'require') {
    const scopeish = keys.some(k => ['temp_min', 'temp_max', 'temp', 'pipe_size_min', 'pipe_size_max', 'pipe_size'].includes(k))
    return scopeish ? 'scope' : 'constraint'
  }
  return null
}

// ---------------------------------------------------------------------------
// 括号提取 / 子句切分
// ---------------------------------------------------------------------------

/** 抽出括号内容（支持嵌套），返回等长文本（括号段置空格）+ 括号片段列表 */
function extractParens(text) {
  const chars = text.split('')
  const groups = []
  let depth = 0
  let buf = ''
  let start = -1
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (ch === '(') {
      if (depth === 0) { start = i; buf = '' }
      depth++
      chars[i] = ' '
    } else if (ch === ')') {
      if (depth > 0) depth--
      if (depth === 0 && start >= 0) { groups.push({ content: buf, start, end: i }); start = -1 }
      chars[i] = ' '
    } else if (depth > 0) {
      buf += ch
      chars[i] = ' '
    }
  }
  if (start >= 0) groups.push({ content: buf, start, end: text.length })
  return { text: chars.join(''), groups }
}

/** 按分号 / 句号 / 换行切分子句（括号已置空，不会误切） */
function splitClauses(text) {
  const out = []
  let from = 0
  for (let i = 0; i <= text.length; i++) {
    const isEnd = i === text.length
    if (isEnd || /[;。\n]/.test(text[i])) {
      const seg = text.slice(from, i)
      if (seg.trim()) out.push({ text: seg, start: from, end: i })
      from = i + 1
    }
  }
  return out
}

/** 相邻条件之间的连接词 → and / or */
function opFromHits(text, hits) {
  const ordered = [...hits].sort((a, b) => a.pos - b.pos)
  let hasOr = false
  let hasAnd = false
  for (let i = 1; i < ordered.length; i++) {
    const gap = text.slice(ordered[i - 1].pos, ordered[i].pos)
    if (/(或者|或|任一|其中之一)/.test(gap)) hasOr = true
    if (/(并且|且|同时|而且|以及)/.test(gap)) hasAnd = true
  }
  return { op: hasOr ? 'or' : 'and', conflict: hasOr && hasAnd }
}

/** 条件命中 → 表达式；同键同算子重复报错，_eq 与 _or 自动合并为集合 */
function mergeHits(expr, hits, errors, origin = '') {
  for (const c of hits) {
    const spec = KEY_SPECS[c.key]
    const slot = expr[c.key] || (expr[c.key] = {})
    if (c.op === '_or') {
      const list = Array.isArray(c.value) ? c.value : [c.value]
      if (Array.isArray(slot._or)) {
        for (const v of list) if (!slot._or.includes(v)) slot._or.push(v)
      } else if (slot._eq !== undefined) {
        slot._or = [slot._eq, ...list].filter((v, i, a) => a.indexOf(v) === i)
        delete slot._eq
      } else {
        slot._or = list
      }
      continue
    }
    if (slot[c.op] !== undefined) {
      if (String(slot[c.op]) !== String(c.value)) {
        errors.push(`${origin}条件「${spec?.label || c.key}」重复出现，请合并为区间或去掉其一`)
      }
      continue
    }
    if (c.op === '_eq' && Array.isArray(slot._or)) {
      if (!slot._or.includes(c.value)) slot._or.push(c.value)
      continue
    }
    slot[c.op] = c.value
  }
}

/** 表达式合并（多子句归入同一规则） */
function mergeExpr(target, src, errors, origin = '') {
  for (const [key, ops] of Object.entries(src || {})) {
    const spec = KEY_SPECS[key]
    const slot = target[key] || (target[key] = {})
    for (const [op, val] of Object.entries(ops)) {
      if (op === '_or' && Array.isArray(val)) {
        slot._or = Array.isArray(slot._or) ? [...new Set([...slot._or, ...val])] : val.slice()
        if (slot._eq !== undefined) { delete slot._eq }
        continue
      }
      if (slot[op] === undefined) { slot[op] = val; continue }
      if (String(slot[op]) !== String(val)) {
        errors.push(`${origin}条件「${spec?.label || key}」重复出现，请合并为区间或去掉其一`)
      }
    }
  }
}

/** 单个子句解析：条件 + 动作 */
function parseClause(text) {
  const errors = []
  const enumHits = scanEnum(text)
  const directHits = scanEnumDirect(text, new Set(enumHits.map(h => h.key)))
  const hits = [...scanNumeric(text), ...enumHits, ...directHits, ...scanBool(text)]
  const expr = {}
  mergeHits(expr, hits, errors)
  const { op, conflict } = opFromHits(text, hits)
  return { expr, op, conflict, hits, actionHit: detectAction(text), errors }
}

/** 动作分值 */
function scoreOf(action, text, actionHit) {
  if (action !== 'boost' && action !== 'penalty') return null
  const tail = actionHit ? text.slice(actionHit.idx, actionHit.idx + 24) : text
  const m = tail.match(/(\d+(?:\.\d+)?)\s*分/) || text.match(/score\s*[:=]?\s*(\d+(?:\.\d+)?)/)
  return m ? Number(m[1]) : null
}

/**
 * 解析中文规则描述（支持括号补充说明、分号多子句、多分支）
 * @returns {ok, errors, notes, target_series, action, action_payload, condition_expr,
 *           condition_op, categoryHint, desc, suggested_name, branches}
 *  branches[] 为每个「动作 + 目标系列」分支的形态，branches[0] 即上面的主字段
 */
export function parseNaturalRule(raw, opts = {}) {
  const text = normalize(raw)
  const notes = []
  if (!text.trim()) {
    return {
      ok: false, errors: ['请输入规则描述'], notes: [], condition_expr: {}, condition_op: 'and',
      action_payload: {}, branches: [],
    }
  }

  const { text: flat, groups: parens } = extractParens(text)
  const clauses = splitClauses(flat)
  const globalAction = detectAction(flat)
  const globalSeries = detectSeries(raw)

  // 逐子句解析（括号按位置归属到子句）
  const parsed = clauses.map(cl => {
    const res = parseClause(cl.text)
    const own = parens.filter(p => p.start >= cl.start && p.end <= cl.end)
    const parenNotes = []
    for (const p of own) {
      const inner = parseClause(p.content)
      const pText = p.content.trim()
      if (inner.hits.length) {
        mergeHits(res.expr, inner.hits, res.errors, '括号内')
        parenNotes.push(`已并入括号内条件「${pText}」`)
      } else if (/(仅|只|限|或|且|除非|但)/.test(pText)) {
        parenNotes.push(`括号说明「${pText}」为补充描述，未参与条件生成`)
      }
    }
    const series = detectSeries(raw.slice(cl.start, cl.end)).series
    return {
      ...res,
      notes: parenNotes,
      series: series || globalSeries.series,
      action: res.actionHit?.action || globalAction?.action || null,
      actionHit: res.actionHit || globalAction,
      text: cl.text,
    }
  })

  // 按「动作 + 系列」归组，不同组即不同分支
  const groups = new Map()
  for (const p of parsed) {
    const key = `${p.action || '?'}|${p.series || '*'}`
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(p)
  }

  const branches = []
  for (const [key, list] of groups) {
    const [action, series] = key.split('|')
    const expr = {}
    const errors = []
    const branchNotes = []
    let op = list.length > 1 ? 'or' : list[0].op
    for (const p of list) {
      mergeExpr(expr, p.expr, errors, list.length > 1 ? '子句' : '')
      errors.push(...p.errors)
      branchNotes.push(...p.notes)
      if (p.conflict) branchNotes.push('条件中同时出现「且」「或」，已按「或」处理，请核对')
      if (list.length > 1 && !Object.keys(p.expr).length) {
        branchNotes.push(`子句「${p.text.trim()}」未识别到条件，请补上字段（如「设计温度低于 -5℃」）`)
      }
    }
    if (list.length > 1) branchNotes.push(`已将 ${list.length} 个子句按「或」合并为一条规则`)

    const payload = {}
    const score = scoreOf(action, list.map(p => p.text).join(' '), list.find(p => p.actionHit)?.actionHit)
    if (score != null) payload.score = score
    if ((action === 'boost' || action === 'penalty') && score == null) {
      branchNotes.push('未识别加减分值，请在「动作参数」中补充 {"score": n}')
    }

    const seriesOut = series === '*' ? '*' : (series === 'null' ? null : series)
    const categoryHint = guessCategory(action, Object.keys(expr))
    const desc = describeCondition(expr, op)
    branches.push({
      target_series: seriesOut,
      action: action === '?' ? null : action,
      action_payload: payload,
      condition_expr: expr,
      condition_op: op,
      categoryHint,
      desc,
      errors,
      notes: branchNotes,
      suggested_name: [seriesOut || '*', desc, action && action !== '?' ? ACTION_LABELS[action] : '']
        .filter(Boolean).join(' '),
    })
  }

  const primary = branches[0] || {
    target_series: null, action: null, action_payload: {}, condition_expr: {},
    condition_op: 'and', categoryHint: null, desc: '无条件（命中全部工况）', errors: [], notes: [],
  }

  // 全局校验与提示
  const errors = [...(primary.errors || [])]
  if (!Object.keys(primary.condition_expr || {}).length) {
    errors.push('未识别到条件，请改用「条件行」录入，或写成「字段 + 比较 + 值」，如「设计温度低于 -5℃」')
  }
  if (!primary.action) errors.push('未识别到动作，请写明要做什么：排除 / 要求 / 加分 / 扣分 / 标记 / 回填')

  const notesAll = [...(primary.notes || []), ...notes]
  if (branches.length > 1) {
    notesAll.push(`识别到 ${branches.length} 个分支（动作或目标系列不同），已采用第 1 个；可在预览中切换`)
  }
  if (!globalSeries.series && !parsed.some(p => p.series)) {
    notesAll.push('未识别目标系列，请在「目标系列」中选择（* 表示全局）')
  } else if (globalSeries.count > 1) {
    notesAll.push(`识别到多个系列，已取 ${globalSeries.series}`)
  }
  if (['flag', 'set_field'].includes(primary.action)) {
    notesAll.push(primary.action === 'flag'
      ? '请把标记名写进「动作参数」，如 {"flag": "steam_service"}'
      : '请把字段名写进「动作参数」，如 {"field": "fd_mode"}')
  }

  return {
    ok: errors.length === 0,
    errors,
    notes: [...new Set(notesAll)],
    target_series: primary.target_series,
    action: primary.action,
    action_payload: primary.action_payload,
    condition_expr: primary.condition_expr,
    condition_op: primary.condition_op,
    categoryHint: primary.categoryHint,
    desc: primary.desc,
    suggested_name: primary.suggested_name,
    branches,
  }
}

/** 枚举值反查中文 */
function enumLabel(key, val) {
  const spec = KEY_SPECS[key]
  const s = String(val)
  if (!spec?.enumValues) return s
  // 大写短码（IV/V/VI、FC/FO）直接显示原值，其余显示首个中文别名
  if (/^[A-Z0-9]{1,4}$/.test(s)) return s
  const words = spec.enumValues[s]
  return words ? words[0] : s
}

function formatVal(key, val) {
  const spec = KEY_SPECS[key] || {}
  if (Array.isArray(val)) return val.map(v => formatVal(key, v)).join('、')
  if (typeof val === 'boolean') return val ? '是' : '否'
  if (spec.enumValues) return enumLabel(key, val)
  if (typeof val === 'number' || /^-?\d+(\.\d+)?$/.test(String(val))) return `${val}${spec.unit || ''}`
  return String(val)
}

/** 把条件表达式翻译成中文（用于编辑时回显预览） */
export function describeCondition(expr, op = 'and') {
  if (!expr || !Object.keys(expr).length) return '无条件（命中全部工况）'
  const parts = []
  for (const [key, v] of Object.entries(expr)) {
    const spec = KEY_SPECS[key] || { label: key }
    const ops = v && typeof v === 'object' && !Array.isArray(v) ? v : { _eq: v }
    for (const [o, val] of Object.entries(ops)) {
      if (o === '_required') parts.push(`${spec.label} ${val ? '必须提供' : '可以缺省'}`)
      else parts.push(`${spec.label} ${OP_TEXT[o] || o} ${formatVal(key, val)}`)
    }
  }
  return parts.join(op === 'or' ? ' 或 ' : ' 且 ')
}

/** 规则结构 → 条件行（编辑时初始化） */
export function conditionToRows(expr, op = 'and') {
  const rows = []
  if (!expr) return rows
  for (const [key, v] of Object.entries(expr)) {
    const ops = v && typeof v === 'object' && !Array.isArray(v) ? v : { _eq: v }
    for (const [o, val] of Object.entries(ops)) {
      rows.push({ key, op: o, value: Array.isArray(val) ? val.join('、') : String(val) })
    }
  }
  return rows
}

/** 中文字面值 → 数据库取值 */
function normalizeValue(key, rawVal) {
  const spec = KEY_SPECS[key]
  const s = String(rawVal).trim()
  if (!spec) return s
  if (spec.bool) {
    if (/^(是|true|1|开|需要|要求)$/i.test(s)) return true
    if (/^(否|false|0|关|不需要|不要求)$/i.test(s)) return false
    return s
  }
  if (spec.enumValues) {
    for (const [val, words] of Object.entries(spec.enumValues)) {
      if (val.toLowerCase() === s.toLowerCase() || words.some(w => w.toLowerCase() === s.toLowerCase())) return val
    }
    return s
  }
  const n = Number(s)
  return Number.isFinite(n) ? n : s
}

/** 条件行 → 条件表达式（附带校验信息） */
export function rowsToCondition(rows) {
  const expr = {}
  const errors = []
  ;(rows || []).forEach((r, i) => {
    const no = i + 1
    if (!r.key) return
    const rawVal = String(r.value ?? '').trim()
    if (!rawVal) return
    const spec = KEY_SPECS[r.key]
    if (!spec) { errors.push(`第 ${no} 行：未知条件键 ${r.key}`); return }
    const op = r.op || '_eq'
    if (expr[r.key] && expr[r.key][op] !== undefined) {
      errors.push(`第 ${no} 行：条件「${spec.label}」与前面重复`)
      return
    }
    let value
    if (op === '_or') {
      value = rawVal.split(/[、,，/]/).map(s => normalizeValue(r.key, s)).filter(v => v !== '')
      if (!value.length) return
    } else {
      value = normalizeValue(r.key, rawVal)
      if (spec.numeric && typeof value !== 'number') {
        errors.push(`第 ${no} 行：「${spec.label}」需要填数值`)
        return
      }
      if (spec.bool && typeof value !== 'boolean') {
        errors.push(`第 ${no} 行：「${spec.label}」需要填 是 / 否`)
        return
      }
    }
    if (spec.bool && !['_eq', '_ne'].includes(op)) {
      errors.push(`第 ${no} 行：布尔条件只能用 = / ≠`)
      return
    }
    expr[r.key] = expr[r.key] || {}
    expr[r.key][op] = value
  })
  return { expr, errors }
}
