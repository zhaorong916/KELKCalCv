import axios from 'axios'

const http = axios.create({ baseURL: '/api/v1', timeout: 60000 })

http.interceptors.response.use(
  r => r.data,
  err => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    return Promise.reject(new Error(msg))
  }
)

// 项目
export const projectsApi = {
  list: (kw) => http.get('/projects', { params: { keyword: kw } }),
  get: (id) => http.get(`/projects/${id}`),
  create: (d) => http.post('/projects', d),
  update: (id, d) => http.put(`/projects/${id}`, d),
  remove: (id) => http.delete(`/projects/${id}`),
}

// 位号
export const valvesApi = {
  list: (pid, kw) => http.get(`/projects/${pid}/valves`, { params: { keyword: kw } }),
  get: (pid, vid) => http.get(`/projects/${pid}/valves/${vid}`),
  create: (pid, d) => http.post(`/projects/${pid}/valves`, d),
  update: (pid, vid, d) => http.put(`/projects/${pid}/valves/${vid}`, d),
  remove: (pid, vid) => http.delete(`/projects/${pid}/valves/${vid}`),
}

// 计算/版本
export const calcApi = {
  list: (vid) => http.get(`/valves/${vid}/calculations`),
  create: (vid, d) => http.post(`/valves/${vid}/calculations`, d),
  get: (vid, cid) => http.get(`/valves/${vid}/calculations/${cid}`),
  remove: (vid, cid) => http.delete(`/valves/${vid}/calculations/${cid}`),
  setCurrent: (vid, cid) => http.put(`/valves/${vid}/calculations/${cid}/set-current`),
  saveConfig: (vid, cid, d) => http.put(`/valves/${vid}/calculations/${cid}/config`, d),
  saveCases: (vid, cid, cases) => http.put(`/valves/${vid}/calculations/${cid}/cases`, cases),
  run: (vid, cid) => http.post(`/valves/${vid}/calculations/${cid}/run`),
  preview: (vid, d) => http.post(`/valves/${vid}/calculations/preview`, d),
}

// 介质
export const fluidsApi = {
  list: (kw) => http.get('/fluids', { params: { keyword: kw } }),
  create: (d) => http.post('/fluids', d),
  update: (id, d) => http.put(`/fluids/${id}`, d),
  remove: (id) => http.delete(`/fluids/${id}`),
  resolveWater: (t, p) => http.get('/fluids/water/resolve', { params: { t, p } }),
}

// 单位字典
export const unitsApi = {
  list: () => http.get('/units'),
  category: (cat) => http.get(`/units/${cat}`),
  categories: () => http.get('/units/categories'),
}

// 阀门产品系列
export const valveTypesApi = {
  list: () => http.get('/valve-types'),
  detail: (sc) => http.get(`/valve-types/${sc}`),
  factorCurves: (sc) => http.get(`/valve-types/${sc}/factor-curves`),
  trimSizes: (sc) => http.get(`/valve-types/${sc}/trim-sizes`),
  curveOptions: (sc) => http.get(`/valve-types/${sc}/curve-options`),
  curvesBySelection: (sc, params) => http.get(`/valve-types/${sc}/curves-by-selection`, { params }),
  cvStk: (sc, params) => http.get(`/valve-types/${sc}/cv-stk`, { params }),
}

// 公称尺寸对照表 (in ↔ mm ↔ JIS A ↔ DN)
export const nominalSizesApi = {
  list: () => http.get('/nominal-sizes'),
}

// 公共选项数据 (连接形式/密封面/材质/填料等下拉)
export const publicOptionsApi = {
  list: (group) => http.get('/public-options', { params: group ? { group } : {} }),
}

// 管道规格数据 (pipe_data 表)
export const pipeDataApi = {
  list: (schedule) => http.get('/pipe-data', { params: schedule ? { schedule } : {} }),
  schedules: () => http.get('/pipe-data/schedules'),
}
