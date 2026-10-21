<template>
  <div class="vt-page">
    <div class="vt-layout">
      <!-- ============ 左栏：系列列表 ============ -->
      <aside class="vt-sidebar">
        <div class="sidebar-header">
          <el-icon><Operation /></el-icon>
          <span>Cv计算因数</span>
        </div>
        <div class="sidebar-search">
          <el-input v-model="keyword" placeholder="搜索系列代码/名称" clearable size="small" prefix-icon="Search" />
        </div>
        <div class="sidebar-tree" v-loading="loadingList">
          <div v-for="g in groupedSeries" :key="g.name" class="series-group">
            <div class="group-title" @click="g.collapsed = !g.collapsed">
              <el-icon><ArrowRight v-if="g.collapsed" /><ArrowDown v-else /></el-icon>
              <span class="group-name">{{ g.name }}</span>
              <span class="group-count">{{ g.items.length }}</span>
            </div>
            <div v-show="!g.collapsed" class="group-items">
              <div
                v-for="s in g.items" :key="s.series_code"
                class="series-item" :class="{active: currentCode === s.series_code}"
                @click="selectSeries(s.series_code)"
              >
                <span class="series-code">{{ s.series_code }}</span>
                <span class="series-name" :title="s.series_name">{{ s.series_name }}</span>
              </div>
            </div>
          </div>
          <el-empty v-if="!loadingList && !seriesList.length" description="暂无系列数据" :image-size="60" />
        </div>
      </aside>

      <!-- ============ 右栏：详情面板 ============ -->
      <section class="vt-detail" v-loading="loadingDetail">
        <template v-if="current">
          <!-- 标题条 (Excel R1 风格) -->
          <div class="excel-title-bar">
            <span class="etb-code">{{ current.series_code }}</span>
            <span class="etb-sep">,</span>
            <span class="etb-name">{{ current.series_name }}</span>
            <el-tag size="small" effect="dark" :type="categoryTagType" class="etb-tag">{{ categoryLabel }}</el-tag>
          </div>

          <!-- 默认系数卡片 -->
          <div class="excel-card">
            <div class="card-title">Default Coefficients (IEC 60534)</div>
            <div class="coef-grid">
              <div class="coef-tile">
                <div class="coef-label">factor_group</div>
                <div class="coef-value small">{{ current.factor_group || '—' }}</div>
              </div>
              <div class="coef-tile">
                <div class="coef-label">eq_index</div>
                <div class="coef-value">{{ current.eq_index ?? '—' }}</div>
              </div>
              <div class="coef-tile">
                <div class="coef-label">FL (default)</div>
                <div class="coef-value">{{ fmtNum(current.fl_default) }}</div>
              </div>
              <div class="coef-tile">
                <div class="coef-label">xT (default)</div>
                <div class="coef-value">{{ fmtNum(current.xt_default) }}</div>
              </div>
              <div class="coef-tile">
                <div class="coef-label">FD (default)</div>
                <div class="coef-value">{{ fmtNum(current.fd_default) }}</div>
              </div>
              <div class="coef-tile">
                <div class="coef-label">Kc (default)</div>
                <div class="coef-value">{{ fmtNum(current.kc_default) }}</div>
              </div>
            </div>
          </div>

          <!-- 系数曲线卡片 (Excel "Choices for Graphs" 风格) -->
          <div class="excel-card">
            <div class="card-title">
              Factor Curves
              <span class="card-sub" v-if="curveOptions.has_curve_data">可按压力等级/阀芯/特性选择</span>
              <span class="card-sub warn" v-else>该系列无曲线映射数据</span>
            </div>

            <!-- 选择器 -->
            <!-- 选择器 -->
            <div class="curve-selectors" v-if="curveOptions.has_curve_data">
              <!-- 动态筛选器 (优先使用 filter_configs) -->
              <template v-if="curveOptions.filter_configs?.length > 0">
                <div class="sel-item" v-for="fc in curveOptions.filter_configs" :key="fc.key">
                  <label>{{ fc.label }}</label>
                  <el-select
                    v-model="filterValues[fc.key]"
                    size="small"
                    @change="onDynamicFilterChange(fc)"
                    :style="{ width: fc.key === 'trim_seat_type' ? '160px' : fc.key === 'nominal_dn' ? '150px' : fc.key === 'nominal_trim' ? '140px' : fc.key === 'pressure_rating' ? '140px' : '130px' }"
                    clearable
                  >
                    <el-option
                      v-for="opt in getFilterOptions(fc)"
                      :key="formatOpt(opt, 'value')"
                      :label="formatOpt(opt, 'label')"
                      :value="formatOpt(opt, 'value')"
                    />
                  </el-select>
                </div>
              </template>

              <!-- 兼容旧硬编码 (fallback, 当无 filter_configs) -->
              <template v-else>
                <!-- Trim Type (EQ%/Linear) -->
                <div class="sel-item" v-if="!useCascade && curveOptions.filters.trim_types?.length > 0">
                  <label>Trim Type</label>
                  <el-select v-model="selTrimType" size="small" @change="loadSelectedCurves" style="width: 120px">
                    <el-option v-for="t in curveOptions.filters.trim_types" :key="t" :label="t" :value="t" />
                  </el-select>
                </div>

                <!-- Trim/Seat Type (GV120 级联入口) -->
                <div class="sel-item" v-if="curveOptions.filters.trim_seat_types?.length > 0">
                  <label>{{ useCascade ? 'Trim Type' : 'Trim / Seat Type' }}</label>
                  <el-select v-model="selTrimSeatType" size="small" @change="onTrimSeatTypeChange" :style="{ width: useCascade ? '150px' : '160px' }" clearable>
                    <el-option v-for="t in curveOptions.filters.trim_seat_types" :key="t" :label="t" :value="t" />
                  </el-select>
                </div>

                <!-- Pressure Rating -->
                <div class="sel-item" v-if="(useCascade ? cascadePressures.length : curveOptions.filters.pressure_ratings?.length) > 0">
                  <label>Pressure Rating</label>
                  <el-select v-model="selPressure" size="small" @change="onPressureChange" style="width: 150px">
                    <template v-if="useCascade">
                      <el-option v-for="p in cascadePressures" :key="p" :label="p" :value="p" />
                    </template>
                    <template v-else>
                      <el-option v-for="p in curveOptions.filters.pressure_ratings" :key="p" :label="p" :value="p" />
                    </template>
                  </el-select>
                </div>

                <!-- Nominal Valve Size (GV120 级联) -->
                <div class="sel-item" v-if="useCascade && cascadeDns.length > 0">
                  <label>Nominal Valve Size</label>
                  <div class="sel-row">
                    <el-select v-model="selDn" size="small" @change="onDnChange" style="width: 140px">
                      <el-option v-for="d in cascadeDns" :key="d.dn_mm" :label="d.label" :value="d.dn_mm">
                        <span>{{ d.label }}</span>
                        <span style="float:right;color:#999;font-size:11px">Stroke {{ d.stroke }}mm</span>
                      </el-option>
                    </el-select>
                    <el-select v-model="dnLabelUnit" size="small" class="unit-toggle" @change="onDnLabelUnitChange">
                      <el-option v-for="o in DN_LABEL_OPTIONS" :key="o.value" :label="o.label" :value="o.value" :title="o.tip" />
                    </el-select>
                  </div>
                </div>

                <!-- Plug Size -->
                <div class="sel-item" v-if="availablePlugs?.length > 0">
                  <label>Plug Size</label>
                  <el-select v-model="selPlug" size="small" @change="loadSelectedCurves" style="width: 130px">
                    <el-option v-for="p in availablePlugs" :key="p" :label="formatPlugLabel(p)" :value="p" />
                  </el-select>
                </div>

                <!-- Flow Direction -->
                <div class="sel-item" v-if="curveOptions.filters.flow_directions?.length > 0">
                  <label>Flow Direction</label>
                  <el-select v-model="selFlowDirection" size="small" @change="loadSelectedCurves" style="width: 140px" clearable>
                    <el-option v-for="f in curveOptions.filters.flow_directions" :key="f.code" :label="f.code" :value="f.code">
                      <span>{{ f.code }}</span>
                      <span style="float:right;color:#999;font-size:11px">{{ f.label.split('(')[0].trim() }}</span>
                    </el-option>
                  </el-select>
                </div>
              </template>

              <div class="sel-item xt-result" v-if="selectedCurves.xt_calculated != null">
                <label>xT (计算)</label>
                <span class="xt-value">{{ fmtNum(selectedCurves.xt_calculated, 4) }}</span>
                <span class="xt-formula">{{ selectedCurves.xt_formula }} (FL={{ fmtNum(selectedCurves.fl_rated, 4) }})</span>
              </div>
            </div>

            <!-- GV120 Table1/Table2 速览 (级联模式) -->
            <div class="gv120-tables" v-if="useCascade && currentPlugRange">
              <div class="gv-table table1">
                <div class="gv-tab-title">Table 1 — Body & Trim Size</div>
                <div class="gv-tab-row"><span>Stroke</span><b>{{ currentPlugRange.stroke }} mm</b></div>
                <div class="gv-tab-row"><span>Available Plugs</span><b>{{ availablePlugs.length }}</b></div>
              </div>
              <div class="gv-table table2" v-if="selPlug">
                <div class="gv-tab-title">Table 2 — Trim Size Capacity</div>
                <template v-if="(() => { const p = currentPlugTable.find(x => x.plug_mm === selPlug); return p; })()">
                  <div class="gv-tab-row"><span>Plug Size</span><b>{{ selPlug }} mm</b></div>
                  <div class="gv-tab-row"><span>Stroke</span><b>{{ currentPlugRange.stroke }} mm</b></div>
                  <div class="gv-tab-row"><span>Cv =%</span><b class="cv-eq-val">{{ fmtNum(currentPlugTable.find(x => x.plug_mm === selPlug)?.cv_eq, 4) }}</b></div>
                  <div class="gv-tab-row"><span>Cv Linear</span><b>{{ fmtNum(currentPlugTable.find(x => x.plug_mm === selPlug)?.cv_linear, 4) }}</b></div>
                  <div class="gv-tab-row"><span>Minimum Cv</span><b>{{ fmtNum(currentPlugTable.find(x => x.plug_mm === selPlug)?.cv_min, 4) }}</b></div>
                  <div class="gv-tab-row"><span>%Stk Index</span><b>{{ currentPlugTable.find(x => x.plug_mm === selPlug)?.stk_index ?? '—' }}</b></div>
                </template>
              </div>
            </div>

            <!-- 双曲线图 -->
            <div class="charts-row" v-if="selectedCurves.fl">
              <!-- 左图: Cv versus Travel -->
              <div class="chart-box">
                <div class="chart-title">Cv versus Travel</div>
                <svg class="chart-svg" :viewBox="`0 0 ${SVG_W} ${SVG_H}`" preserveAspectRatio="none">
                  <g class="grid">
                    <line v-for="i in 10" :key="'lx'+i" :x1="CHART_X0 + i*CELL" :y1="CHART_Y0" :x2="CHART_X0 + i*CELL" :y2="CHART_Y_MAX" />
                    <line v-for="i in 10" :key="'ly'+i" :x1="CHART_X0" :y1="CHART_Y0 + i*CELL" :x2="CHART_X0 + CHART_W" :y2="CHART_Y0 + i*CELL" />
                  </g>
                  <line :x1="CHART_X0" :y1="CHART_Y_MAX" :x2="CHART_X0 + CHART_W" :y2="CHART_Y_MAX" class="axis" />
                  <line :x1="CHART_X0" :y1="CHART_Y0" :x2="CHART_X0" :y2="CHART_Y_MAX" class="axis" />
                  <text v-for="i in 11" :key="'yt'+i" :x="CHART_X0 - 5" :y="CHART_Y_MAX - i*CELL + 3" text-anchor="end" font-size="9">{{ i*10 }}%</text>
                  <text v-for="i in 11" :key="'xt'+i" :x="CHART_X0 + i*CELL" :y="CHART_Y_MAX + 15" text-anchor="middle" font-size="9">{{ i*10 }}%</text>
                  <polyline :points="cvTravelPoints" class="curve-line" fill="none" />
                  <circle v-if="verifyOpening >= 0" :cx="CHART_X0 + (verifyOpening/100)*CHART_W" :cy="cvTravelY(verifyOpening/100)" r="3.5" class="curve-marker" />
                </svg>
                <div class="chart-axis-label">Valve Travel, % of Full Open</div>
                <div class="chart-y-label">Percentage of Rated Cv</div>
              </div>

              <!-- 右图: Sizing Indices versus % Rated Cv -->
              <div class="chart-box">
                <div class="chart-title">Sizing Indices versus % Rated Cv</div>
                <svg class="chart-svg" :viewBox="`0 0 ${SVG_W} ${SVG_H}`" preserveAspectRatio="none">
                  <g class="grid">
                    <line v-for="i in 10" :key="'sx'+i" :x1="CHART_X0 + i*CELL" :y1="CHART_Y0" :x2="CHART_X0 + i*CELL" :y2="CHART_Y_MAX" />
                    <line v-for="i in 10" :key="'sy'+i" :x1="CHART_X0" :y1="CHART_Y0 + i*CELL" :x2="CHART_X0 + CHART_W" :y2="CHART_Y0 + i*CELL" />
                  </g>
                  <line :x1="CHART_X0" :y1="CHART_Y_MAX" :x2="CHART_X0 + CHART_W" :y2="CHART_Y_MAX" class="axis" />
                  <line :x1="CHART_X0" :y1="CHART_Y0" :x2="CHART_X0" :y2="CHART_Y_MAX" class="axis" />
                  <text v-for="i in 11" :key="'syt'+i" :x="CHART_X0 - 5" :y="CHART_Y_MAX - i*CELL + 3" text-anchor="end" font-size="9">{{ fmtNum(i*0.1, 1) }}</text>
                  <text v-for="i in 11" :key="'sxt'+i" :x="CHART_X0 + i*CELL" :y="CHART_Y_MAX + 15" text-anchor="middle" font-size="9">{{ i*10 }}%</text>
                  <polyline :points="sizingPoints('fl')" class="sizing-fl" fill="none" />
                  <polyline :points="sizingPoints('xt')" class="sizing-xt" fill="none" />
                  <polyline :points="sizingPoints('kc')" class="sizing-kc" fill="none" />
                  <polyline v-if="selectedCurves.fd || fdIsFormula()" :points="sizingPoints('fd')" class="sizing-fd" fill="none" />
                </svg>
                <div class="chart-axis-label">Percentage of Rated Cv</div>
                <div class="chart-y-label">Sizing Indices</div>
                <div class="chart-legend">
                  <span class="lg lg-fl">FL</span>
                  <span class="lg lg-xt">xT</span>
                  <span class="lg lg-kc">Kc</span>
                  <span v-if="selectedCurves.fd || fdIsFormula()" class="lg lg-fd">Fd</span>
                </div>
              </div>

              <!-- 右侧: Curve Feature Values -->
              <div class="feature-table-wrap">
                <div class="feature-table-title">Curve Feature Values</div>
                <table class="feature-table">
                  <thead>
                    <tr>
                      <th>Cv/Cvrated</th>
                      <th>%Stk</th>
                      <th>FL</th>
                      <th>xT</th>
                      <th>Kc</th>
                      <th>Fd</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in featureTable" :key="row.phi">
                      <td>{{ row.phi }}%</td>
                      <td>{{ fmtNum(row.stk, 1) }}%</td>
                      <td>{{ fmtNum(row.fl, 3) }}</td>
                      <td>{{ fmtNum(row.xt, 3) }}</td>
                      <td>{{ fmtNum(row.kc, 3) }}</td>
                      <td>{{ fmtNum(row.fd, 3) }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- 下方: 多项式系数表 -->
            <div class="coef-tables" v-if="selectedCurves.fl">
              <table class="curve-coef-table small">
                <thead>
                  <tr>
                    <th>Factor</th><th>Index</th><th>Min</th><th>Max</th>
                    <th>P0</th><th>P1</th><th>P2</th><th>P3</th><th>P4</th>
                    <th>A0</th><th>A1</th><th>A2</th><th>A3</th><th>A4</th><th>A5</th><th>A6</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>{{ selTrimType === 'Linear' ? 'Linear' : 'Eq%' }}</td>
                    <td>{{ strokeModeLabel }}</td>
                    <td>—</td><td>—</td>
                    <td>{{ fmtNum(selectedCurves.eqcv?.p0) }}</td>
                    <td>{{ fmtNum(selectedCurves.eqcv?.p1) }}</td>
                    <td>{{ fmtNum(selectedCurves.eqcv?.p2) }}</td>
                    <td>{{ fmtNum(selectedCurves.eqcv?.p3) }}</td>
                    <td>{{ fmtNum(selectedCurves.eqcv?.p4) }}</td>
                    <td>{{ fmtNum(selectedCurves.eqcv?.a0) }}</td>
                    <td>{{ fmtNum(selectedCurves.eqcv?.a1) }}</td>
                    <td>{{ fmtNum(selectedCurves.eqcv?.a2) }}</td>
                    <td>{{ fmtNum(selectedCurves.eqcv?.a3) }}</td>
                    <td>{{ fmtNum(selectedCurves.eqcv?.a4) }}</td>
                    <td>{{ fmtNum(selectedCurves.eqcv?.a5) }}</td>
                    <td>{{ fmtNum(selectedCurves.eqcv?.a6) }}</td>
                  </tr>
                  <tr>
                    <td>FL</td>
                    <td>{{ selectedCurves.fl?.eq_index ?? selectedCurves.debug?.fl_eq_index ?? '—' }}</td>
                    <td>{{ fmtNum(selectedCurves.fl?.value_min) }}</td>
                    <td>{{ fmtNum(selectedCurves.fl?.value_max) }}</td>
                    <td>{{ fmtNum(selectedCurves.fl?.p0) }}</td>
                    <td>{{ fmtNum(selectedCurves.fl?.p1) }}</td>
                    <td>{{ fmtNum(selectedCurves.fl?.p2) }}</td>
                    <td>{{ fmtNum(selectedCurves.fl?.p3) }}</td>
                    <td>{{ fmtNum(selectedCurves.fl?.p4) }}</td>
                    <td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td>
                  </tr>
                  <tr>
                    <td>Kc</td>
                    <td>{{ selectedCurves.kc?.eq_index ?? selectedCurves.debug?.kc_eq_index ?? '—' }}</td>
                    <td>{{ fmtNum(selectedCurves.kc?.value_min) }}</td>
                    <td>{{ fmtNum(selectedCurves.kc?.value_max) }}</td>
                    <td>{{ fmtNum(selectedCurves.kc?.p0) }}</td>
                    <td>{{ fmtNum(selectedCurves.kc?.p1) }}</td>
                    <td>{{ fmtNum(selectedCurves.kc?.p2) }}</td>
                    <td>{{ fmtNum(selectedCurves.kc?.p3) }}</td>
                    <td>{{ fmtNum(selectedCurves.kc?.p4) }}</td>
                    <td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td>
                  </tr>
                  <tr>
                    <td>Fd</td>
                    <td>{{ selectedCurves.fd_mode === 'eqn' ? '公式' : (selectedCurves.fd_mode === 'gc210_eqn' ? 'GC210' : (selectedCurves.fd_mode === 'kfd' ? '常数' : (selectedCurves.fd?.eq_index ?? '—'))) }}</td>
                    <td>{{ fmtNum(selectedCurves.fd?.value_min) }}</td>
                    <td>{{ fmtNum(selectedCurves.fd?.value_max) }}</td>
                    <td>{{ fmtNum(selectedCurves.fd?.p0) }}</td>
                    <td>{{ fmtNum(selectedCurves.fd?.p1) }}</td>
                    <td>{{ fmtNum(selectedCurves.fd?.p2) }}</td>
                    <td>{{ fmtNum(selectedCurves.fd?.p3) }}</td>
                    <td>{{ fmtNum(selectedCurves.fd?.p4) }}</td>
                    <td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <el-empty v-else-if="!(curveOptions.filters?.pressure_ratings?.length || curveOptions.cascade)" description="该系列无曲线映射数据" :image-size="80" />
          </div>

          <!-- 额定容量表卡片 (Excel Table 1 Rated Capacities 风格) -->
          <div class="excel-card">
            <div class="card-title">
              Table 1 · Rated Capacities
              <span class="card-sub" v-if="trimSizesFiltered.length">共 {{ trimSizesFiltered.length }} 行</span>
              <span class="card-sub warn" v-else-if="trimSizes.length">筛选后无匹配数据（共 {{ trimSizes.length }} 行）</span>
              <span class="card-sub warn" v-else>该系列暂未导入 Trim/Cv 数据</span>
            </div>
            <div class="trim-table-wrap" v-if="trimSizesFiltered.length">
              <table class="trim-table">
                <thead>
                  <tr>
                    <th v-if="showCol('dn_label')">DN Label</th>
                    <th v-if="showCol('trim_label')">Trim Label</th>
                    <th v-if="showCol('flow_char')">Flow Char</th>
                    <th v-if="showCol('trim_type')">Trim Type</th>
                    <th v-if="showCol('pressure_rating')">Pressure Rating</th>
                    <th v-if="showCol('seat_type')">Seat Type</th>
                    <th v-if="showCol('rated_cv')" class="col-cv">Rated Cv</th>
                    <th v-if="showCol('stroke_unit')">Stroke Unit</th>
                    <th v-if="showCol('stroke_value')">Stroke Value</th>
                    <th v-if="showCol('plug_mm')">Plug (mm)</th>
                    <th v-if="showCol('stk_index')">%Stk Index</th>
                    <th v-if="showCol('kfd')">Kfd</th>
                    <th v-if="showCol('kfo')">Kfo</th>
                    <th v-if="showCol('kfb')">Kfb</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(r, i) in trimSizesFiltered" :key="i">
                    <td>{{ r.dn_label ?? '' }}</td>
                    <td>{{ r.trim_label ?? '' }}</td>
                    <td v-if="showCol('flow_char')">{{ r.flow_char ?? '' }}</td>
                    <td v-if="showCol('trim_type')">{{ r.trim_type ?? '' }}</td>
                    <td v-if="showCol('pressure_rating')">{{ r.pressure_rating ?? '' }}</td>
                    <td v-if="showCol('seat_type')">{{ r.seat_type ?? '' }}</td>
                    <td v-if="showCol('rated_cv')" class="cell-cv">{{ fmtNum(r.rated_cv) }}</td>
                    <td v-if="showCol('stroke_unit')">{{ r.stroke_unit ?? '' }}</td>
                    <td v-if="showCol('stroke_value')">{{ fmtNum(r.stroke_value) }}</td>
                    <td v-if="showCol('plug_mm')">{{ fmtNum(r.plug_mm) }}</td>
                    <td v-if="showCol('stk_index')">{{ fmtNum(r.stk_index) }}</td>
                    <td v-if="showCol('kfd')">{{ fmtNum(r.kfd) }}</td>
                    <td v-if="showCol('kfo')">{{ fmtNum(r.kfo) }}</td>
                    <td v-if="showCol('kfb')">{{ fmtNum(r.kfb) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <el-empty v-else-if="trimSizes.length" description="当前筛选条件无匹配数据" :image-size="80" />
            <el-empty v-else description="该系列暂未导入 Trim/Cv 数据" :image-size="80" />
          </div>

          <!-- 校核卡片 -->
          <div class="excel-card verify-card">
            <div class="card-title">
              多项式曲线校核
              <span class="card-sub">输入开度，实时求值并对比 value_min/max 钳制范围</span>
            </div>
            <div class="verify-controls">
              <span class="vc-label">开度 %:</span>
              <el-slider v-model="verifyOpening" :min="0" :max="100" :step="1" style="flex:1; margin: 0 12px" />
              <el-input-number v-model="verifyOpening" :min="0" :max="100" :step="1" size="small" controls-position="right" style="width: 110px" />
            </div>
            <div class="verify-results">
              <div v-for="ft in VERIFY_FACTORS" :key="ft.key" class="vr-item" :class="verifyStatus(ft.key)">
                <div class="vr-label">{{ ft.label }}</div>
                <div class="vr-value">{{ fmtNum(verifyValue(ft.key), 4) }}</div>
                <div class="vr-range" v-if="selectedCurves[ft.key]">
                  范围 [{{ fmtNum(selectedCurves[ft.key].value_min) }}, {{ fmtNum(selectedCurves[ft.key].value_max) }}]
                </div>
                <div class="vr-status">
                  <span v-if="ft.key === 'fd' && fdIsFormula()" class="status-ok">公式计算</span>
                  <span v-else-if="!selectedCurves[ft.key]" class="status-miss">无曲线</span>
                  <span v-else-if="verifyInBounds(ft.key)" class="status-ok">✓ 在范围内</span>
                  <span v-else class="status-bad">✗ 超出钳制</span>
                </div>
              </div>
              <div class="vr-item status-info">
                <div class="vr-label">xT</div>
                <div class="vr-value">{{ fmtNum(verifyValue('xt'), 4) }}</div>
                <div class="vr-status"><span class="status-info">xT=0.84×FL²</span></div>
              </div>
              <div class="vr-item status-info">
                <div class="vr-label">Eq%</div>
                <div class="vr-value">{{ fmtNum(verifyValue('eqcv'), 4) }}</div>
                <div class="vr-status"><span class="status-info">行程比</span></div>
              </div>
            </div>
            <div class="verify-note" v-if="clampedValues.length">
              <el-icon><WarningFilled /></el-icon>
              <span>以下系数超出 [value_min, value_max] 范围，计算引擎将钳制：{{ clampedValues.join('、') }}</span>
            </div>
          </div>
        </template>

        <el-empty v-else-if="!loadingDetail" description="请从左侧选择阀门系列" :image-size="100" />
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { valveTypesApi, nominalSizesApi } from '@/api'

// ---------- 公称尺寸对照表 ----------
const nominalSizeRefs = ref([])  // [{dn_mm, nps_in, nps_in_decimal, jis_a, dn_label}]

// 公称尺寸显示单位: in(英制, 默认) / mm(公制) / A(JIS) / DN
const dnLabelUnit = ref(localStorage.getItem('dnLabelUnit') || 'in')

const DN_LABEL_OPTIONS = [
  { value: 'in',  label: 'in',   tip: '英制 NPS' },
  { value: 'mm',  label: 'mm',   tip: '公制' },
  { value: 'A',   label: 'JIS',  tip: 'JIS 10A/20A' },
  { value: 'DN',  label: 'DN',   tip: 'DN15/DN25' },
]

// 按 dn_mm 查找公称尺寸行
function findNominalByMm(mm) {
  if (mm == null) return null
  return nominalSizeRefs.value.find(r => r.dn_mm === Number(mm))
}

// 生成 DN 标签（根据当前选中的单位制）
function formatDnLabel(val) {
  if (val == null || val === '') return ''
  // 如果是字符串 (如 "40A"), 直接查 jis_a
  if (typeof val === 'string') {
    // 尝试查 jis_a
    const row = nominalSizeRefs.value.find(r => r.jis_a === val)
    if (!row) return val  // 找不到就原样返回
    const u = dnLabelUnit.value
    if (u === 'in')  return row.nps_in
    if (u === 'mm')  return `${row.dn_mm}`
    if (u === 'A')   return row.jis_a || ''
    if (u === 'DN')  return row.dn_label || ''
    return val
  }
  // 数值: 按 dn_mm 查
  const row = findNominalByMm(val)
  if (!row) return `${val}`
  const u = dnLabelUnit.value
  if (u === 'in')  return row.nps_in
  if (u === 'mm')  return `${row.dn_mm}`
  if (u === 'A')   return row.jis_a || ''
  if (u === 'DN')  return row.dn_label || ''
  return `${val}`
}

// 生成 Plug Size 标签（优先显示 in，附带 mm）
function formatPlugLabel(mm) {
  const row = findNominalByMm(mm)
  if (!row) return `${mm}`
  const u = dnLabelUnit.value
  if (u === 'in')  return `${row.nps_in} (${mm})`
  if (u === 'mm')  return `${mm}`
  if (u === 'A')   return `${row.jis_a || ''} (${mm})`
  if (u === 'DN')  return `${row.dn_label || ''} (${mm})`
  return `${mm}`
}

function onDnLabelUnitChange() {
  localStorage.setItem('dnLabelUnit', dnLabelUnit.value)
}

// ---------- 系列列表 ----------
const seriesList = ref([])
const loadingList = ref(false)
const keyword = ref('')

const PRODUCT_LINE_ORDER = ['GC系列套筒调节阀', 'GV系列调节阀', 'GA系列角阀', 'BT系列蝶阀', 'BC/BE系列球阀', 'BV系列球阀', 'GT系列闸阀', 'GZ系列自力式']
const PRODUCT_LINE_LABEL = {
  'GC系列套筒调节阀': '调节阀 · GC',
  'GV系列调节阀': '调节阀 · GV',
  'GA系列角阀': '调节阀 · GA',
  'BT系列蝶阀': '蝶阀 · BT',
  'BC/BE系列球阀': '球阀 · BC/BE',
  'BV系列球阀': '球阀 · BV',
  'GT系列闸阀': '闸阀 · GT',
  'GZ系列自力式': '自力式 · GZ',
}

const filteredSeries = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return seriesList.value
  return seriesList.value.filter(s =>
    s.series_code.toLowerCase().includes(kw) ||
    (s.series_name || '').toLowerCase().includes(kw)
  )
})

const groupedSeries = computed(() => {
  const groups = {}
  for (const s of filteredSeries.value) {
    const pl = s.product_line || '其它'
    if (!groups[pl]) groups[pl] = { name: PRODUCT_LINE_LABEL[pl] || pl, items: [], collapsed: false }
    groups[pl].items.push(s)
  }
  // 按 PRODUCT_LINE_ORDER 排序，未列入的放最后
  const ordered = []
  for (const pl of PRODUCT_LINE_ORDER) {
    if (groups[pl]) ordered.push(groups[pl])
  }
  for (const pl of Object.keys(groups)) {
    if (!PRODUCT_LINE_ORDER.includes(pl)) ordered.push(groups[pl])
  }
  // 组内按 series_code 排序
  for (const g of ordered) g.items.sort((a, b) => a.series_code.localeCompare(b.series_code))
  return ordered
})

async function loadSeriesList() {
  loadingList.value = true
  try {
    seriesList.value = await valveTypesApi.list()
    if (seriesList.value.length && !currentCode.value) {
      // 默认选第一个有 trim 数据的系列，否则选第一个
      const withTrim = ['GC120', 'GC210', 'BT120', 'BT210']
      const first = seriesList.value.find(s => withTrim.includes(s.series_code)) || seriesList.value[0]
      selectSeries(first.series_code)
    }
  } catch (e) { ElMessage.error(e.message) }
  finally { loadingList.value = false }
}

// ---------- 详情 ----------
const currentCode = ref('')
const current = ref(null)
const curves = ref([])
const trimSizes = ref([])
const loadingDetail = ref(false)
const verifyOpening = ref(60)

// ---------- 曲线选择 ----------
const curveOptions = ref({
  has_curve_data: false,
  filters: { pressure_ratings: [], plug_sizes: [], plug_sizes_by_pressure: {}, trim_types: [], trim_seat_types: [], flow_directions: [] },
  default_selection: { pressure_rating: '', plug_size: null, trim_type: 'EQ%', trim_seat_type: null, flow_direction: null },
  cascade: {},     // GV120 级联: { tst: { pressure_ratings, dn_ranges_by_pressure, plug_table } }
  table1: [],      // DN 级别 Table1 数据
  table2: [],      // Plug 级别 Table2 数据
})
const selTrimType = ref('EQ%')
const selPressure = ref('')
const selPlug = ref(null)
const selTrimSeatType = ref(null)  // Trim/Seat Type (GV120 有 Standard P-port/On/Off Q-port/Large Cv P-port)
const selFlowDirection = ref(null)  // FTC / FTO (GV120/GC 系列)
const selDn = ref(null)  // Nominal Valve Size (GV120 专用)
const selTrim = ref('')  // Nominal Trim Size (GC120/GC210 trim_inch)

// DN 变化时触发曲线加载 (plug 需用户手动选择或由初始化逻辑设置)
watch(selDn, () => {
  loadSelectedCurves()
})

// ===== 动态筛选器状态 =====
const filterValues = ref({})  // { filter_key: selected_value }
const filterChangeEvent = ref(0)  // 触发级联更新和查询的计数器

// 筛选器级联: 根据父值计算当前 filter 的可用 options
// 兼容对象型选项 {code, label} 或原始字符串
function formatOpt(opt, field) {
  if (opt == null) return ''
  if (typeof opt === 'object') {
    if (field === 'value') return opt.code ?? opt.value ?? String(opt)
    return opt.label ?? opt.code ?? String(opt)
  }
  return String(opt)
}

function getFilterOptions(fc) {
  // ==== 动态级联: 用 trimSizes (valve_cv_stk 数据) 作为唯一数据源 ====
  // 只要 trimSizes 已加载, 所有下拉选项都根据已选条件动态过滤
  // 映射: filter_key → valve_cv_stk 字段
  const FILTER_TO_CVSTK = {
    trim_type: 'trim_type',           // 阀内件形式 (Large Cv/Standard/ON-OFF)
    trim_seat_type: 'trim_type',      // 别名, 同上
    nominal_dn: 'dn_label',           // 阀门口径
    nominal_trim: 'trim_label',       // 阀芯尺寸
    trim_characteristics: 'flow_char', // 流量特性 (EQ%/Linear)
    pressure_rating: 'pressure_rating',
    seat_type: 'seat_type',
  }

  const fv = filterValues.value
  const myKey = fc.key
  const cvstkField = FILTER_TO_CVSTK[myKey]

  // 如果 trimSizes 有数据 且 当前 filter 能映射到 cv_stk 字段 → 走动态级联
  if (trimSizes.value.length > 0 && cvstkField) {
    // 收集"其他"已选条件 (排除当前 filter, 因为当前 filter 就是我们要计算选项的那个)
    const otherConditions = []
    for (const [fk, cvField] of Object.entries(FILTER_TO_CVSTK)) {
      if (fk === myKey) continue  // 排除自己
      const val = fv[fk]
      if (val !== undefined && val !== null && val !== '' && val !== 'all') {
        otherConditions.push({ field: cvField, val })
      }
    }

    // 额外兼容: 旧变量 selTrimSeatType 也作为 trim_type 条件
    if (myKey !== 'trim_type' && myKey !== 'trim_seat_type' && selTrimSeatType.value) {
      const already = otherConditions.some(c => c.field === 'trim_type')
      if (!already) otherConditions.push({ field: 'trim_type', val: selTrimSeatType.value })
    }
    if (myKey !== 'trim_characteristics' && selTrimType.value) {
      const already = otherConditions.some(c => c.field === 'flow_char')
      if (!already) otherConditions.push({ field: 'flow_char', val: selTrimType.value })
    }

    // 用其他条件过滤 trimSizes
    // pressure_rating 特殊处理: cv_stk 中多为 null 或 'all', 选中后仍保留这些行
    let rows = trimSizes.value
    for (const cond of otherConditions) {
      if (cond.field === 'pressure_rating') {
        rows = rows.filter(r => {
          const v = r[cond.field]
          return v === cond.val || v === null || v === 'all'
        })
      } else {
        rows = rows.filter(r => r[cond.field] === cond.val || r[cond.field] == null)
      }
    }

    // 从过滤后的 rows 提取当前字段的唯一值
    const uniqueVals = new Set()
    for (const r of rows) {
      const v = r[cvstkField]
      if (v !== null && v !== undefined && v !== '') {
        uniqueVals.add(v)
      }
    }
    let result = Array.from(uniqueVals)

    // 数值排序 (40, 50, 65...) vs 字符串排序
    result.sort((a, b) => {
      const na = Number(a), nb = Number(b)
      if (!isNaN(na) && !isNaN(nb)) return na - nb
      return String(a).localeCompare(String(b))
    })

    // Fallback: 动态结果为空时 (如 pressure_rating 在 cv_stk 中全为 null), 用后端静态 options
    if (result.length === 0 && fc.options && fc.options.length > 0) {
      return fc.options.map(o => formatOpt(o, 'value'))
    }

    return result.map(v => String(v))
  }

  // ==== fallback: 静态 options ====
  if (fc.source === 'hardcoded') return fc.options || []
  if (fc.dependent_on) {
    const parents = fc.dependent_on.split(',').map(p => p.trim())
    const allSet = parents.every(p => filterValues.value[p])
    if (allSet) {
      const key = parents.map(p => String(filterValues.value[p])).join('|')
      const byParent = fc.options_by_parent || {}
      return byParent[key] || []
    }
    return []
  }
  return fc.options || []
}

function onDynamicFilterChange(fc) {
  filterChangeEvent.value++
  const all = curveOptions.value.filter_configs || []

  // 动态级联模式 (trimSizes 已加载): 智能清除下游
  // 对于每个其他 filter Y: 用新选的 X 值重新计算 Y 的有效选项, 若 Y 当前值不在里面 → 清除
  if (trimSizes.value.length > 0) {
    // 临时同步一下, 让其他 filter 的 getFilterOptions 能用到新值
    // (但当前 fc 的值已经通过 v-model 更新到 filterValues 了)
    for (const f of all) {
      if (f.key === fc.key) continue
      const currentVal = filterValues.value[f.key]
      if (currentVal === undefined || currentVal === null || currentVal === '') continue
      const opts = getFilterOptions(f)
      if (!opts.includes(String(currentVal))) {
        filterValues.value[f.key] = null
      }
    }
  } else {
    // 静态级联模式: 只清除后端 dependent_on 里声明的下游
    for (const f of all) {
      if (f.dependent_on) {
        const deps = f.dependent_on.split(',').map(d => d.trim())
        if (deps.includes(fc.key) && filterValues.value[f.key] !== undefined) {
          filterValues.value[f.key] = null
        }
      }
    }
  }
  // 同步旧变量 (兼容 loadSelectedCurves)
  syncFilterValuesToOldVars()
  loadSelectedCurves()
}

function syncFilterValuesToOldVars() {
  const fv = filterValues.value
  if (fv.trim_characteristics !== undefined) selTrimType.value = fv.trim_characteristics
  if (fv.pressure_rating !== undefined) selPressure.value = fv.pressure_rating
  if (fv.plug_size !== undefined) selPlug.value = fv.plug_size
  if (fv.trim_type !== undefined) selTrimSeatType.value = fv.trim_type
  if (fv.trim_seat_type !== undefined) selTrimSeatType.value = fv.trim_seat_type
  if (fv.flow_direction !== undefined) selFlowDirection.value = fv.flow_direction
  if (fv.nominal_dn !== undefined) selDn.value = fv.nominal_dn
  if (fv.nominal_trim !== undefined) selTrim.value = fv.nominal_trim
  if (fv.opening_angle !== undefined) { /* no old var needed */ }
  if (fv.seat_type !== undefined) { /* no old var */ }
  if (fv.bore_type !== undefined) { /* no old var */ }
}

const selectedCurves = ref({})
const currentDp = ref(0)  // 当前阀芯尺寸 mm, 在 loadSelectedCurves 里设置

// 是否使用 GV120 级联模式 (有 cascade 数据)
const useCascade = computed(() => {
  const c = curveOptions.value.cascade
  return c && typeof c === 'object' && Object.keys(c).length > 0
})

// GV120 级联: 当前 TrimSeatType 可用的压力等级
const cascadePressures = computed(() => {
  if (!useCascade.value || !selTrimSeatType.value) return []
  return curveOptions.value.cascade[selTrimSeatType.value]?.pressure_ratings || []
})

// GV120 级联: 当前 (TrimSeatType + Pressure) 可用的 DN 列表
const cascadeDns = computed(() => {
  if (!useCascade.value || !selTrimSeatType.value || !selPressure.value) return []
  const ranges = curveOptions.value.cascade[selTrimSeatType.value]?.dn_ranges_by_pressure?.[selPressure.value] || []
  return ranges.map(r => ({
    label: formatDnLabel(r.dn_mm),
    dn_label: r.dn_label || (r.dn_mm ? `${r.dn_mm}A` : ''),
    dn_mm: r.dn_mm,
    stroke: r.stroke_mm,
  }))
})

// 当前选择下 DN 的 Plug Size 范围 (Table1)
const currentPlugRange = computed(() => {
  if (!useCascade.value || !selDn.value) return null
  const dn = cascadeDns.value.find(d => d.dn_label === selDn.value || Number(d.dn_mm) === Number(selDn.value))
  return dn ? { stroke: dn.stroke } : null
})

// 当前 TrimSeatType 的 Plug 级别表格 (Table2)
const currentPlugTable = computed(() => {
  if (!useCascade.value || !selTrimSeatType.value) return []
  return curveOptions.value.cascade[selTrimSeatType.value]?.plug_table || []
})

// 当前 DN 可用的 Plug Size 选项: Table1 范围 ∩ Table2 存在的 plug
const availablePlugs = computed(() => {
  if (!useCascade.value) {
    // 传统逻辑 (非 GV120)
    const byPres = curveOptions.value.filters.plug_sizes_by_pressure
    if (selPressure.value && byPres[selPressure.value]) {
      return byPres[selPressure.value]
    }
    return curveOptions.value.filters.plug_sizes || []
  }
  // GV120 级联逻辑: 直接从 currentPlugTable 取所有 plug_mm
  return currentPlugTable.value.map(p => p.plug_mm).filter(p => p != null)
})

function onTrimSeatTypeChange() {
  // 重设压力等级 (用级联第一个可用)
  const cps = cascadePressures.value
  if (cps.length && !cps.includes(selPressure.value)) {
    selPressure.value = cps[0]
  }
  onPressureChange()
}

function onPressureChange() {
  // 重设 DN
  const dns = cascadeDns.value
  if (dns.length && !dns.find(d => d.dn_label === selDn.value)) {
    selDn.value = dns[0].dn_label
  } else if (!dns.length) {
    selDn.value = null
  }
  onDnChange()
}

function onDnChange() {
  // watch(selDn) 会处理 loadSelectedCurves
}

async function loadSelectedCurves() {
  if (!currentCode.value) return
  if (!curveOptions.value.has_curve_data) return
  
  const fv = filterValues.value

  // 用户要求: 加载时不设默认值. 若未选择任何筛选条件, 不请求曲线, 清空已显示的曲线
  // 必须至少有 nominal_dn 或 trim_type 才查询 (否则后端会返回错误的 fallback 数据)
  const hasEssential = fv.nominal_dn || fv.trim_type || fv.trim_seat_type || selDn.value || selTrimSeatType.value
  if (!hasEssential) {
    selectedCurves.value = {}
    return
  }
  // DN 型系列 (BT/BE/BC): plug_size 从 nominal_dn 推导 (如 "80A" → 80)
  let plugSize = fv.plug_size || selPlug.value || 0
  const dnBasedSeries = ['BT110','BT120','BT210','BT210D','BT310','BT320','BT410','BT420',
                         'BE110','BE120','BC110','BC120','BV110','BV120','BV130','BV210']
  if (dnBasedSeries.includes(currentCode.value) && fv.nominal_dn) {
    const m = String(fv.nominal_dn).match(/(\d+)/)
    if (m) plugSize = parseFloat(m[1])
  }
  // GV/GC 系列: 无独立 plug_size 筛选器, 强制从 nominal_trim 推导 (如 "100A" → 100)
  // 避免残留其他系列的 selPlug 值
  const isGlobeSeries = currentCode.value.startsWith('GV') || currentCode.value.startsWith('GC')
  if (isGlobeSeries && fv.nominal_trim) {
    const m = String(fv.nominal_trim).match(/(\d+)/)
    if (m) plugSize = parseFloat(m[1])
  }
  // 保存当前阀芯尺寸供 calcFd 使用 (避免 filterValues 响应式时序问题)
  currentDp.value = plugSize
  // 直接把所有 filterValues 传到 API (后端已支持全部 key)
  const params = {
    pressure_rating: fv.pressure_rating || selPressure.value || '',
    plug_size: plugSize,
    nominal_dn: fv.nominal_dn || selDn.value || '',
    nominal_trim: fv.nominal_trim || selTrim.value || '',
    trim_type: fv.trim_type || fv.trim_seat_type || selTrimSeatType.value || '',
    trim_seat_type: fv.trim_seat_type || '',
    flow_direction: fv.flow_direction || selFlowDirection.value || '',
    opening_angle: fv.opening_angle || '',
    seat_type: fv.seat_type || '',
    trim_characteristics: fv.trim_characteristics || '',
  }
  // 注: Linear 特性由后端根据 trim_characteristics 自动切换 stroke_mode=linear,
  //     但 rated_cv 仍需 plug_size 查找, 所以不强制 plug_size=0
  
  try {
    const data = await valveTypesApi.curvesBySelection(currentCode.value, params)
    selectedCurves.value = data
  } catch (e) {
    console.error('加载曲线失败:', e)
  }
}

const categoryLabel = computed(() => ({
  globe: '调节阀', ball: '球阀', butterfly: '蝶阀', gate: '闸阀'
}[current.value?.valve_category] || current.value?.valve_category || '—'))
const categoryTagType = computed(() => ({
  globe: '', ball: 'warning', butterfly: 'success', gate: 'info'
}[current.value?.valve_category] || 'info'))

const flowDirectionText = computed(() => {
  // GC/GV 系列默认 FTC/FTO；蝶阀/球阀按 trim_option_types 推断
  const cat = current.value?.valve_category
  if (cat === 'globe') return 'FTC, FTO'
  if (cat === 'butterfly' || cat === 'ball') return 'Bidirectional'
  return '—'
})
const trimCharacteristicText = computed(() => {
  const t = current.value?.trim_option_types
  if (t) return t
  // 从 trim 数据推断
  if (trimSizes.value.length) {
    const chars = [...new Set(trimSizes.value.map(r => r.characteristic).filter(Boolean))]
    const charMap = { eq: 'EQ%', linear: 'Linear', quick_opening: 'Quick Opening' }
    if (chars.length) return chars.map(c => charMap[c] || c).join(', ')
  }
  return '—'
})

function curveByType(ft) {
  return curves.value.find(c => c.factor_type === ft)
}

// 返回某曲线的系数数组 (高次到低次)；eqcv 用 A6..A0，FL/Kc/Fd 用 P4..P0
function curveCoeffList(ft) {
  const c = curveByType(ft)
  if (!c) return []
  if (ft === 'eqcv') return [c.a6, c.a5, c.a4, c.a3, c.a2, c.a1, c.a0]
  return [c.p4, c.p3, c.p2, c.p1, c.p0]
}

async function selectSeries(code) {
  currentCode.value = code
  loadingDetail.value = true
  selectedCurves.value = {}
  try {
    const [detail, fc, ts, co] = await Promise.all([
      valveTypesApi.detail(code),
      valveTypesApi.factorCurves(code),
      valveTypesApi.trimSizes(code),
      valveTypesApi.curveOptions(code),
    ])
    current.value = detail
    curves.value = fc || []
    trimSizes.value = ts || []
    curveOptions.value = co || curveOptions.value

    // ========== 初始化动态筛选器 filterValues ==========
    // 用户要求: 加载时不设置任何默认值, 让用户手动选择
    // Table 1 显示该型号所有数据 (trimSizesFiltered 无 filter 时返回全量)
    filterValues.value = {}

    // 同步清空旧变量, 避免残留上一个系列的值
    selTrimType.value = ''
    selTrimSeatType.value = null
    selFlowDirection.value = null
    selPressure.value = ''
    selDn.value = null
    selTrim.value = ''
    selPlug.value = null

    // 同步 filterValues → old vars (此时为空)
    syncFilterValuesToOldVars()

    if (curveOptions.value.has_curve_data) {
      loadSelectedCurves()
    }
  } catch (e) { ElMessage.error(e.message) }
  finally { loadingDetail.value = false }
}

// ---------- Table 1 列显示: 按 valve_cv_stk 列顺序, 隐藏所有行均为空的列 ----------
const ALL_TRIM_COLS = [
  'dn_label',       // DN Label (始终显示)
  'trim_label',     // Trim Label (始终显示)
  'flow_char',      // Flow Characteristic
  'trim_type',      // Trim Type
  'pressure_rating',// Pressure Rating
  'seat_type',      // Seat Type
  'rated_cv',       // Rated Cv
  'stroke_unit',    // Stroke Unit (mm / °)
  'stroke_value',   // Stroke Value
  'plug_mm',        // Plug Size (mm)
  'stk_index',      // %Stk Index
  'kfd',            // Kfd
  'kfo',            // Kfo
  'kfb',            // Kfb
]

// ---------- Table 1 按筛选条件动态过滤 ----------
// 映射: 筛选器 → valve_cv_stk 表字段
//   selDn / nominal_dn       → dn_label
//   selTrim / nominal_trim   → trim_label
//   selTrimSeatType          → trim_type  (Large Cv / Standard / ON-OFF)
//   selTrimType              → flow_char  (EQ% / Linear)
//   selPressure              → pressure_rating  ('all' 或具体压力)
const trimSizesFiltered = computed(() => {
  if (!trimSizes.value.length) return []
  const fv = filterValues.value

  // 收集有效筛选条件 (空/undefined/'all' 不生效)
  const conditions = []

  // DN Label
  const dn = fv.nominal_dn || selDn.value
  if (dn && dn !== 'all') conditions.push({ key: 'dn_label', val: dn })

  // Trim Label
  const trim = fv.nominal_trim || selTrim.value
  if (trim && trim !== 'all') conditions.push({ key: 'trim_label', val: trim })

  // Trim Type (阀内件形式) — GV120/GC 系列用 trim_seat_type, 其他系列用 trim_type
  const gvTrimType = fv.trim_seat_type || fv.trim_type || selTrimSeatType.value || selTrimType.value
  if (gvTrimType && gvTrimType !== 'all') conditions.push({ key: 'trim_type', val: gvTrimType })

  // Flow Char (流量特性)
  const flowChar = fv.trim_characteristics || selTrimType.value
  if (flowChar && flowChar !== 'all' && flowChar !== 'EQ%' && flowChar !== 'Linear') {
    // 只有明确传了 EQ%/Linear 才过滤, 避免把默认值误加进来
  } else if (flowChar === 'EQ%' || flowChar === 'Linear') {
    conditions.push({ key: 'flow_char', val: flowChar })
  }

  // Pressure Rating
  const pres = fv.pressure_rating || selPressure.value
  if (pres && pres !== 'all') conditions.push({ key: 'pressure_rating', val: pres })

  // Seat Type (阀座形式)
  const seat = fv.seat_type
  if (seat && seat !== 'all') conditions.push({ key: 'seat_type', val: seat })

  // Opening Angle (开启角度) — BT 系列关键过滤条件 (60 Deg / 90 Deg 有不同 Cv)
  const openingAngle = fv.opening_angle
  if (openingAngle && openingAngle !== 'all') {
    // 后端 opening_angle options 的 code 是数字字符串 "60"/"90"，需匹配 stroke_value
    const strokeDeg = String(openingAngle).trim()
    // row.stroke_value 是数值, 转字符串后比较
    conditions.push({ key: 'stroke_value', val: Number(strokeDeg) || strokeDeg })
  }

  // 无有效条件 → 返回全部
  if (!conditions.length) return trimSizes.value

  // 过滤: 所有条件 AND 组合
  return trimSizes.value.filter(row => {
    return conditions.every(c => row[c.key] === c.val)
  })
})

const visibleTrimCols = computed(() => {
  const data = trimSizesFiltered.value  // ← 用过滤后的数据算可见列
  const result = []
  for (const key of ALL_TRIM_COLS) {
    if (key === 'dn_label' || key === 'trim_label') { result.push(key); continue }
    const hasValue = data.some(r => {
      const v = r[key]
      return v !== null && v !== undefined && v !== '' && v !== false
    })
    if (hasValue) result.push(key)
  }
  return result
})

function showCol(key) {
  return visibleTrimCols.value.includes(key)
}

// ---------- 多项式求值 (Horner 法) ----------
function getCurveCoeffs(ft) {
  const c = curveByType(ft)
  if (!c) return null
  if (ft === 'eqcv') {
    return [c.a6, c.a5, c.a4, c.a3, c.a2, c.a1, c.a0].filter(v => v != null)
  }
  return [c.p4, c.p3, c.p2, c.p1, c.p0].filter(v => v != null)
}

function evalPoly(coeffs, x) {
  if (!coeffs || !coeffs.length) return 0
  return coeffs.reduce((acc, c) => acc * x + (c || 0), 0)
}

// stroke_mode 显示标签 — 严格反映后端实际使用的 stroke_mode
const strokeModeLabel = computed(() => {
  const s = selectedCurves.value.stroke_mode
  const si = selectedCurves.value.stk_index
  const info = selectedCurves.value.stroke_info || {}
  if (s === 'ln_eqn') return `Ln Eqn (Fstk=${info.fstk})`
  if (s === 'linear') return 'Linear (φ=%Stk)'
  if (s === 'exp_formula') return `Exp 公式 (÷${info.opening_angle || info.divisor || 60}°)`
  if (s === 'poly_cv_div100') return '多项式 (Cv输入, ÷100)'
  if (s === 'poly_phi100_div100') return '多项式 (φ×100输入, ÷100)'
  if (s === 'poly_cv_div_angle' || s === 'poly_div60') return `多项式 (Cv输入, ÷${info.opening_angle || info.divisor || 60}°)`
  if (s === 'eq_index') return si ? `Eq#${si}` : '—'
  return '—'
})

function verifyValue(ft) {
  // 用户滑块调的是 %Stk，需要先反解 phi 再求值
  const stk = verifyOpening.value / 100
  const phi = solvePhiFromStk(stk)
  if (ft === 'eqcv') return evalEqcv(phi)
  if (ft === 'xt') {
    const fl = evalFactor('fl', phi)
    return 0.84 * fl * fl
  }
  if (ft === 'fd' && fdIsFormula()) return calcFd(phi)
  return evalFactor(ft, phi)
}

function verifyInBounds(ft) {
  const c = selectedCurves.value[ft]
  if (!c || c.value_min == null || c.value_max == null) return true
  const v = verifyValue(ft)
  if (v == null) return true
  return v >= c.value_min && v <= c.value_max
}

const VERIFY_FACTORS = [
  { key: 'fl', label: 'FL' },
  { key: 'kc', label: 'Kc' },
  { key: 'fd', label: 'Fd' },
]

const clampedValues = computed(() => {
  const out = []
  for (const t of VERIFY_FACTORS) {
    const c = selectedCurves.value[t.key]
    if (c && !verifyInBounds(t.key)) {
      out.push(`${t.label} = ${fmtNum(verifyValue(t.key), 4)}`)
    }
  }
  return out
})

// ---------- 双曲线图计算 ----------
// 正方形坐标: X轴和Y轴像素长度相同 (250px), 确保 Linear 曲线为 45°
const CHART_W = 250, CHART_X0 = 50, CHART_Y0 = 20
const CHART_Y_MAX = CHART_Y0 + CHART_W  // Y 轴长度 = X 轴长度 = 250
const CELL = CHART_W / 10  // 每 10% = 25px
const SVG_W = CHART_X0 + CHART_W + 20
const SVG_H = CHART_Y0 + CHART_W + 20

// ========== 重要 ==========
// Excel 中所有多项式都是 y = f(phi)，自变量 phi = Cv/Cvrated
//   - eq_index:     %Stk = A0 + A1*phi + A2*phi² + ... (6次多项式)
//   - ln_eqn:       %Stk = 1 + ln(phi) / ln(Fstk)     (GC120/GV410)
//   - linear:       %Stk = phi                         (GV110)
//   - exp_formula:  %Stk = Exp(A4*ln(phi)+A3*phi+A1/(phi+A2)+A0)/60  (BT110/BT120)
//   - poly_div60:   %Stk = (A5*phi^5+...+A0)/60        (BT210)
//   - FL/Kc/Fd:     Factor = P0 + P1*phi + P2*phi² + ... + P4*phi⁴

// 常数：系数全 0 且 value_min=value_max 时，返回 value_min
function isConstantCurve(c) {
  if (!c) return false
  const p = [c.p0, c.p1, c.p2, c.p3, c.p4]
  return p.every(v => !v) && c.value_min != null && c.value_max != null && c.value_min === c.value_max
}

// Fd 计算 (公式模式)
// - GV120 FTO: Fd = 1.13 * sqrt(17 * CvReq * FL) / (2 * Dp - (17 * CvReq * FL) / Dp)
// - GC210: Fd = (π/(4*20.8))^0.5 * KFd * ((KFo*φ)^-2 - KFb^-2)^0.25
function calcFd(phi) {
  if (selectedCurves.value.fd_mode === 'gc210_eqn') {
    return calcFdGC210(phi)
  }
  // GV120 FTO 模式: Fd = 1.13 * sqrt(17 * CvReq'd * FL) / (2*Dp - (17*CvReq'd*FL)/Dp)
  // CvReq'd = phi * rated_cv (当前开度对应的 Cv, 不是额定 Cv)
  const ratedCv = selectedCurves.value.stroke_info?.rated_cv
  const cvReq = phi * (ratedCv || 0)
  const fl = evalFactor('fl', phi)
  // Dp = 阀芯尺寸 mm: 优先用 loadSelectedCurves 中设置的 currentDp (与 API 的 plug_size 一致),
  // 兜底从 nominal_trim / selPlug / stroke_info.plug_mm 提取
  let dp = currentDp.value || 0
  if (!dp) {
    const trimStr = String(filterValues.value.nominal_trim || '')
    const dpMatch = trimStr.match(/\d+(\.\d+)?/)
    dp = dpMatch ? parseFloat(dpMatch[0]) : 0
  }
  if (!dp) {
    const plugStr = String(selPlug.value || '')
    const m2 = plugStr.match(/\d+(\.\d+)?/)
    dp = m2 ? parseFloat(m2[0]) : 0
  }
  if (!dp) {
    const plugMm = selectedCurves.value.stroke_info?.plug_mm
    dp = plugMm ? Number(plugMm) : 0
  }
  if (!cvReq || !fl || !dp) return null
  const inner = 17 * cvReq * fl
  if (inner <= 0) return null
  const numerator = 1.13 * Math.sqrt(inner)
  const denominator = 2 * dp - inner / dp
  if (denominator === 0) return null
  const fd_val = numerator / denominator
  return Math.min(1.0, fd_val)  // Fd 最大值钳制为 1
}

// Fd 是否使用公式计算 (FTO 模式 或 GC210 公式模式)
function fdIsFormula() {
  const mode = selectedCurves.value.fd_mode
  return mode === 'eqn' || mode === 'gc210_eqn'
}

// GC210 Fd 公式: Fd = (π/(4*20.8))^0.5 * KFd * ((KFo*φ)^-2 - KFb^-2)^0.25
function calcFdGC210(phi) {
  const fd = selectedCurves.value.fd
  if (!fd || !fd.kfo || !fd.kfb || !fd.kfd) return null
  const kfo = fd.kfo
  const kfb = fd.kfb
  const kfd = fd.kfd
  if (phi <= 0) return null
  const term = 1 / Math.pow(kfo * phi, 2) - 1 / Math.pow(kfb, 2)
  if (term <= 0) return null
  const fd_val = Math.sqrt(Math.PI / (4 * 20.8)) * kfd * Math.pow(term, 0.25)
  return Math.min(1.0, fd_val)  // Fd 最大值钳制为 1
}

// FL/Kc/Fd 多项式: Factor = f(phi)
function evalFactor(factorType, phi) {
  const c = selectedCurves.value[factorType]
  if (!c) return 0
  // 常数曲线
  if (isConstantCurve(c)) return c.value_min
  let v = [c.p4, c.p3, c.p2, c.p1, c.p0]
    .reduce((acc, val) => acc * phi + (val || 0), 0)
  // 钳制到 [value_min, value_max]
  if (c.value_min != null) v = Math.max(v, c.value_min)
  if (c.value_max != null) v = Math.min(v, c.value_max)
  return v
}

// Eq% 多项式: %Stk = f(phi), 输出钳制到 [0, 1]
// 注意: stroke_mode 由后端根据系列/尺寸决定，前端不要用 trim_characteristics 覆盖它！
//       Excel 中行程曲线与 EQ%/Linear 流量特性无关。
function evalEqcv(phi) {
  if (phi <= 0) return 0
  if (phi >= 1) return 1

  const mode = selectedCurves.value.stroke_mode
  const info = selectedCurves.value.stroke_info || {}
  const ratedCv = info.rated_cv || 100
  const cvVal = phi * ratedCv  // 实际 Cv = Cvrated * phi
  
  switch (mode) {
    case 'linear':
      return phi
    
    case 'ln_eqn': {
      const fstk = info.fstk || 50
      const stk = 1 + Math.log(phi) / Math.log(fstk)
      return Math.max(0, Math.min(1, stk))
    }
    
    case 'exp_formula': {
      // %Stk = Exp(A4*ln(Cv) + A3*Cv + A1/(Cv + A2) + A0) / opening_angle
      // 系数从 eqcv 曲线获取 (a0=A0, a1=A1, a2=A2, a3=A3, a4=A4)
      const c = selectedCurves.value.eqcv
      const a0 = (c?.a0) || 0, a1 = (c?.a1) || 0, a2 = (c?.a2) || 0
      const a3 = (c?.a3) || 0, a4 = (c?.a4) || 0
      const divisor = info.opening_angle || info.divisor || 60
      const lnCv = Math.log(cvVal)
      let arg = a4 * lnCv + a3 * cvVal + a1 / (cvVal + a2) + a0
      if (arg > 700) arg = 700
      if (arg < -700) arg = -700
      const stk = Math.exp(arg) / divisor
      return Math.max(0, Math.min(1, stk))
    }
    
    case 'poly_cv_div100': {
      // GV120非Standard: %Stk = (A4*Cv^4 + A3*Cv^3 + A2*Cv^2 + A1*Cv + A0) / 100
      const c = selectedCurves.value.eqcv
      if (!c) return 0
      const a0 = c.a0 || 0, a1 = c.a1 || 0, a2 = c.a2 || 0
      const a3 = c.a3 || 0, a4 = c.a4 || 0
      let stk = a4*Math.pow(cvVal,4) + a3*Math.pow(cvVal,3) + a2*Math.pow(cvVal,2) + a1*cvVal + a0
      stk = stk / 100
      return Math.max(0, Math.min(1, stk))
    }
    
    case 'poly_phi100_div100': {
      // BE120: %Stk = (A4*(phi*100)^4 + ... + A0) / 100, clamp到1
      const c = selectedCurves.value.eqcv
      if (!c) return 0
      const a0 = c.a0 || 0, a1 = c.a1 || 0, a2 = c.a2 || 0
      const a3 = c.a3 || 0, a4 = c.a4 || 0, a5 = c.a5 || 0
      const x = phi * 100
      let stk = a5*Math.pow(x,5) + a4*Math.pow(x,4) + a3*Math.pow(x,3) + a2*Math.pow(x,2) + a1*x + a0
      stk = stk / 100
      return Math.max(0, Math.min(1, stk))
    }
    
    case 'poly_cv_div_angle':
    case 'poly_div60': {
      // BT210: %Stk = (A4*Cv^4 + ... + A0) / opening_angle
      const c = selectedCurves.value.eqcv
      if (!c) return 0
      const a0 = c.a0 || 0, a1 = c.a1 || 0, a2 = c.a2 || 0
      const a3 = c.a3 || 0, a4 = c.a4 || 0, a5 = c.a5 || 0
      const divisor = info.opening_angle || info.divisor || 60
      let stk = a5*Math.pow(cvVal,5) + a4*Math.pow(cvVal,4) + a3*Math.pow(cvVal,3) + a2*Math.pow(cvVal,2) + a1*cvVal + a0
      stk = stk / divisor
      return Math.max(0, Math.min(1, stk))
    }
    
    case 'eq_index':
    default: {
      const c = selectedCurves.value.eqcv
      if (!c) return 0
      // %Stk = A0 + A1*phi + A2*phi² + ... + A6*phi^6
      let stk = [c.a6, c.a5, c.a4, c.a3, c.a2, c.a1, c.a0]
        .reduce((acc, v) => acc * phi + (v || 0), 0)
      return Math.max(0, Math.min(1, stk))
    }
  }
}

// 反解 Eq%: 给定 %Stk，求 phi (Cv/Cvrated)
// 因为多项式是 stk = f(phi)，求 cv vs travel 需要反函数
// 仅当后端 stroke_mode === 'linear' 时直接返回 (GV110 等系列本身就是直线特性)
function solvePhiFromStk(targetStk) {
  const mode = selectedCurves.value.stroke_mode
  if (mode === 'linear') return targetStk
  if (targetStk <= 0) return 0
  if (targetStk >= 1) return 1
  // 二分法求解 f(phi) = targetStk
  let lo = 0, hi = 1
  for (let i = 0; i < 80; i++) {
    const mid = (lo + hi) / 2
    if (evalEqcv(mid) < targetStk) lo = mid
    else hi = mid
  }
  return (lo + hi) / 2
}

// 左图: Cv versus Travel
// X 轴 = %Stk, Y 轴 = Cv/Cvrated (phi)
// 给定 stk → phi = solvePhiFromStk(stk)
const cvTravelPoints = computed(() => {
  const pts = []
  for (let i = 1; i <= 100; i++) {
    const stk = i / 100
    const phi = solvePhiFromStk(stk)
    const y = Math.max(0, Math.min(1, phi)) * 100
    const sx = CHART_X0 + stk * CHART_W
    const sy = CHART_Y_MAX - (y / 100) * (CHART_Y_MAX - CHART_Y0)
    pts.push(`${sx},${sy}`)
  }
  return pts.join(' ')
})

function cvTravelY(stk) {
  const phi = solvePhiFromStk(stk)
  const y = Math.max(0, Math.min(1, phi)) * 100
  return CHART_Y_MAX - (y / 100) * (CHART_Y_MAX - CHART_Y0)
}

// 右图: Sizing Indices versus % Rated Cv
// x轴: 0-100% (额定Cv百分比), y轴: 0-1.0
// FL/Kc/Fd 曲线直接用多项式; xT = 0.84 * FL^2
function sizingPoints(factorType) {
  const pts = []
  for (let i = 1; i <= 100; i++) {
    const x = i / 100
    let v
    if (factorType === 'xt') {
      const fl = evalFactor('fl', x)
      v = 0.84 * fl * fl
    } else if (factorType === 'fd' && fdIsFormula()) {
      v = calcFd(x) ?? 0
    } else {
      v = evalFactor(factorType, x)
    }
    v = Math.max(0, Math.min(1.0, v))
    const sx = CHART_X0 + x * CHART_W
    const sy = CHART_Y_MAX - v * (CHART_Y_MAX - CHART_Y0)
    pts.push(`${sx},${sy}`)
  }
  return pts.join(' ')
}

// ---------- 特征值表 (Excel Table 风格) ----------
// Cv/Cvrated (phi) 序列，参考 Excel: 0.5,1,2,4,8,16 然后 35-100 每5
const PHI_SEQ = [0.5, 1, 2, 4, 8, 16, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]

// 特征值表数据: 给定 phi, 直接用多项式计算 stk 和 factors
const featureTable = computed(() => {
  if (!selectedCurves.value.fl) return []
  const isFdFormula = fdIsFormula()
  return PHI_SEQ.map(phiPct => {
    const phi = phiPct / 100
    const stk = evalEqcv(phi) * 100  // 转百分比
    const fl = evalFactor('fl', phi)
    const kc = evalFactor('kc', phi)
    const fd = isFdFormula ? (calcFd(phi) ?? 0) : evalFactor('fd', phi)
    const xt = 0.84 * fl * fl
    return {
      phi: phiPct,
      stk,
      fl,
      xt,
      kc,
      fd,
    }
  })
})

// ---------- 工具 ----------
function fmtNum(v, d = 4) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  if (Number.isInteger(n)) return String(n)
  return n.toFixed(d).replace(/\.?0+$/, m => m.startsWith('.') ? '' : m)
}

