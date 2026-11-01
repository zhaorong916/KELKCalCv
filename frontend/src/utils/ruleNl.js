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
    aliases: ['阀前压力', '进口压力', '入口压力', '前压', '压力', 'p1'] },
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
  { key: 'leakage_class', label: '泄漏等级', aliases: ['泄漏等级', '泄漏级别', '密封等级', '泄漏等级class'],
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
  { label: '枚举', options: ENUM_FIELDS.map(f => ({ key: f.key, label: f.label })) },
  { label: '布尔', options: BOOL_FIELDS.map(b => ({ key: b.key, label: b.label })) },
]

function dedupe(keys) {
  const seen = new Set()
  return keys.filter(k => (seen.has(k) ? false : (seen.add(k), true)))
    .map(k => {
      const label = KEY_SPECS[k].label
      // 同一物理量的下限/上限/要求键共享 label，下拉框里加后缀区分
      let suffix = ''
      if (k.endsWith('_min')) suffix = '（下限）'
      else if (k.endsWith('_max')) suffix = '（上限）'
      else if (k.endsWith('_required')) suffix = '（要求）'
      return { key: k, label: label + suffix }
    })
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

// ---------------------------------------------------------------------------
// 括号与多分支逻辑解析
// ---------------------------------------------------------------------------
// 连接词模式（长优先扫描，避免「或」截断「或者」、「且」截断「并且」）
const SEP_PATTERNS = [
  { re: /或者|或是/, type: 'or' },
  { re: /并且|而且|同时|以及/, type: 'and' },
  { re: /或/, type: 'or' },
  { re: /且/, type: 'and' },
  { re: /[,，;；]/, type: 'and' },
]

/** 找出括号外的所有连接词位置：[{idx, len, type}] */
function findTopLevelSeps(text) {
  const seps = []
  let depth = 0
  let i = 0
  while (i < text.length) {
    const ch = text[i]
    if (ch === '(') { depth++; i++; continue }
    if (ch === ')') { if (depth > 0) depth--; i++; continue }
    if (depth > 0) { i++; continue }
    let matched = null
    for (const p of SEP_PATTERNS) {
      const m = text.slice(i).match(p.re)
      if (m && m.index === 0) {
        if (!matched || m[0].length > matched.len) matched = { idx: i, len: m[0].length, type: p.type }
      }
    }
    if (matched) { seps.push(matched); i += matched.len }
    else i++
  }
  return seps
}

function splitBySeps(text, seps) {
  const parts = []
  let last = 0
  for (const s of seps) {
    parts.push({ text: text.slice(last, s.idx), type: s.type })
    last = s.idx + s.len
  }
  parts.push({ text: text.slice(last), type: null })
  return parts
}

/** 去除最外层成对括号（支持多层嵌套） */
function stripOuterParens(text) {
  text = text.trim()
  while (text.startsWith('(') && text.endsWith(')')) {
    let depth = 0
    let closedAt = -1
    for (let i = 0; i < text.length; i++) {
      if (text[i] === '(') depth++
      else if (text[i] === ')') {
        depth--
        if (depth === 0) { closedAt = i; break }
      }
    }
    if (closedAt === text.length - 1) text = text.slice(1, -1).trim()
    else break
  }
  return text
}

/** 查找与 text[openIdx] 处 '(' 匹配的 ')' 下标，找不到返回 -1 */
function findMatchingParen(text, openIdx) {
  let depth = 0
  for (let i = openIdx; i < text.length; i++) {
    if (text[i] === '(') depth++
    else if (text[i] === ')') {
      depth--
      if (depth === 0) return i
    }
  }
  return -1
}

/** 单条子句（无顶层连接词）→ 扁平条件 dict；inheritKey 用于省略字段名时继承 */
function parseLeaf(text, inheritKey = null) {
  const enumHits = scanEnum(text)
  const directHits = scanEnumDirect(text, new Set(enumHits.map(h => h.key)))
  let numHits = scanNumeric(text)
  const boolHits = scanBool(text)

  // 继承字段：文本中无字段名时，用前一字段解析值
  if (inheritKey && !numHits.length && !enumHits.length && !directHits.length && !boolHits.length) {
    numHits = scanNumeric(text, KEY_TO_GROUP[inheritKey] || null)
    const enumHit = scanEnumByKey(text, inheritKey)
    if (enumHit) return enumHit
    const boolHit = scanBoolByKey(text, inheritKey)
    if (boolHit) return boolHit
  }

  const conditions = [...numHits, ...enumHits, ...directHits, ...boolHits]
  const expr = {}
  for (const c of conditions) {
    expr[c.key] = expr[c.key] || {}
    if (c.op === '_or') expr[c.key]._or = c.value
    else expr[c.key][c.op] = c.value
  }
  return expr
}

/** 对指定枚举键，在文本中扫描其取值（不依赖字段名） */
function scanEnumByKey(text, key) {
  const f = ENUM_FIELDS.find(x => x.key === key)
  if (!f || !f.values) return null
  const found = []
  for (const [val, words] of Object.entries(f.values)) {
    for (const w of words) {
      const p = findWord(text, w)
      if (p >= 0) { found.push({ val, p }); break }
    }
  }
  if (!found.length) return null
  found.sort((a, b) => a.p - b.p)
  const vals = found.map(x => x.val)
  return { [key]: { [vals.length > 1 ? '_or' : '_eq']: vals.length > 1 ? vals : vals[0] } }
}

/** 对指定布尔键，在文本中扫描（不依赖字段名） */
function scanBoolByKey(text, key) {
  const b = BOOL_FIELDS.find(x => x.key === key)
  if (!b) return null
  const alias = b.aliases.map(a => a.toLowerCase()).find(a => text.includes(a))
  if (!alias) return null
  const idx = text.indexOf(alias)
  const before = text.slice(Math.max(0, idx - 3), idx)
  const neg = /(非|无|不|没有)/.test(before)
  return { [key]: { _eq: !neg } }
}

/** 递归解析：括号分组 + 顶层 or/and 连接，产出 {$and/$or: [...]} 嵌套结构 */
function parseLogic(text) {
  text = text.trim()
  if (!text) return {}

  // 以括号组开头，且括号后无顶层连接词（只有动作词等）→ 解析括号内部
  if (text.startsWith('(')) {
    const closeIdx = findMatchingParen(text, 0)
    if (closeIdx > 0) {
      const after = text.slice(closeIdx + 1)
      if (findTopLevelSeps(after).length === 0) {
        return parseLogic(text.slice(1, closeIdx))
      }
    }
  }

  text = stripOuterParens(text)
  if (!text.trim()) return {}
  const seps = findTopLevelSeps(text)
  if (!seps.length) return parseLeaf(text)

  const orSeps = seps.filter(s => s.type === 'or')
  if (orSeps.length) {
    const parts = splitBySeps(text, orSeps)
    const valid = resolveParts(parts)
    if (valid.length <= 1) return valid[0] || parseLeaf(text)
    return { $or: valid }
  }
  const andSeps = seps.filter(s => s.type === 'and')
  if (andSeps.length) {
    const parts = splitBySeps(text, andSeps)
    const valid = resolveParts(parts)
    if (valid.length <= 1) return valid[0] || parseLeaf(text)
    return { $and: valid }
  }
  return parseLeaf(text)
}

/** 对拆分后的子句逐个解析；空子句尝试用前一个字段继承解析 */
function resolveParts(parts) {
  const valid = []
  let prevKey = null
  for (const p of parts) {
    if (!p.text.trim()) continue
    let sub = parseLogic(p.text)
    if (!sub || !Object.keys(sub).length) {
      if (prevKey) sub = parseLeaf(p.text, prevKey)
    }
    if (sub && Object.keys(sub).length) {
      valid.push(sub)
      const k = firstFieldKey(sub)
      if (k) prevKey = k
    }
  }
  return valid
}

/** 统计叶子条件数（用于「未识别到条件」提示） */
function countConditions(expr) {
  if (!expr) return 0
  const ks = Object.keys(expr)
  if (ks.length === 1 && (ks[0] === '$and' || ks[0] === '$or')) {
    return expr[ks[0]].reduce((n, s) => n + countConditions(s), 0)
  }
  return ks.length
}

/** 收集所有出现的条件键（用于类别推断） */
function collectKeys(expr) {
  const keys = []
  if (!expr) return keys
  const ks = Object.keys(expr)
  if (ks.length === 1 && (ks[0] === '$and' || ks[0] === '$or')) {
    for (const s of expr[ks[0]]) keys.push(...collectKeys(s))
    return keys
  }
  return ks
}

// 跳过的连接词（注意不能吞掉「为 / 是」，它们是等值算子；括号保留用于分组）
const SKIP = /^[\s在时时候达到的,、;:]*/

const NUM_ALIASES = NUM_GROUPS.flatMap(g => g.aliases.map(alias => ({ alias: alias.toLowerCase(), g })))

// 条件键 → 所属数值组（用于省略字段名时继承前一字段）
const KEY_TO_GROUP = {}
for (const g of NUM_GROUPS) {
  for (const k of [g.low, g.high, g.eq]) {
    if (k) KEY_TO_GROUP[k] = g
  }
}

/** 从条件表达式中提取第一个条件键（用于省略字段名时继承） */
function firstFieldKey(expr) {
  if (!expr) return null
  const ks = Object.keys(expr)
  if (ks.length === 1 && (ks[0] === '$and' || ks[0] === '$or')) {
    for (const s of expr[ks[0]]) {
      const k = firstFieldKey(s)
      if (k) return k
    }
    return null
  }
  return ks[0] || null
}

/**
 * 扫描数值型条件：字段 + 算子 + 数值(+单位)
 * 返回 [{ key, op, value, group, consumedTo }]
 */
function scanNumeric(text, inheritGroup = null) {
  const hits = []
  let from = 0
  let lastGroup = inheritGroup
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

    // 当前位置到下一个字段别名之间，若出现「算子+数值」则继承上一字段
    let rest = '', basePos = from, group = lastGroup
    if (best) {
      const gap = text.slice(from, best.idx).replace(SKIP, '')
      if (gap && lastGroup) {
        const m1 = gap.match(new RegExp(`(${OP_PATTERN})\\s*(?:达|到)?\\s*([-+]?\\d+(?:\\.\\d+)?)\\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?`))
        const m2 = gap.match(/([-+]?\d+(?:\.\d+)?)\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?\s*(及以上|以上|以下|以内)/)
        const m3 = gap.match(/在?\s*([-+]?\d+(?:\.\d+)?)\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?\s*(?:到|至|~|-)\s*([-+]?\d+(?:\.\d+)?)\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?/)
        if (applyNumericMatch(lastGroup, m1, m2, m3, hits)) {
          from = best.idx
          continue
        }
      }
      const afterAlias = text.slice(best.idx + best.alias.length)
      rest = afterAlias.replace(SKIP, '')
      basePos = text.length - afterAlias.length + (afterAlias.length - rest.length)
      group = best.g
    } else {
      // 没有更多字段别名，尝试用继承字段解析剩余文本（搜索式匹配）
      if (!lastGroup) break
      const tail = text.slice(from)
      const m1 = tail.match(new RegExp(`(${OP_PATTERN})\\s*(?:达|到)?\\s*([-+]?\\d+(?:\\.\\d+)?)\\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?`))
      const m2 = tail.match(/([-+]?\d+(?:\.\d+)?)\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?\s*(及以上|以上|以下|以内)/)
      const m3 = tail.match(/在?\s*([-+]?\d+(?:\.\d+)?)\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?\s*(?:到|至|~|-)\s*([-+]?\d+(?:\.\d+)?)\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?/)
      const consumed = applyNumericMatch(lastGroup, m1, m2, m3, hits)
      if (consumed > 0) {
        const matchIdx = (m1 || m2 || m3).index
        from = from + matchIdx + consumed
        lastGroup = lastGroup
        continue
      }
      break
    }

    const m1 = rest.match(new RegExp(`^(${OP_PATTERN})\\s*(?:达|到)?\\s*([-+]?\\d+(?:\\.\\d+)?)\\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?`))
    const m2 = rest.match(/^([-+]?\d+(?:\.\d+)?)\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?\s*(及以上|以上|以下|以内)/)
    const m3 = rest.match(/^在?\s*([-+]?\d+(?:\.\d+)?)\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?\s*(?:到|至|~|-)\s*([-+]?\d+(?:\.\d+)?)\s*(mpa|kpa|bar|℃|度|mm|dn|%|a)?/)

    const consumed = applyNumericMatch(group, m1, m2, m3, hits)
    if (consumed > 0) {
      lastGroup = group
      from = basePos + consumed
    } else if (best) {
      lastGroup = best.g
      from = best.idx + best.alias.length
    } else {
      break
    }
  }
  return hits
}