function verifyStatus(ft) {
  if (!selectedCurves.value[ft]) {
    if (ft === 'fd' && fdIsFormula()) return 'status-ok'
    return 'status-none'
  }
  if (ft === 'eqcv') return 'status-info'
  return verifyInBounds(ft) ? 'status-ok' : 'status-bad'
}

onMounted(async () => {
  loadSeriesList()
  try {
    const res = await nominalSizesApi.list()
    nominalSizeRefs.value = res.items || []
  } catch (e) {
    console.warn('加载公称尺寸对照表失败:', e.message)
  }
})
</script>

<style scoped>
.vt-page { height: calc(100vh - 72px); }
.vt-layout { display: flex; gap: 12px; height: 100%; }

/* ============ 左栏 ============ */
.vt-sidebar {
  width: 260px; flex-shrink: 0; background: #fff; border-radius: 6px;
  display: flex; flex-direction: column; overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
.sidebar-header {
  height: 44px; display: flex; align-items: center; gap: 8px;
  padding: 0 14px; background: #2c3e50; color: #fff; font-weight: 600;
  font-size: 14px; flex-shrink: 0;
}
.sidebar-search { padding: 10px; border-bottom: 1px solid #eef0f3; flex-shrink: 0; }
.sidebar-tree { flex: 1; overflow-y: auto; padding: 4px 0; }

.series-group { margin-bottom: 2px; }
.group-title {
  display: flex; align-items: center; gap: 6px; padding: 8px 12px;
  font-size: 12px; font-weight: 600; color: #5a6a7a; cursor: pointer;
  background: #f7f9fc; user-select: none;
}
.group-title:hover { background: #eef2f7; }
.group-name { flex: 1; }
.group-count {
  background: #e4e7ed; color: #5a6a7a; padding: 1px 7px;
  border-radius: 9px; font-size: 11px;
}
.group-items { padding: 2px 0; }
.series-item {
  display: flex; align-items: center; gap: 8px; padding: 7px 14px 7px 24px;
  cursor: pointer; font-size: 12px; border-left: 3px solid transparent;
  transition: all .15s;
}
.series-item:hover { background: #f0f5ff; }
.series-item.active { background: #e6f1ff; border-left-color: #409eff; }
.series-code { font-weight: 600; color: #303133; min-width: 56px; font-family: Consolas, monospace; }
.series-name { color: #5a6a7a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }

/* ============ 右栏 ============ */
.vt-detail {
  flex: 1; overflow-y: auto; padding-right: 4px;
  display: flex; flex-direction: column; gap: 12px;
}

/* Excel 标题条 */
.excel-title-bar {
  background: #2c3e50; color: #fff; padding: 12px 18px;
  border-radius: 6px; font-family: Arial, sans-serif;
  display: flex; align-items: center; gap: 6px; font-size: 14px;
  box-shadow: 0 2px 6px rgba(0,0,0,.1);
}
.etb-code { font-weight: 700; font-size: 15px; letter-spacing: 1px; }
.etb-sep { opacity: .6; }
.etb-name { font-weight: 500; flex: 1; }
.etb-tag { margin-left: 8px; }

/* Excel 卡片 */
.excel-card {
  background: #fff; border-radius: 6px; padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
.card-title {
  font-size: 14px; font-weight: 600; color: #303133;
  margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid #2c3e50;
  display: flex; align-items: center; gap: 8px;
  font-family: Arial, sans-serif;
}
.card-title::before {
  content: ''; width: 4px; height: 14px; background: #409eff; border-radius: 2px;
}
.card-sub { font-size: 12px; color: #909399; font-weight: 400; margin-left: 8px; }
.card-sub.warn { color: #e6a23c; }

/* 默认系数 */
.coef-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
}
.coef-tile {
  background: #f7f9fc; border-left: 3px solid #409eff;
  padding: 10px 14px; border-radius: 4px;
}
.coef-label { font-size: 12px; color: #909399; font-family: Arial, sans-serif; }
.coef-value { font-size: 18px; font-weight: 600; color: #303133; margin-top: 4px; }
.coef-value.small { font-size: 13px; font-family: Consolas, monospace; word-break: break-all; }

/* 系数曲线 - 选择器 */
.curve-selectors {
  display: flex; gap: 16px; align-items: flex-end; flex-wrap: wrap;
  margin-bottom: 16px; padding: 12px; background: #f7f9fc; border-radius: 4px;
}
.sel-item { display: flex; flex-direction: column; gap: 4px; }
.sel-item label { font-size: 11px; color: #5a6a7a; font-weight: 600; }
.sel-row { display: flex; gap: 6px; align-items: center; }
.unit-toggle { width: 56px !important; }
.unit-toggle .el-select__wrapper { min-height: 24px !important; padding: 0 4px !important; }
.unit-toggle .el-select__placeholder,
.unit-toggle .el-select__selected-item { font-size: 11px !important; }
.xt-result { margin-left: auto; }
.xt-value {
  font-size: 20px; font-weight: 700; color: #e17055;
  font-family: Consolas, monospace;
}
.xt-formula { font-size: 11px; color: #909399; margin-left: 8px; }

/* GV120 Table1/Table2 速览卡片 */
.gv120-tables { display: flex; gap: 12px; margin: 12px 0; }
.gv-table {
  flex: 1; min-width: 200px; max-width: 260px;
  background: #f8f9fb; border: 1px solid #e4e7ed; border-radius: 6px;
  padding: 10px 14px;
}
.gv-table.table1 { border-left: 3px solid #409eff; }
.gv-table.table2 { border-left: 3px solid #67c23a; }
.gv-tab-title { font-size: 12px; font-weight: 600; color: #606266; margin-bottom: 6px; border-bottom: 1px dashed #dcdfe6; padding-bottom: 4px; }
.gv-tab-row { display: flex; justify-content: space-between; font-size: 12px; padding: 2px 0; }
.gv-tab-row span { color: #909399; }
.gv-tab-row b { color: #303133; font-weight: 600; }

/* 双曲线图 + 系数表 */
.charts-row { display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-start; }
.chart-box { flex: 0 0 auto; width: 340px; position: relative; }
.chart-title {
  font-size: 16px; font-weight: 700; text-align: center;
  margin-bottom: 8px; color: #2c3e50; font-family: Arial, sans-serif;
}
.chart-svg {
  width: 100%; height: 310px; background: #fff;
  border: 1px solid #e4e7ed; border-radius: 4px;
}
.chart-svg .grid line { stroke: #e4e7ed; stroke-width: 0.5; }
.chart-svg .axis { stroke: #5a6a7a; stroke-width: 1; }
.chart-svg .curve-line { stroke: #2980b9; stroke-width: 2; }
.chart-svg .curve-marker { fill: #f56c6c; stroke: #fff; stroke-width: 1.5; }
.chart-svg .sizing-fl { stroke: #2c3e50; stroke-width: 2.5; }
.chart-svg .sizing-xt { stroke: #e74c3c; stroke-width: 2; }
.chart-svg .sizing-kc { stroke: #3498db; stroke-width: 2; }
.chart-svg .sizing-fd { stroke: #27ae60; stroke-width: 2; }
.chart-axis-label {
  text-align: center; font-size: 12px; color: #5a6a7a;
  margin-top: 4px; font-weight: 600;
}
.chart-y-label {
  position: absolute; left: -8px; top: 50%; transform: rotate(-90deg) translateX(50%);
  font-size: 11px; color: #5a6a7a; font-weight: 600;
  transform-origin: left center; white-space: nowrap;
}
.chart-legend {
  display: flex; justify-content: center; gap: 16px; margin-top: 8px;
  font-size: 12px; font-weight: 600;
}
.chart-legend .lg { display: flex; align-items: center; gap: 4px; }
.chart-legend .lg::before {
  content: ''; display: inline-block; width: 16px; height: 3px;
}
.lg-fl::before { background: #2c3e50; }
.lg-xt::before { background: #e74c3c; }
.lg-kc::before { background: #3498db; }
.lg-fd::before { background: #27ae60; }

/* 图表行: 两个图表 + 右侧特征值表 */
.charts-row { display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-start; }
.feature-table-wrap { flex: 0 0 auto; }
/* 下方: 多项式系数表 */
.coef-tables { margin-top: 12px; }
.curve-coef-table.small { font-size: 11px; }
.curve-coef-table.small th, .curve-coef-table.small td { padding: 4px 10px; }

/* 特征值表 */
.feature-table-wrap { }
.feature-table-title {
  font-size: 12px; font-weight: 600; color: #2c3e50;
  margin-bottom: 6px; font-family: Arial, sans-serif;
}
.feature-table {
  border-collapse: collapse; font-size: 11px;
  font-family: Consolas, monospace;
}
.feature-table th, .feature-table td {
  border: 1px solid #d0d4dc; padding: 3px 8px; text-align: right;
}
.feature-table th {
  background: #2c3e50; color: #fff; font-weight: 600; text-align: center;
}
.feature-table tbody td { background: #fff; color: #303133; }
.feature-table tbody tr:nth-child(even) td { background: #f7f9fc; }
.feature-table td:first-child { text-align: center; color: #2980b9; font-weight: 600; }

/* 额定容量表 (Excel Table 1 风格) */
.trim-table-wrap { overflow-x: auto; }
.trim-table {
  width: max-content;
  min-width: 100%;
  border-collapse: collapse; font-size: 12px;
  font-family: Arial, sans-serif;
}
.trim-table th, .trim-table td {
  border: 1px solid #d0d4dc; padding: 6px 8px; text-align: center;
}
.trim-table th {
  background: #2c3e50; color: #fff; font-weight: 600; font-size: 11px;
  line-height: 1.3;
}
.trim-table tbody td { background: #fff; color: #303133; }
.trim-table tbody tr:nth-child(even) td { background: #fafbfc; }
.trim-table .merged-row td { border-top: 1px dashed #e4e7ed; }
.trim-table .cell-pressure {
  background: #e8edf3 !important; font-weight: 600; vertical-align: middle;
  writing-mode: horizontal-tb; color: #2c3e50;
}
.trim-table .cell-cv { color: #e17055; font-weight: 700; font-family: Consolas, monospace; }
.trim-table .cell-remark { color: #909399; font-size: 11px; }
.group-divider td { height: 4px; background: #2c3e50 !important; padding: 0; border: none; }

.col-pressure { width: 90px; }
.col-dn { width: 120px; }
.col-trim { width: 160px; }
.col-trimmm, .col-plug, .col-stroke { width: 70px; }
.col-cv { width: 80px; }
.col-remark { width: 110px; }

/* 校核卡片 */
.verify-card { border-left: 4px solid #e6a23c; }
.verify-controls {
  display: flex; align-items: center; gap: 8px; margin-bottom: 14px;
  background: #f7f9fc; padding: 12px 16px; border-radius: 4px;
}
.vc-label { font-size: 13px; font-weight: 600; color: #303133; }
.verify-results {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}
.vr-item {
  background: #f7f9fc; border-left: 3px solid #909399;
  padding: 10px 14px; border-radius: 4px;
}
.vr-item.status-ok { border-left-color: #67c23a; }
.vr-item.status-bad { border-left-color: #f56c6c; background: #fef0f0; }
.vr-item.status-info { border-left-color: #409eff; }
.vr-item.status-none { opacity: .5; }
.vr-label { font-size: 12px; color: #5a6a7a; font-weight: 600; }
.vr-value { font-size: 18px; font-weight: 700; color: #303133; font-family: Consolas, monospace; margin: 4px 0; }
.vr-range { font-size: 11px; color: #909399; font-family: Consolas, monospace; }
.vr-status { font-size: 12px; margin-top: 4px; }
.status-ok { color: #67c23a; }
.status-bad { color: #f56c6c; font-weight: 600; }
.status-info { color: #409eff; }
.status-miss { color: #909399; }
.verify-note {
  margin-top: 12px; padding: 8px 12px; background: #fef0f0;
  border-left: 3px solid #f56c6c; border-radius: 4px;
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: #f56c6c;
}
</style>