/** 把匹配到的数值模式写入 hits，返回消耗的字符数（0 表示未匹配） */
function applyNumericMatch(g, m1, m2, m3, hits) {
  if (m1) {
    const op = OP_MAP[m1[1]]
    const [num] = convertValue(g, m1[2], m1[3], hits)
    hits.push({ group: g, key: keyFor(g, op), op, value: num })
    return m1[0].length
  }
  if (m3) {
    const [lo] = convertValue(g, m3[1], m3[2], hits)
    const [hi] = convertValue(g, m3[3], m3[4], hits)
    hits.push({ group: g, key: g.low, op: '_min', value: lo })
    hits.push({ group: g, key: g.high, op: '_max', value: hi })
    return m3[0].length
  }
  if (m2) {
    const [num] = convertValue(g, m2[1], m2[2], hits)
    const upper = ['及以上', '以上'].includes(m2[3])
    hits.push({ group: g, key: upper ? g.low : g.high, op: upper ? '_min' : '_max', value: num })
    return m2[0].length
  }
  return 0
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
    hits.push({ key: f.key, op, value: vals.length > 1 ? vals : vals[0] })
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
    hits.push({ key: f.key, op: vals.length > 1 ? '_or' : '_eq', value: vals.length > 1 ? vals : vals[0] })
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
    hits.push({ key: b.key, op: '_eq', value: !neg })
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
  let best = null
  for (const r of ACTION_RULES) {
    const m = text.match(r.re)
    if (!m) continue
    const idx = text.indexOf(m[0])
    if (!best || idx < best.idx) best = { idx, word: m[0], action: r.action }
  }
  return best
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

/**
 * 解析中文规则描述
 * @returns {ok, errors, notes, target_series, action, action_payload,
 *           condition_expr, condition_op, categoryHint, desc, suggested_name}
 */
export function parseNaturalRule(raw, opts = {}) {
  const text = normalize(raw)
  const errors = []
  const notes = []
  if (!text.trim()) {
    return { ok: false, errors: ['请输入规则描述'], notes: [], condition_expr: {}, condition_op: 'and', action_payload: {} }
  }

  // 条件解析：支持括号分组与多分支（递归产出 $and/$or 嵌套结构）
  const expr = parseLogic(text)
  if (countConditions(expr) === 0) {
    errors.push('未识别到条件，请改用「条件行」录入，或写成「字段 + 比较 + 值」，如「设计温度低于 -5℃」')
  }

  const actionHit = detectAction(text)
  if (!actionHit) errors.push('未识别到动作，请写明要做什么：排除 / 要求 / 加分 / 扣分 / 标记 / 回填')
  const action = actionHit?.action || null

  const actionPayload = {}
  if (action === 'boost' || action === 'penalty') {
    const tail = actionHit ? text.slice(actionHit.idx, actionHit.idx + 24) : text
    const sm = tail.match(/(\d+(?:\.\d+)?)\s*分/) || text.match(/score\s*[:=]?\s*(\d+(?:\.\d+)?)/)
    if (sm) actionPayload.score = Number(sm[1])
    else notes.push('未识别加减分值，请在「动作参数」中补充 {"score": n}')
  }
  if (action === 'flag') notes.push('请把标记名写进「动作参数」，如 {"flag": "steam_service"}')
  if (action === 'set_field') notes.push('请把字段名写进「动作参数」，如 {"field": "fd_mode"}')

  // 顶层连接关系：嵌套结构已由 $and/$or 表达，扁平结构默认 and
  let conditionOp = opts.conditionOp
  if (!conditionOp) {
    conditionOp = expr.$or ? 'or' : 'and'
  }

  const series = detectSeries(raw)
  if (series.count > 1) notes.push(`识别到多个系列（${series.series} 等），已取第一个；如需匹配多个系列请改用 JSON 直编`)
  if (!series.series) notes.push('未识别目标系列，请在「目标系列」中选择（* 表示全局）')

  const categoryHint = guessCategory(action, collectKeys(expr))
  const desc = describeCondition(expr, conditionOp)
  const suggestedName = [
    series.series || '*',
    desc,
    action ? ACTION_LABELS[action] : '',
  ].filter(Boolean).join(' ')

  return {
    ok: errors.length === 0,
    errors,
    notes,
    target_series: series.series,
    action,
    action_payload: actionPayload,
    condition_expr: expr,
    condition_op: conditionOp,
    categoryHint,
    desc,
    suggested_name: suggestedName,
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
  const ks = Object.keys(expr)
  // 嵌套逻辑：$and / $or
  if (ks.length === 1 && (ks[0] === '$and' || ks[0] === '$or')) {
    const subOp = ks[0] === '$and' ? 'and' : 'or'
    const parts = expr[ks[0]].map(s => {
      const d = describeCondition(s, subOp)
      // 子表达式含多个条件时加括号，增强可读性
      const nested = s && Object.keys(s).length === 1 &&
        (Object.keys(s)[0] === '$and' || Object.keys(s)[0] === '$or')
      return nested ? `(${d})` : d
    })
    return parts.join(subOp === 'and' ? ' 且 ' : ' 或 ')
  }
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

/** 规则结构 → 条件行（编辑时初始化；嵌套结构打平，逻辑关系请在 JSON 中查看） */
export function conditionToRows(expr, op = 'and') {
  const rows = []
  collectRows(expr, rows)
  return rows
}

function collectRows(expr, rows) {
  if (!expr) return
  const ks = Object.keys(expr)
  if (ks.length === 1 && (ks[0] === '$and' || ks[0] === '$or')) {
    for (const s of expr[ks[0]]) collectRows(s, rows)
    return
  }
  for (const [key, v] of Object.entries(expr)) {
    const ops = v && typeof v === 'object' && !Array.isArray(v) ? v : { _eq: v }
    for (const [o, val] of Object.entries(ops)) {
      rows.push({ key, op: o, value: Array.isArray(val) ? val.join('、') : String(val) })
    }
  }
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
