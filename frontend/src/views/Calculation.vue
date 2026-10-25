<template>
  <div v-loading="loading" class="calc-page">
    <!-- 顶部：位号信息 + 版本管理 + 操作 -->
    <div class="calc-header">
      <div class="header-left">
        <el-tag type="primary" effect="dark" class="tag-tag">{{ valve?.tag_no }}</el-tag>
        <span class="valve-name">{{ valve?.valve_name || valve?.service }}</span>
        <span class="muted">{{ valve?.valve_type }} · {{ valve?.line_size }}</span>
      </div>
      <div class="header-right">
        <span class="muted">版本</span>
        <el-select v-model="currentCid" placeholder="选择版本" size="small" style="width:200px" @change="onVersionChange">
          <el-option v-for="c in calcs" :key="c.id" :label="`V${c.version_no} ${c.version_label||''} ${c.is_current?'(当前)':''}`" :value="c.id" />
        </el-select>
        <el-button size="small" @click="newVersion" plain><el-icon><Plus /></el-icon>新建</el-button>
        <el-button size="small" v-if="calc && !calc.is_current" @click="setCurrent" plain>设为当前</el-button>
        <el-tag v-if="calc" size="small" :type="calc.status==='已计算'?'success':'info'">{{ calc.status }}</el-tag>
        <el-tag v-if="calc" size="small" type="warning" effect="plain">{{ calc.calc_standard }}</el-tag>
        <el-button type="success" size="small" @click="runCalc" :loading="running"><el-icon><VideoPlay /></el-icon>执行计算</el-button>
      </div>
    </div>

    <!-- 主体：双栏布局 -->
    <div class="calc-body" v-if="calc">
      <!-- 左栏：表单区 -->
      <div class="col-form">
        <!-- 卡片 0：设计数据（管道数据，阀前/阀后分栏） -->
        <div class="section-card">
          <div class="section-title">设计数据 <span class="muted">管道数据</span></div>
          <!-- 表头：阀前 | 阀后 -->
          <div class="form-row pipe-header-row">
            <label style="min-width:110px"></label>
            <div class="pipe-col-label">阀前</div>
            <div class="pipe-col-label">阀后</div>
            <div class="pipe-col-sync"></div>
          </div>
          <!-- 管道规格 (lookup_key) -->
          <div class="form-row">
            <label>管道规格</label>
            <el-select v-model="config.pipe_spec_front" size="small" filterable placeholder="选择管道规格" style="width:100%" @change="onPipeSpecChange('front')">
              <el-option v-for="p in pipeDataList" :key="p.id" :label="p.lookup_key" :value="p.lookup_key" />
            </el-select>
            <el-select v-model="config.pipe_spec_back" size="small" filterable placeholder="同前" clearable style="width:100%" @change="onPipeSpecChange('back')">
              <el-option v-for="p in pipeDataList" :key="p.id" :label="p.lookup_key" :value="p.lookup_key" />
            </el-select>
            <el-button link size="small" type="primary" title="同步阀后为阀前" @click="syncBackToFront('pipe_spec_front','pipe_spec_back')">⇄</el-button>
          </div>
          <!-- 管道尺寸 (nps_label, 由管道规格自动填充) -->
          <div class="form-row">
            <label>管道尺寸</label>
            <el-input v-model="config.pipe_size_front" size="small" placeholder="如 89×4 / DN80" />
            <el-input v-model="config.pipe_size_back" size="small" placeholder="同前" />
            <el-button link size="small" type="primary" title="同步阀后为阀前" @click="syncBackToFront('pipe_size_front','pipe_size_back')">⇄</el-button>
          </div>
          <!-- 管道 SCH -->
          <div class="form-row">
            <label>管道 SCH</label>
            <el-select v-model="config.sch_front" size="small" placeholder="选择" style="width:100%">
              <el-option v-for="o in PIPE_SCH_DATA" :key="o" :label="o" :value="o" />
            </el-select>
            <el-select v-model="config.sch_back" size="small" placeholder="同前" clearable style="width:100%">
              <el-option v-for="o in PIPE_SCH_DATA" :key="o" :label="o" :value="o" />
            </el-select>
            <el-button link size="small" type="primary" title="同步阀后为阀前" @click="syncBackToFront('sch_front','sch_back')">⇄</el-button>
          </div>
          <!-- 管道壁厚 -->
          <div class="form-row">
            <label>管道壁厚</label>
            <el-input v-model="config.pipe_wall_front" size="small" placeholder="mm" />
            <el-input v-model="config.pipe_wall_back" size="small" placeholder="同前" />
            <el-button link size="small" type="primary" title="同步阀后为阀前" @click="syncBackToFront('pipe_wall_front','pipe_wall_back')">⇄</el-button>
          </div>
          <!-- 推荐 SCH (ASME B31.3) -->
          <div class="form-row">
            <label></label>
            <el-button size="small" plain type="primary" :disabled="!config.pipe_spec_front" @click="openSchRecommend">推荐 SCH (ASME B31.3)</el-button>
          </div>
          <!-- 管道材质 -->
          <div class="form-row">
            <label>管道材质</label>
            <el-input v-model="config.pipe_material_front" size="small" placeholder="如 Q235A / 304" />
            <el-input v-model="config.pipe_material_back" size="small" placeholder="同前" />
            <el-button link size="small" type="primary" title="同步阀后为阀前" @click="syncBackToFront('pipe_material_front','pipe_material_back')">⇄</el-button>
          </div>
          <!-- 设计压力 (不分前后) -->
          <div class="form-row">
            <label>设计压力</label>
            <el-input-number v-model="config.design_pressure" :min="0" :precision="3" size="small" :controls="false" /><span class="unit-inline unit-design">MPa(G)</span>
          </div>
          <!-- 设计温度 -->
          <div class="form-row">
            <label>设计温度</label>
            <el-input-number v-model="config.design_temp" size="small" :controls="false" /><span class="unit-inline unit-design">℃</span>
          </div>
          <!-- 关闭压差 -->
          <div class="form-row">
            <label>关闭压差</label>
            <el-input-number v-model="config.close_dp" :min="0" :precision="3" size="small" :controls="false" /><span class="unit-inline unit-design">MPa</span>
          </div>
        </div>

        <!-- 卡片 1：接管附件 -->
        <div class="section-card">
          <div class="section-title">接管附件 <span class="muted">手工选择</span></div>
          <!-- 表头：阀前 | 阀后 -->
          <div class="form-row pipe-header-row">
            <label style="min-width:110px"></label>
            <div class="pipe-col-label">阀前</div>
            <div class="pipe-col-label">阀后</div>
            <div class="pipe-col-sync"></div>
          </div>
          <!-- 连接形式 -->
          <div class="form-row">
            <label>连接形式</label>
            <el-select v-model="config.connection_type_front" size="small" placeholder="选择" style="width:100%">
              <el-option v-for="o in COMMON_DATA.connection_types" :key="o" :label="o" :value="o" />
            </el-select>
            <el-select v-model="config.connection_type_back" size="small" placeholder="同前" clearable style="width:100%">
              <el-option v-for="o in COMMON_DATA.connection_types" :key="o" :label="o" :value="o" />
            </el-select>
            <el-button link size="small" type="primary" @click="syncBackToFront('connection_type_front','connection_type_back')">⇄</el-button>
          </div>
          <!-- 密封面形式 -->
          <div class="form-row">
            <label>密封面形式</label>
            <el-select v-model="config.face_type_front" size="small" placeholder="选择" style="width:100%">
              <el-option v-for="o in COMMON_DATA.face_types" :key="o" :label="o" :value="o" />
            </el-select>
            <el-select v-model="config.face_type_back" size="small" placeholder="同前" clearable style="width:100%">
              <el-option v-for="o in COMMON_DATA.face_types" :key="o" :label="o" :value="o" />
            </el-select>
            <el-button link size="small" type="primary" @click="syncBackToFront('face_type_front','face_type_back')">⇄</el-button>
          </div>
          <!-- 法兰标准 -->
          <div class="form-row">
            <label>法兰标准</label>
            <el-select v-model="config.flange_standard_front" size="small" placeholder="选择" style="width:100%">
              <el-option v-for="o in COMMON_DATA.flange_standards" :key="o" :label="o" :value="o" />
            </el-select>
            <el-select v-model="config.flange_standard_back" size="small" placeholder="同前" clearable style="width:100%">
              <el-option v-for="o in COMMON_DATA.flange_standards" :key="o" :label="o" :value="o" />
            </el-select>
            <el-button link size="small" type="primary" @click="syncBackToFront('flange_standard_front','flange_standard_back')">⇄</el-button>
          </div>
          <!-- 接管附件 -->
          <div class="form-row">
            <label>接管附件</label>
            <el-input v-model="config.pipe_accessory_front" size="small" placeholder="如 弯管 / 直管段" />
            <el-input v-model="config.pipe_accessory_back" size="small" placeholder="同前" />
            <el-button link size="small" type="primary" @click="syncBackToFront('pipe_accessory_front','pipe_accessory_back')">⇄</el-button>
          </div>
          <!-- 接管材质 -->
          <div class="form-row">
            <label>接管材质</label>
            <el-input v-model="config.pipe_material_2_front" size="small" placeholder="如 20# / 304" />
            <el-input v-model="config.pipe_material_2_back" size="small" placeholder="同前" />
            <el-button link size="small" type="primary" @click="syncBackToFront('pipe_material_2_front','pipe_material_2_back')">⇄</el-button>
          </div>
        </div>

        <!-- 卡片 2：阀门计算数据 -->
        <div class="section-card">
          <div class="section-title">阀门计算数据 <span class="muted">手工选择</span></div>
          <div class="form-grid">
            <div class="form-row full-width">
              <label>阀门型号</label>
              <el-select v-model="config.valve_style" size="small" filterable placeholder="选择KELK阀门系列" style="width:100%" @change="onValveStyleChange">
                <el-option-group label="套筒/单座调节阀 (Globe)">
                  <el-option v-for="v in valveTypes.filter(v => v.valve_category === 'globe')" :key="v.series_code" :label="`${v.series_code} ${v.series_name}`" :value="v.series_code" />
                </el-option-group>
                <el-option-group label="球阀 (Ball)">
                  <el-option v-for="v in valveTypes.filter(v => v.valve_category === 'ball')" :key="v.series_code" :label="`${v.series_code} ${v.series_name}`" :value="v.series_code" />
                </el-option-group>
                <el-option-group label="蝶阀 (Butterfly)">
                  <el-option v-for="v in valveTypes.filter(v => v.valve_category === 'butterfly')" :key="v.series_code" :label="`${v.series_code} ${v.series_name}`" :value="v.series_code" />
                </el-option-group>
              </el-select>
            </div>
            <!-- 阀门口径 (阀前/阀后) -->
            <div class="form-row full-width">
              <label>阀门口径</label>
              <el-select v-model="config.nominal_dn" size="small" placeholder="先选型号" style="width:100%" @change="onDnChange">
                <el-option v-for="o in filterOptions.nominal_dn" :key="o.value" :label="o.label || o.value" :value="o.value" />
              </el-select>
              <el-input v-model="config.nominal_dn_back" size="small" placeholder="阀后 (同前)" clearable />
            </div>
            <div class="form-row"><label>阀芯尺寸</label>
              <el-select v-model="config.nominal_trim" size="small" placeholder="先选口径" style="width:100%" @change="onTrimChange">
                <el-option v-for="o in filterOptions.nominal_trim" :key="o.value" :label="o.label || o.value" :value="o.value" />
              </el-select>
            </div>
            <div class="form-row"><label>阀座形式</label>
              <el-select v-model="config.seat_type_front" size="small" placeholder="自动填充" clearable style="width:100%" @change="onTrimChange">
                <el-option v-for="o in seatTypeOptions" :key="o" :label="o" :value="o" />
              </el-select>
            </div>
            <div class="form-row"><label>流量特性</label>
              <el-select v-model="config.trim_characteristics" size="small" placeholder="可选" style="width:100%" @change="onTrimChange">
                <el-option v-for="o in filterOptions.trim_characteristics" :key="o.value" :label="o.label || o.value" :value="o.value" />
              </el-select>
            </div>
            <div class="form-row"><label>压力等级</label>
              <el-select v-model="config.pressure_rating" size="small" placeholder="先选型号" style="width:100%" @change="onDnChange">
                <el-option v-for="o in filterOptions.pressure_rating" :key="o.value" :label="o.label || o.value" :value="o.value" />
              </el-select>
            </div>
            <div class="form-row"><label>阀内件形式</label>
              <el-select v-model="config.trim_seat_type" size="small" placeholder="可选" style="width:100%" @change="onTrimChange">
                <el-option v-for="o in filterOptions.trim_seat_type" :key="o.value" :label="o.label || o.value" :value="o.value" />
              </el-select>
            </div>
            <div class="form-row"><label>流向</label>
              <el-select v-model="config.flow_direction" size="small" placeholder="可选" style="width:100%" @change="onTrimChange">
                <el-option v-for="o in filterOptions.flow_direction" :key="o.value" :label="o.label || o.value" :value="o.value" />
              </el-select>
            </div>
            <div class="form-row"><label>额定 Cv</label>
              <el-input v-model="config.rated_cv" size="small" placeholder="自动填充" />
            </div>
            <div class="form-row"><label>行程</label>
              <el-input v-model="config.stroke_value" size="small" placeholder="自动填充" /><span class="unit-inline">{{ config.stroke_unit || '' }}</span>
            </div>
            <div class="form-row"><label>降噪级数</label>
              <el-input-number v-model="config.stages" :min="1" :max="12" :step="1" :precision="0" size="small" :controls="false" style="width:100%" />
            </div>
            <div class="form-row"><label>可调比</label>
              <el-input-number v-model="config.rangeability" :min="1" :precision="0" size="small" :controls="false" style="width:100%" />
            </div>
          </div>
        </div>

        <!-- 卡片 3：计算系数 -->
        <div class="section-card">
          <div class="section-title">计算系数 <span class="muted">自动填充</span></div>
          <div class="form-grid">
            <div class="form-row"><label>F<sub>L</sub> 压力恢复</label><el-input-number v-model="config.fl" :min="0" :max="1" :step="0.01" :precision="3" size="small" :controls="false" style="width:100%" /></div>
            <div class="form-row"><label>F<sub>D</sub> 类型修正</label><el-input-number v-model="config.fd" :min="0" :max="1" :step="0.01" :precision="3" size="small" :controls="false" style="width:100%" /></div>
            <div class="form-row"><label>x<sub>T</sub> 临界压差比</label><el-input-number v-model="config.xt" :min="0" :max="1" :step="0.01" :precision="3" size="small" :controls="false" style="width:100%" /></div>
            <div class="form-row"><label>K<sub>C</sub> 空化系数</label><el-input-number v-model="config.kc" :min="0" :precision="3" size="small" :controls="false" style="width:100%" /></div>
          </div>
          <div class="section-footer">
            <span class="muted">可手工修改，修改后保存配置生效</span>
          </div>
        </div>

        <!-- 卡片 4：阀体参数 -->
        <div class="section-card">
          <div class="section-title">阀体参数 <span class="muted">手工选择</span></div>
          <div class="form-grid">
            <div class="form-row"><label>阀体材质</label>
              <el-select v-model="config.body_material" size="small" filterable placeholder="选择" style="width:100%">
                <el-option v-for="o in COMMON_DATA.body_materials" :key="o" :label="o" :value="o" />
              </el-select>
            </div>
            <div class="form-row"><label>阀盖形式</label>
              <el-select v-model="config.bonnet_form" size="small" placeholder="选择" style="width:100%">
                <el-option v-for="o in COMMON_DATA.bonnet_forms" :key="o" :label="o" :value="o" />
              </el-select>
            </div>
            <div class="form-row"><label>阀盖材质</label>
              <el-select v-model="config.bonnet_material" size="small" filterable placeholder="选择" style="width:100%">
                <el-option v-for="o in COMMON_DATA.bonnet_materials" :key="o" :label="o" :value="o" />
              </el-select>
            </div>
            <div class="form-row"><label>夹套连接</label>
              <el-select v-model="config.jacket_connection" size="small" placeholder="选择" style="width:100%">
                <el-option v-for="o in COMMON_DATA.jacket_connections" :key="o" :label="o" :value="o" />
              </el-select>
            </div>
            <div class="form-row"><label>填料材质</label>
              <el-select v-model="config.packing_material" size="small" placeholder="选择" style="width:100%">
                <el-option v-for="o in COMMON_DATA.packing_materials" :key="o" :label="o" :value="o" />
              </el-select>
            </div>
            <div class="form-row"><label>填料类型</label>
              <el-select v-model="config.packing_type" size="small" placeholder="选择" style="width:100%">
                <el-option v-for="o in COMMON_DATA.packing_types" :key="o" :label="o" :value="o" />
              </el-select>
            </div>
            <div class="form-row"><label>阀芯材质</label>
              <el-select v-model="config.trim_material" size="small" filterable placeholder="选择" style="width:100%">
                <el-option v-for="o in COMMON_DATA.trim_materials" :key="o" :label="o" :value="o" />
              </el-select>
            </div>
            <div class="form-row"><label>阀杆材质</label>
              <el-select v-model="config.stem_material" size="small" filterable placeholder="选择" style="width:100%">
                <el-option v-for="o in COMMON_DATA.stem_materials" :key="o" :label="o" :value="o" />
              </el-select>
            </div>
            <div class="form-row"><label>阀座材质</label>
              <el-select v-model="config.seat_material" size="small" filterable placeholder="选择" style="width:100%">
                <el-option v-for="o in COMMON_DATA.seat_materials" :key="o" :label="o" :value="o" />
              </el-select>
            </div>
            <div class="form-row"><label>平衡密封材料</label>
              <el-select v-model="config.balance_seal_ring" size="small" filterable placeholder="选择" style="width:100%">
                <el-option v-for="o in COMMON_DATA.balance_seal_rings" :key="o" :label="o" :value="o" />
              </el-select>
            </div>
            <div class="form-row"><label>套筒材质</label>
              <el-select v-model="config.sleeve_material" size="small" filterable placeholder="选择" style="width:100%">
                <el-option v-for="o in COMMON_DATA.sleeve_materials" :key="o" :label="o" :value="o" />
              </el-select>
            </div>
            <div class="form-row"><label>特殊处理</label>
              <el-input v-model="config.special_treatment" size="small" placeholder="如 硬化 / 镀层" />
            </div>
          </div>

          <div class="section-footer">
            <el-button size="small" type="primary" @click="saveConfig">保存配置</el-button>
          </div>
        </div>
      </div>

      <!-- 右栏：工艺工况 + 结果区 -->
      <div class="col-result">

        <!-- 工艺工况（列式布局 + 单位下拉框在第一列） -->
        <div class="section-card">
          <div class="section-title">
            工艺工况 <span class="muted">(单台最多 {{ MAX }} 组，当前 {{ cases.length }} 组)</span>
            <div class="title-actions">
              <el-button size="small" plain @click="addCase" :disabled="cases.length>=MAX" type="primary"><el-icon><Plus /></el-icon>添加</el-button>
              <el-button size="small" @click="saveCases">保存配置与工况</el-button>
            </div>
          </div>

          <div v-if="!cases.length" class="empty-hint">
            <el-icon :size="40"><DataLine /></el-icon>
            <div>点击「添加」录入工艺工况</div>
          </div>

          <!-- 列式工况表 -->
          <div v-else class="cases-table-wrapper">
            <table class="cases-table">
              <colgroup>
                <col class="col-label" />
                <col v-for="(c, i) in cases" :key="i" class="col-case" />
                <col class="col-add" />
              </colgroup>
              <thead>
                <tr>
                  <th class="th-label">参数</th>
                  <th v-for="(c, i) in cases" :key="i" class="th-case">
                    <div class="case-header">
                      <div class="case-no">Case {{ c.case_no }}</div>
                      <div class="case-actions">
                        <el-switch v-model="c.is_active" size="small" style="--el-switch-on-color:#67c23a" />
                        <el-button link type="danger" size="small" @click="removeCase(i)"><el-icon><Close /></el-icon></el-button>
                      </div>
                    </div>
                    <el-input v-model="c.case_name" size="small" placeholder="工况名称" class="case-name-input" />
                  </th>
                  <th class="th-add" :class="{ 'th-add-disabled': cases.length>=MAX }" @click="addCase">
                    <template v-if="cases.length<MAX">
                      <el-icon :size="20"><Plus /></el-icon>
                      <span>添加</span>
                    </template>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td class="td-label"><span class="lbl">介质</span></td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-select v-model="c.fluid_id" size="small" filterable allow-create default-first-option placeholder="选择或输入自定义介质" @change="(val) => onFluidChange(c, val)">
                      <el-option v-for="f in fluids" :key="f.id" :label="(f.fluid_name_cn || f.fluid_name) + (f.formula ? ' (' + f.formula + ')' : '') + (f.is_water?' ⚡':'')" :value="f.id" />
                    </el-select>
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <tr>
                  <td class="td-label"><span class="lbl">相态覆盖</span></td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-select v-model="c.fluid_state_override" size="small" clearable placeholder="自动">
                      <el-option label="液态" value="liquid" /><el-option label="气态" value="gas" />
                    </el-select>
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <!-- P1 阀前压力 -->
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">P1 阀前压力</span>
                      <el-select v-model="caseUnits.p1" size="small" class="unit-select">
                        <el-option-group label="公制">
                          <el-option v-for="u in (unitsByGroup.pressure?.metric || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in (unitsByGroup.pressure?.imperial || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.p1" :min="0" :precision="2" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <!-- P2 阀后压力 -->
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">P2 阀后压力</span>
                      <el-select v-model="caseUnits.p2" size="small" class="unit-select">
                        <el-option-group label="公制">
                          <el-option v-for="u in (unitsByGroup.pressure?.metric || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in (unitsByGroup.pressure?.imperial || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.p2" :min="0" :precision="2" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <!-- ΔP 自动计算 -->
                <tr>
                  <td class="td-label"><span class="lbl">ΔP = P1-P2</span></td>
                  <td v-for="(c, i) in cases" :key="i" class="val-delta">
                    {{ calcDeltaP(c) != null ? calcDeltaP(c) : '—' }} <span class="unit-badge">kPa</span>
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <!-- T1 阀前温度 -->
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">T1 阀前温度</span>
                      <el-select v-model="caseUnits.t1" size="small" class="unit-select">
                        <el-option-group label="公制">
                          <el-option v-for="u in (unitsByGroup.temperature?.metric || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in (unitsByGroup.temperature?.imperial || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.t1" :precision="1" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <!-- 质量流量 -->
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">质量流量</span>
                      <el-select v-model="caseUnits.flow_mass" size="small" class="unit-select">
                        <el-option-group label="公制">
                          <el-option v-for="u in (unitsByGroup.mass_flow?.metric || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in (unitsByGroup.mass_flow?.imperial || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.flow_mass" :min="0" :precision="2" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <!-- 体积流量 -->
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">体积流量(液/气)</span>
                      <el-select v-model="caseUnits.flow_vol" size="small" class="unit-select">
                        <el-option-group v-if="flowVolOptions.std_gas.length" label="标况气体">
                          <el-option v-for="u in flowVolOptions.std_gas" :key="u.unit_code" :label="u.unit_label + ' (标况)'" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="公制">
                          <el-option v-for="u in flowVolOptions.metric" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in flowVolOptions.imperial" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.flow_vol" :min="0" :precision="2" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <!-- 管道内径 -->
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">管道内径</span>
                      <el-select v-model="caseUnits.pipe_diameter" size="small" class="unit-select">
                        <el-option-group label="公制">
                          <el-option v-for="u in (unitsByGroup.diameter?.metric || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in (unitsByGroup.diameter?.imperial || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.pipe_diameter" :min="0" :precision="1" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <!-- 管道壁厚 -->
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">管道壁厚</span>
                      <el-select v-model="caseUnits.pipe_wall" size="small" class="unit-select">
                        <el-option-group label="公制">
                          <el-option v-for="u in (unitsByGroup.wall_thickness?.metric || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in (unitsByGroup.wall_thickness?.imperial || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.pipe_wall" :min="0" :precision="1" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <!-- 测点距离 -->
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">噪音测点距离</span>
                      <el-select v-model="caseUnits.distance" size="small" class="unit-select">
                        <el-option-group label="公制">
                          <el-option v-for="u in (unitsByGroup.distance?.metric || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in (unitsByGroup.distance?.imperial || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.distance" :min="0.1" :step="0.5" :precision="1" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <!-- 两相流参数（可折叠） -->
                <tr class="section-sep clickable" @click="twophaseCollapsed = !twophaseCollapsed">
                  <td :colspan="cases.length + 2" class="sep-line sep-line-clickable">
                    <span class="collapse-icon">
                      <el-icon :size="12" :class="{ rotate: !twophaseCollapsed }"><ArrowRight /></el-icon>
                    </span>
                    两相流参数（仅气液混合工况填写）
                    <span class="muted collapse-hint">{{ twophaseCollapsed ? '点击展开' : '点击收起' }}</span>
                  </td>
                </tr>
                <template v-if="!twophaseCollapsed">
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">气相流量</span>
                      <el-select v-model="caseUnits.mass_flow_gas" size="small" class="unit-select">
                        <el-option-group label="公制">
                          <el-option v-for="u in (unitsByGroup.mass_flow?.metric || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in (unitsByGroup.mass_flow?.imperial || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.mass_flow_gas" :min="0" :precision="2" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">液相流量</span>
                      <el-select v-model="caseUnits.mass_flow_liquid" size="small" class="unit-select">
                        <el-option-group label="公制">
                          <el-option v-for="u in (unitsByGroup.mass_flow?.metric || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in (unitsByGroup.mass_flow?.imperial || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.mass_flow_liquid" :min="0" :precision="2" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <tr :style="shouldShowTwoPhase ? '' : 'display:none'">
                  <td class="td-label"><span class="lbl">两相方法</span></td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-select v-model="c.twophase_method" size="small">
                      <el-option label="IEC Annex C（与Excel一致，推荐）" value="iec_annexc" />
                      <el-option label="叠加法(additive，保守)" value="additive" />
                      <el-option label="均相膨胀法(homogeneous)" value="homogeneous" />
                    </el-select>
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">气相密度</span>
                      <el-select v-model="caseUnits.density_gas" size="small" class="unit-select">
                        <el-option-group label="公制">
                          <el-option v-for="u in (unitsByGroup.density?.metric || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in (unitsByGroup.density?.imperial || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.density_gas" :min="0" :precision="3" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">液相密度</span>
                      <el-select v-model="caseUnits.density_liquid" size="small" class="unit-select">
                        <el-option-group label="公制">
                          <el-option v-for="u in (unitsByGroup.density?.metric || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in (unitsByGroup.density?.imperial || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.density_liquid" :min="0" :precision="3" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                </template>
                <!-- 物性覆盖 -->
                <tr class="section-sep"><td :colspan="cases.length + 2" class="sep-line">物性覆盖（可选，留空用介质物性表 / IAPWS-IF97 自动计算）</td></tr>
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">密度覆盖</span>
                      <el-select v-model="caseUnits.density_override" size="small" class="unit-select">
                        <el-option-group v-if="unitsByGroup.density?.std_gas?.length" label="标况气体">
                          <el-option v-for="u in unitsByGroup.density.std_gas" :key="u.unit_code" :label="u.unit_label + ' (标况)'" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="公制">
                          <el-option v-for="u in (unitsByGroup.density?.metric || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in (unitsByGroup.density?.imperial || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.density_override" :min="0" :precision="3" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">粘度覆盖</span>
                      <el-select v-model="caseUnits.viscosity_override" size="small" class="unit-select">
                        <el-option-group label="公制">
                          <el-option v-for="u in (unitsByGroup.viscosity?.metric || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in (unitsByGroup.viscosity?.imperial || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.viscosity_override" :min="0" :precision="4" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <tr>
                  <td class="td-label">
                    <div class="label-with-unit">
                      <span class="lbl">摩尔质量覆盖</span>
                      <el-select v-model="caseUnits.molecular_weight_override" size="small" class="unit-select">
                        <el-option-group label="公制">
                          <el-option v-for="u in (unitsByGroup.molecular_weight?.metric || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                        <el-option-group label="英制">
                          <el-option v-for="u in (unitsByGroup.molecular_weight?.imperial || [])" :key="u.unit_code" :label="u.unit_label" :value="u.unit_code" />
                        </el-option-group>
                      </el-select>
                    </div>
                  </td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.molecular_weight_override" :min="0" :precision="2" size="small" :controls="false" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
                <tr>
                  <td class="td-label"><span class="lbl">比热比 γ</span></td>
                  <td v-for="(c, i) in cases" :key="i">
                    <el-input-number v-model="c.gamma_override" :min="0" :step="0.01" :precision="3" size="small" :controls="false" style="width:100%" />
                  </td>
                  <td class="td-add" :class="{ 'td-add-disabled': cases.length>=MAX }"></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="section-card" v-if="!hasResults">
          <div class="section-title">计算结果</div>
          <div class="empty-hint">
            <el-icon :size="40"><Histogram /></el-icon>
            <div>尚未计算，请在上方录入工艺工况后点击「执行计算」</div>
          </div>
        </div>

        <template v-else>
          <div class="section-card">
            <div class="section-title">计算结果汇总</div>
            <div class="result-table-wrapper">
              <table class="result-table">
                <colgroup>
                  <col class="col-label" />
                  <col v-for="r in resultRows" :key="r.case_no" class="col-case" />
                  <col class="col-add" />
                </colgroup>
                <thead>
                  <tr>
                    <th class="th-label">参数</th>
                    <th v-for="r in resultRows" :key="r.case_no" class="th-case">
                      Case {{ r.case_no }}
                      <div class="case-sub">{{ r.case_name }}</div>
                    </th>
                    <th class="th-add-placeholder"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr><td class="td-label"><span class="lbl">相态</span></td>
                    <td v-for="r in resultRows" :key="r.case_no"><el-tag size="small" :type="phaseTag(r.phase)" effect="light">{{ phaseText(r.phase) }}</el-tag></td><td class="td-add-placeholder"></td></tr>
                  <tr><td class="td-label"><span class="lbl">所需 Cv</span></td>
                    <td v-for="r in resultRows" :key="r.case_no" class="val-strong">{{ fmt(r.cv_required) }}</td><td class="td-add-placeholder"></td></tr>
                  <tr><td class="td-label"><span class="lbl">额定 Cv</span></td>
                    <td v-for="r in resultRows" :key="r.case_no">{{ fmt(r.cv_rated_selected) }}</td><td class="td-add-placeholder"></td></tr>
                  <tr><td class="td-label"><span class="lbl">开度 %</span></td>
                    <td v-for="r in resultRows" :key="r.case_no" :class="openingClass(r.cv_opening)">{{ fmt(r.cv_opening) }}</td><td class="td-add-placeholder"></td></tr>
                  <tr><td class="td-label"><span class="lbl">流态</span></td>
                    <td v-for="r in resultRows" :key="r.case_no"><el-tag size="small" :type="regimeTag(r.flow_regime)">{{ regimeText(r.flow_regime) }}</el-tag></td><td class="td-add-placeholder"></td></tr>
                  <tr><td class="td-label"><span class="lbl">ΔP kPa</span></td>
                    <td v-for="r in resultRows" :key="r.case_no">{{ fmt(r.dp) }}</td><td class="td-add-placeholder"></td></tr>
                  <tr v-if="hasGasResult"><td class="td-label"><span class="lbl">压差比 x</span></td>
                    <td v-for="r in resultRows" :key="r.case_no">{{ fmt4(r.x) }}</td><td class="td-add-placeholder"></td></tr>
                  <tr v-if="hasGasResult"><td class="td-label"><span class="lbl">膨胀系数 Y</span></td>
                    <td v-for="r in resultRows" :key="r.case_no">{{ fmt4(r.y) }}</td><td class="td-add-placeholder"></td></tr>
                  <tr><td class="td-label"><span class="lbl">雷诺数</span></td>
                    <td v-for="r in resultRows" :key="r.case_no">{{ fmt(r.reynolds) }}</td><td class="td-add-placeholder"></td></tr>
                  <tr><td class="td-label"><span class="lbl">噪音 LpA dB(A)</span></td>
                    <td v-for="r in resultRows" :key="r.case_no" :class="noiseClass(r.noise_dba)">{{ fmt(r.noise_dba) }}</td><td class="td-add-placeholder"></td></tr>
                  <tr><td class="td-label"><span class="lbl">峰值频率 Hz</span></td>
                    <td v-for="r in resultRows" :key="r.case_no">{{ fmt(r.noise_freq_peak) }}</td><td class="td-add-placeholder"></td></tr>
                  <tr><td class="td-label"><span class="lbl">流态详情</span></td>
                    <td v-for="r in resultRows" :key="r.case_no" class="regime-detail">{{ r.flow_regime }}</td><td class="td-add-placeholder"></td></tr>
                  <template v-if="hasMultiStageResult">
                    <tr class="section-sep"><td colspan="99">多级降噪阀压降分配</td></tr>
                    <tr><td class="td-label"><span class="lbl">降噪级数 N</span></td>
                      <td v-for="r in resultRows" :key="r.case_no">{{ (noiseDetail(r)||{}).stages || '—' }}</td><td class="td-add-placeholder"></td></tr>
                    <tr><td class="td-label"><span class="lbl">总压差比 xT</span></td>
                      <td v-for="r in resultRows" :key="r.case_no">{{ fmt4((noiseDetail(r)||{}).x_total) }}</td><td class="td-add-placeholder"></td></tr>
                    <tr><td class="td-label"><span class="lbl">每级压差比 x</span></td>
                      <td v-for="r in resultRows" :key="r.case_no">{{ fmt4((noiseDetail(r)||{}).x_stage) }}</td><td class="td-add-placeholder"></td></tr>
                    <tr><td class="td-label"><span class="lbl">每级压力比 r</span></td>
                      <td v-for="r in resultRows" :key="r.case_no">{{ fmt4((noiseDetail(r)||{}).r_stage) }}</td><td class="td-add-placeholder"></td></tr>
                    <tr><td class="td-label"><span class="lbl">所需最少级数</span></td>
                      <td v-for="r in resultRows" :key="r.case_no" :class="{ 'val-warn': (noiseDetail(r)||{}).stages_needed > (noiseDetail(r)||{}).stages }">{{ (noiseDetail(r)||{}).stages_needed || '—' }}</td><td class="td-add-placeholder"></td></tr>
                  </template>
                </tbody>
              </table>
            </div>
          </div>

          <div class="section-card">
            <div class="section-title">介质物性快照（内部统一单位）</div>
            <div class="result-table-wrapper">
              <table class="result-table">
                <colgroup>
                  <col class="col-label" />
                  <col v-for="r in resultRows" :key="r.case_no" class="col-case" />
                  <col class="col-add" />
                </colgroup>
                <thead>
                  <tr>
                    <th class="th-label">参数</th>
                    <th v-for="r in resultRows" :key="r.case_no" class="th-case">Case {{ r.case_no }}</th>
                    <th class="th-add-placeholder"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr><td class="td-label"><span class="lbl">介质</span></td>
                    <td v-for="r in resultRows" :key="r.case_no">{{ (r.resolved_properties || {}).name || '—' }}</td><td class="td-add-placeholder"></td></tr>
                  <tr><td class="td-label"><span class="lbl">密度 kg/m³</span></td>
                    <td v-for="r in resultRows" :key="r.case_no">{{ fmt((r.resolved_properties || {}).density) }}</td><td class="td-add-placeholder"></td></tr>
                  <tr><td class="td-label"><span class="lbl">粘度 cP</span></td>
                    <td v-for="r in resultRows" :key="r.case_no">{{ fmt((r.resolved_properties || {}).viscosity_cp) }}</td><td class="td-add-placeholder"></td></tr>
                  <tr><td class="td-label"><span class="lbl">比热比 γ</span></td>
                    <td v-for="r in resultRows" :key="r.case_no">{{ fmt4((r.resolved_properties || {}).gamma) }}</td><td class="td-add-placeholder"></td></tr>
                  <tr><td class="td-label"><span class="lbl">饱和蒸汽压 kPa</span></td>
                    <td v-for="r in resultRows" :key="r.case_no">{{ fmt((r.resolved_properties || {}).vapor_pressure_kpa) }}</td><td class="td-add-placeholder"></td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="section-card" v-if="allWarnings.length">
            <div class="section-title">提示与警告</div>
            <div class="warnings-list">
              <div v-for="(w, i) in allWarnings" :key="i" class="warning-item" :class="w.severity">
                <el-icon v-if="w.severity==='danger'"><Warning /></el-icon>
                <el-icon v-else-if="w.severity==='warn'"><WarningFilled /></el-icon>
                <el-icon v-else><InfoFilled /></el-icon>
                <span>Case {{ w.case_no }}: {{ w.text }}</span>
              </div>
            </div>
          </div>
        </template>

        <!-- 曲线图（置于底部）：Cv vs 行程 与 计算因数 并排 -->
        <div class="charts-row">
          <div class="section-card chart-card">
            <div class="section-title">Cv vs 行程曲线
              <span class="muted" v-if="strokeModeInfo">{{ strokeModeInfo }}</span>
            </div>
            <v-chart class="calc-chart" :option="cvChartOption" autoresize />
          </div>
          <div class="section-card chart-card">
            <div class="section-title">计算因数曲线
              <span class="muted">FL / xT / Kc / Fd vs % 额定 Cv</span>
            </div>
            <v-chart class="calc-chart" :option="factorChartOption" autoresize />
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 推荐 SCH 对话框 (ASME B31.3) -->
  <el-dialog v-model="schDialog.visible" title="推荐 SCH — ASME B31.3" width="640px" append-to-body>
    <div class="sch-form">
      <div class="sch-form-row"><span class="sch-label">管道规格</span><span>{{ schDialog.specLabel || '—' }}</span></div>
      <div class="sch-form-row">
        <span class="sch-label">设计压力</span>
        <el-input-number v-model="schDialog.pressure_mpa" :min="0.001" :precision="3" size="small" :controls="false" style="width:140px" />
        <span class="sch-unit">MPa(G)</span>
      </div>
      <div class="sch-form-row">
        <span class="sch-label">设计温度</span>
        <el-input-number v-model="schDialog.temp_c" :precision="1" size="small" :controls="false" style="width:140px" />
        <span class="sch-unit">℃</span>
      </div>
      <div class="sch-form-row">
        <span class="sch-label">管道材质</span>
        <el-select v-model="schDialog.material_code" size="small" filterable style="width:280px">
          <el-option v-for="m in schDialog.materials" :key="m.material_code" :value="m.material_code"
            :label="`${m.material_code} — ${m.notes || m.material_group || ''}`" />
        </el-select>
      </div>
      <div class="sch-form-row">
        <span class="sch-label">焊缝系数 E</span>
        <el-input-number v-model="schDialog.weld_factor_e" :min="0.1" :max="1" :step="0.05" :precision="2" size="small" :controls="false" style="width:140px" />
        <span class="sch-unit">无缝管 1.0</span>
      </div>
      <div class="sch-form-row">
        <span class="sch-label">腐蚀裕量 CA</span>
        <el-input-number v-model="schDialog.corrosion_allowance_mm" :min="0" :precision="1" size="small" :controls="false" style="width:140px" />
        <span class="sch-unit">mm</span>
      </div>
      <div class="sch-form-row">
        <el-button type="primary" size="small" :loading="schDialog.loading" @click="runSchRecommend">计算推荐</el-button>
      </div>
    </div>

    <template v-if="schDialog.result">
      <el-alert :title="schDialog.result.note" type="info" :closable="false" show-icon style="margin:10px 0" />
      <el-table :data="schDialog.result.candidates" size="small" border max-height="260">
        <el-table-column prop="schedule" label="SCH" width="90">
          <template #default="{ row }">
            <span :style="row.schedule === schDialog.result.recommended_schedule ? 'color:#409eff;font-weight:700' : ''">{{ row.schedule }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="thk_mm" label="壁厚 mm" width="100" />
        <el-table-column prop="margin_mm" label="裕量 mm" width="100" />
        <el-table-column label="校核" width="90">
          <template #default="{ row }">
            <el-tag :type="row.ok ? 'success' : 'danger'" size="small">{{ row.ok ? '合格' : '不足' }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </template>

    <template #footer>
      <el-button size="small" @click="schDialog.visible = false">关闭</el-button>
      <el-button size="small" type="primary" :disabled="!schDialog.result?.recommended_schedule" @click="applySchRecommend">
        应用推荐 SCH{{ schDialog.result?.recommended_schedule ? ` (${schDialog.result.recommended_schedule})` : '' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, onMounted, watch, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { valvesApi, calcApi, fluidsApi, unitsApi, valveTypesApi, publicOptionsApi, pipeDataApi } from '@/api'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkPointComponent, MarkLineComponent, LegendComponent } from 'echarts/components'
use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, MarkPointComponent, MarkLineComponent, LegendComponent])

// 公共数据常量（从界面参考.xlsx 公共数据页签采集）
// 公共选项数据 (优先从后端 /public-options 加载, 失败时用本地兜底)
// 后端 group_key 是单数形式 (connection_type), 模板里属性名是复数 (connection_types)
const COMMON_DATA = ref({
  connection_types: ['法兰连接', '对夹连接', '对焊连接', '支耳连接', '螺纹连接', '卡套连接', '卡箍连接', '内自紧连接'],
  face_types: ['FF', 'RF', 'RJ', 'M', 'FM', 'T', 'G', 'BW', 'SW'],
  flange_standards: ['HG/T 20592-2009', 'HG/T 20615-2009', 'HG/T 20623-2009(A)', 'HG/T 20623-2009(B)', 'ASME B16.5'],
  body_materials: ['A216M-WCB', 'A217M-WC6', 'A217M-WC9', 'LCB', 'A351M-CF8', 'A351M-CF8M', 'A351M-CF3', 'A351M-CF3M', '304', '316', '304L', '316L', '321', '347', '310S', 'CD4MCU', 'Alloy 20#', 'WCB'],
  bonnet_materials: ['与阀体相同', 'A216M-WCB', '304', '316', '316L', 'A182-F11', 'A182-F22'],
  bonnet_forms: ['标准型', '散热片型', '加长型', '波纹管型', '蒸汽夹套型', '低温型加冷箱'],
  jacket_connections: ['NON', 'Rc1/2"', 'NPT1/2"', 'DN25'],
  packing_types: ['标准型', '双重密封', '动态密封', '双重动态密封'],
  packing_materials: ['PTFE', 'PTFE(禁油)', '柔性石墨'],
  trim_materials: ['304', '304L', '304/部分堆STL.6', '304/全堆STL.6', '316', '316L', '316/部分堆STL.6', '316/全堆STL.6', '17-4PH/H1025', 'XM-19/HT', 'Inconel718/HT', 'CD4MCU'],
  seat_materials: ['PTFE', 'Nylon 66', '外部轴承型', '固体镶嵌轴承(铜合金基体)', 'Alloy 20#'],
  sleeve_materials: ['304', '304L', '316', '316L', 'CF8', 'CF8M'],
  stem_materials: ['410', '410/HT', '316', '316L', 'A182-F11', 'A182-F11/HT', 'Inconel X-750/HT'],
  balance_seal_rings: ['PTFE', 'PPL', '304/Ni55', '316/Ni55', '310S/Ni55', '304/F46', '316/F46', 'Alloy 20#'],
  seat_types: ['15 Deg Sealed', 'Back Seat', 'Damper', 'Metal', 'Soft'],
})

// 后端 group_key -> 前端 COMMON_DATA 属性名映射
const PUBLIC_OPTIONS_KEY_MAP = {
  connection_type: 'connection_types',
  face_type: 'face_types',
  flange_standard: 'flange_standards',
  body_material: 'body_materials',
  bonnet_material: 'bonnet_materials',
  bonnet_form: 'bonnet_forms',
  jacket_connection: 'jacket_connections',
  packing_type: 'packing_types',
  packing_material: 'packing_materials',
  trim_material: 'trim_materials',
  seat_material: 'seat_materials',
  sleeve_material: 'sleeve_materials',
  stem_material: 'stem_materials',
  balance_seal_ring: 'balance_seal_rings',
  seat_type: 'seat_types',
}

// 从后端加载公共选项数据 (缓存到 COMMON_DATA)
async function loadPublicOptions() {
  try {
    const { data } = await publicOptionsApi.list()
    const groups = data?.groups || {}
    for (const [groupKey, items] of Object.entries(groups)) {
      const propName = PUBLIC_OPTIONS_KEY_MAP[groupKey]
      if (propName && Array.isArray(items) && items.length) {
        COMMON_DATA.value[propName] = items.map(o => o.value)
      }
    }
  } catch (e) {
    // 失败时用本地兜底 (不报错)
  }
}

// 加载管道规格数据 (pipe_data 表)
async function loadPipeData() {
  try {
    const data = await pipeDataApi.list()
    pipeDataList.value = Array.isArray(data) ? data : []
  } catch (e) {
    pipeDataList.value = []
  }
}

// 格式化：英制 in (公制 mm)，如 "2 in (50 mm)"
function fmtImperialMetric(inVal, mmVal) {
  if (inVal == null && mmVal == null) return ''
  const mmStr = mmVal != null ? `${Math.round(mmVal)} mm` : ''
  if (inVal != null) return `${inVal} in (${mmStr})`
  return mmStr
}

// ---- 推荐 SCH (ASME B31.3) ----
const schDialog = reactive({
  visible: false, loading: false,
  specLabel: '', dn_mm: null,
  pressure_mpa: null, temp_c: null, material_code: 'A106-B',
  weld_factor_e: 1.0, corrosion_allowance_mm: 1.5,
  materials: [], result: null,
})

function openSchRecommend() {
  const found = pipeDataList.value.find(p => p.lookup_key === config.value.pipe_spec_front)
  if (!found) { ElMessage.warning('请先选择阀前管道规格'); return }
  schDialog.specLabel = found.lookup_key
  schDialog.dn_mm = found.dn_mm
  schDialog.pressure_mpa = config.value.design_pressure ?? 1.0
  schDialog.temp_c = config.value.design_temp ?? 38
  schDialog.material_code = guessMaterialCode(config.value.pipe_material_front)
  schDialog.result = null
  schDialog.visible = true
  if (!schDialog.materials.length) {
    pipeDataApi.materials().then(d => { schDialog.materials = Array.isArray(d) ? d : [] }).catch(() => {})
  }
}

// 从管道材质文本推断 ASME 材质代码
function guessMaterialCode(text) {
  const t = (text || '').toUpperCase().replace(/[\s-]/g, '')
  if (!t) return 'A106-B'
  if (t.includes('316L')) return 'TP316L'
  if (t.includes('316')) return 'TP316'
  if (t.includes('304L')) return 'TP304L'
  if (t.includes('304') || t.includes('0CR18NI9')) return 'TP304'
  if (t.includes('321')) return 'TP321'
  if (t.includes('347')) return 'TP347'
  if (t.includes('P22') || t.includes('2.25CR')) return 'A335-P22'
  if (t.includes('P11') || t.includes('1.25CR')) return 'A335-P11'
  if (t.includes('20#') || t.includes('Q235') || t.includes('A106')) return 'A106-B'
  return 'A106-B'
}

async function runSchRecommend() {
  if (!schDialog.dn_mm) return
  if (!schDialog.pressure_mpa || schDialog.temp_c == null) { ElMessage.warning('请填写设计压力和设计温度'); return }
  schDialog.loading = true
  try {
    schDialog.result = await pipeDataApi.suggestSch({
      dn_mm: schDialog.dn_mm,
      pressure_mpa: schDialog.pressure_mpa,
      temp_c: schDialog.temp_c,
      material_code: schDialog.material_code,
      weld_factor_e: schDialog.weld_factor_e,
      corrosion_allowance_mm: schDialog.corrosion_allowance_mm,
    })
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '推荐计算失败')
    schDialog.result = null
  } finally {
    schDialog.loading = false
  }
}

function applySchRecommend() {
  const rec = schDialog.result?.recommended_schedule
  if (!rec || schDialog.dn_mm == null) return
  // 找到同 DN 且 schedule 匹配的管道规格, 切换阀前规格并联动填充
  const target = pipeDataList.value.find(p => p.dn_mm === schDialog.dn_mm && p.schedule === rec)
  if (target) {
    config.value.pipe_spec_front = target.lookup_key
    onPipeSpecChange('front')
    // 阀后沿用「同步阀后为阀前」由用户决定, 这里不强制
  } else {
    config.value.sch_front = rec
  }
  schDialog.visible = false
  ElMessage.success(`已应用推荐 SCH ${rec}`)
}

// 管道规格变更时, 自动填充管道尺寸 (nps_label)、管道 SCH、管道壁厚
function onPipeSpecChange(side) {
  const specKey = side === 'front' ? 'pipe_spec_front' : 'pipe_spec_back'
  const sizeKey = side === 'front' ? 'pipe_size_front' : 'pipe_size_back'
  const schKey = side === 'front' ? 'sch_front' : 'sch_back'
  const wallKey = side === 'front' ? 'pipe_wall_front' : 'pipe_wall_back'
  const lookupKey = config.value[specKey]
  if (!lookupKey) return
  const found = pipeDataList.value.find(p => p.lookup_key === lookupKey)
  if (found) {
    config.value[sizeKey] = fmtImperialMetric(found.nps_label, found.dn_mm)
    if (found.schedule) config.value[schKey] = found.schedule
    config.value[wallKey] = fmtImperialMetric(found.thk_in, found.thk_mm)
    // 阀前管道规格选定后, 把内径/壁厚按工艺工况所选单位同步到所有 case
    if (side === 'front') syncPipeDimsToCases(found)
  }
}

// 把管道规格的内径/壁厚 (mm) 按工艺工况当前所选单位填入所有 case
function syncPipeDimsToCases(pipe) {
  if (!pipe) return
  cases.forEach(c => {
    if (pipe.id_mm != null) c.pipe_diameter = convertMmTo(pipe.id_mm, caseUnits.pipe_diameter)
    if (pipe.thk_mm != null) c.pipe_wall = convertMmTo(pipe.thk_mm, caseUnits.pipe_wall)
  })
}

// mm → 目标单位 (根据 units 字典中的 factor, factor 表示 1 单位 = factor mm)
function convertMmTo(mmVal, unitCode) {
  if (mmVal == null) return null
  const all = [...(units.diameter || []), ...(units.wall_thickness || []), ...(units.distance || [])]
  const u = all.find(x => x.unit_code === unitCode)
  const factor = u && u.factor ? Number(u.factor) : 1
  if (factor === 0) return mmVal
  return Number((mmVal / factor).toFixed(4))
}

// 管道 SCH 等级（硬编码，后端 pipe_data API 后续接入）
const PIPE_SCH_DATA = ['5S', '10S', '20', '30', '40', '80', '100', '120', '140', '160']

// 把后端 curve-options 返回的 filter_configs 数组转为以 key 为索引的对象
function normalizeFilterConfigs(raw) {
  if (!raw) return {}
  if (!Array.isArray(raw)) return raw
  const out = {}
  // 后端 filter_configs 的 key 与前端字段名映射
  const KEY_MAP = {
    trim_type: 'trim_seat_type',  // 后端 trim_type = 阀内件形式 (前端字段 trim_seat_type)
  }
  for (const item of raw) {
    if (!item.key) continue
    const targetKey = KEY_MAP[item.key] || item.key
    // 后端 options 可能是纯字符串数组 ["100A","20A"] 或对象 [{value,label}] 或 [{code,label}]
    // 统一归一为对象数组 {value, label}
    const opts = (item.options || []).map(o => {
      if (typeof o === 'string' || typeof o === 'number') return { value: o, label: String(o) }
      if (o.code != null) return { value: o.code, label: o.label || String(o.code) }
      return { value: o.value, label: o.label || String(o.value) }
    })
    const obp = item.options_by_parent || {}
    const obp_norm = {}
    for (const [pk, pvs] of Object.entries(obp)) {
      obp_norm[pk] = (pvs || []).map(o => {
        if (typeof o === 'string' || typeof o === 'number') return { value: o, label: String(o) }
        if (o.code != null) return { value: o.code, label: o.label || String(o.code) }
        return { value: o.value, label: o.label || String(o.value) }
      })
    }
    out[targetKey] = {
      ...item,
      key: targetKey,
      options: opts,
      options_by_parent: obp_norm,
    }
  }
  return out
}

// Cv 曲线标准开度点
const STANDARD_STROKES = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 1.00]

const route = useRoute()
const pid = computed(() => route.params.pid)
const vid = computed(() => route.params.vid)
const MAX = 5
const loading = ref(false)
const running = ref(false)
// 两相流参数区域折叠（默认折叠）
const twophaseCollapsed = ref(true)

const valve = ref(null)
const calcs = ref([])
const calc = ref(null)
const currentCid = ref(null)
const fluids = ref([])
const valveTypes = ref([])
const pipeDataList = ref([])
const config = ref({})
const cases = ref([])
const results = ref({})

// ---- 阀门选型级联 & 曲线数据 ----
const filterConfigs = ref({})   // curve-options 返回的 filter_configs
const curveInfo = reactive({
  stroke_mode: '',
  eqcv: null,          // { eq_index, a0..a6, divisor? }
  fstk: null,          // ln_eqn 模式的等比分值
  rated_cv: null,
  stroke_value: null,
  stroke_unit: null,
  seat_type: null,
  fl: null, fd: null, xt: null, kc: null,
})

// 单位字典（从后端加载）
const units = reactive({
  pressure: [], temperature: [], mass_flow: [], vol_flow_liquid: [], vol_flow_gas: [],
  density: [], viscosity: [], diameter: [], wall_thickness: [], distance: [], molecular_weight: [],
})
const unitDefaults = reactive({})
const unitLabels = computed(() => {
  const out = {}
  for (const cat of Object.keys(units)) {
    out[cat] = {}
    for (const u of units[cat]) out[cat][u.unit_code] = u.unit_label
  }
  return out
})

// 同行统一单位（所有 Case 共用）
const caseUnits = reactive({
  p1: 'kPaA', p2: 'kPaA',
  t1: 'C', t2: 'C',
  flow_mass: 'kg_h', flow_vol: 'm3_h',
  pipe_diameter: 'mm', pipe_wall: 'mm', distance: 'm',
  mass_flow_gas: 'kg_h', mass_flow_liquid: 'kg_h',
  density_gas: 'kg_m3', density_liquid: 'kg_m3',
  density_override: 'kg_m3', viscosity_override: 'cP',
  molecular_weight_override: 'kg_kmol',
})

// 按公制/英制分组的单位字典
const unitsByGroup = computed(() => {
  const out = {}
  for (const cat of Object.keys(units)) {
    const all = units[cat] || []
    out[cat] = {
      metric: all.filter(u => u.unit_group === 'metric'),
      imperial: all.filter(u => u.unit_group === 'imperial'),
      std_gas: all.filter(u => u.unit_group === 'standard_gas'),
    }
  }
  return out
})

// 体积流量合并液/气类别
const flowVolOptions = computed(() => {
  const g = unitsByGroup.value['vol_flow_liquid'] || {}
  const gg = unitsByGroup.value['vol_flow_gas'] || {}
  return {
    metric: [...(g.metric || []), ...(gg.metric || [])],
    imperial: [...(g.imperial || []), ...(gg.imperial || [])],
    std_gas: (gg.std_gas || []),
  }
})

const hasResults = computed(() => Object.keys(results.value).length > 0)
const resultRows = computed(() => cases.value
  .filter(c => c.is_active !== false)
  .map(c => results.value[c.id] ? { ...results.value[c.id], case_no: c.case_no, case_name: c.case_name } : null)
  .filter(Boolean))
const hasGasResult = computed(() => resultRows.value.some(r => r.phase !== 'liquid'))
// 多级降噪阀: 任一结果的 detail.noise.stages > 1
const hasMultiStageResult = computed(() => resultRows.value.some(r => {
  const nd = noiseDetail(r)
  return nd && nd.stages && nd.stages > 1
}))
// 提取 r.detail.noise (兼容 dict / JSON 字符串)
function noiseDetail(r) {
  if (!r || !r.detail) return null
  let d = r.detail
  if (typeof d === 'string') { try { d = JSON.parse(d) } catch { return null } }
  return (d && d.noise) ? d.noise : null
}

// 两相流方法下拉仅在：任一结果为两相 或 任一case填写了气液双流量 时显示
const shouldShowTwoPhase = computed(() => {
  if (resultRows.value.some(r => r.phase === 'twophase')) return true
  if (cases.value.some(c => (c.mass_flow_gas ?? 0) > 0 && (c.mass_flow_liquid ?? 0) > 0)) return true
  return false
})

const allWarnings = computed(() => {
  const out = []
  for (const r of resultRows.value) {
    const msgs = (r.message || '').split(';').filter(Boolean)
    for (const m of msgs) {
      let severity = 'info'
      if (m.includes('偏小') || m.includes('闪蒸') || m.includes('空化')) severity = 'danger'
      else if (m.includes('噪音') || m.includes('阻塞')) severity = 'warn'
      out.push({ case_no: r.case_no, text: m.trim(), severity })
    }
  }
  return out
})

// ---- 阀门型号匹配 ----
const currentSeries = computed(() => {
  const sc = config.value.valve_style
  if (!sc) return null
  return valveTypes.value.find(v => v.series_code === sc) || null
})

// ---- 级联过滤后的下拉选项 ----
// filterOptions 的原始对象（包含 filters fallback 数据，可在 onValveStyleChange 时赋值）
let _curveFiltersFallback = {}

const filterOptions = computed(() => {
  const fc = filterConfigs.value || {}
  const out = {}
  const keys = ['nominal_dn', 'pressure_rating', 'nominal_trim', 'flow_direction', 'trim_characteristics', 'trim_seat_type', 'seat_type']
  for (const key of keys) {
    const conf = fc[key]
    // 先取 filter_configs 的 options，若为空数组则 fallback 到 _curveFiltersFallback[key]
    let opts = (conf?.options && conf.options.length) ? conf.options : (_curveFiltersFallback[key] || [])
    out[key] = opts
  }
  // 级联过滤：优先使用后端提供的 options_by_parent
  const dn = config.value.nominal_dn
  const pr = config.value.pressure_rating
  const nt = config.value.nominal_trim
  for (const key of keys) {
    const conf = fc[key]
    if (!conf) continue
    // 使用 options_by_parent 级联
    if (conf.options_by_parent && typeof conf.options_by_parent === 'object') {
      const dep = conf.dependent_on
      const parentVal = dep ? config.value[dep] : null
      if (parentVal != null && parentVal !== '' && conf.options_by_parent[parentVal]) {
        out[key] = conf.options_by_parent[parentVal]
      }
    }
  }
  return out
})

// 阀座形式选项: 优先用后端 curve-options 返回的系列特定选项，否则用通用默认值
// 后端 options 可能是 [{value,label}] 对象数组，需要拍平成字符串数组给 el-option 使用
const seatTypeOptions = computed(() => {
  const fromFilter = filterOptions.value.seat_type
  if (fromFilter && fromFilter.length) {
    return fromFilter.map(o => (typeof o === 'object' && o !== null) ? (o.value ?? o.label ?? o) : String(o))
  }
  return COMMON_DATA.value.seat_types
})

// ---- Cv 曲线计算 ----
// evalEqcv: phi(Cv/Cvrated) -> stk(%Stk)
// 与 ValveTypes.vue 完全一致的实现 (ValveTypes.vue 已验证正确)
function evalEqcv(phi, strokeMode, eqcv, ratedCv, fstk) {
  if (phi <= 0) return 0
  if (phi >= 1) return 1
  const cvVal = phi * ratedCv  // 绝对 Cv 值, poly_cv_div100 用
  const c = eqcv || {}
  const a0 = c.a0 || 0, a1 = c.a1 || 0, a2 = c.a2 || 0
  const a3 = c.a3 || 0, a4 = c.a4 || 0, a5 = c.a5 || 0, a6 = c.a6 || 0

  switch (strokeMode) {
    case 'linear':
      return phi

    case 'ln_eqn': {
      const f = fstk || 50
      const stk = 1 + Math.log(phi) / Math.log(f)
      return Math.max(0, Math.min(1, stk))
    }

    case 'exp_formula': {
      // %Stk = Exp(A4*ln(Cv) + A3*Cv + A1/(Cv + A2) + A0) / divisor
      const lnCv = Math.log(Math.max(cvVal, 1e-9))
      let arg = a4 * lnCv + a3 * cvVal + a1 / (cvVal + a2) + a0
      if (arg > 700) arg = 700
      if (arg < -700) arg = -700
      const divisor = c.divisor || 60
      const stk = Math.exp(arg) / divisor
      return Math.max(0, Math.min(1, stk))
    }

    case 'poly_cv_div100': {
      // %Stk = (A4*Cv^4 + A3*Cv^3 + A2*Cv^2 + A1*Cv + A0) / 100
      let stk = a4*Math.pow(cvVal,4) + a3*Math.pow(cvVal,3) + a2*Math.pow(cvVal,2) + a1*cvVal + a0
      stk = stk / 100
      return Math.max(0, Math.min(1, stk))
    }

    case 'poly_phi100_div100': {
      // %Stk = (A5*(phi*100)^5 + ... + A0) / 100
      const x = phi * 100
      let stk = a5*Math.pow(x,5) + a4*Math.pow(x,4) + a3*Math.pow(x,3) + a2*Math.pow(x,2) + a1*x + a0
      stk = stk / 100
      return Math.max(0, Math.min(1, stk))
    }

    case 'poly_cv_div_angle':
    case 'poly_div60': {
      const divisor = c.divisor || 60
      let stk = a5*Math.pow(cvVal,5) + a4*Math.pow(cvVal,4) + a3*Math.pow(cvVal,3) + a2*Math.pow(cvVal,2) + a1*cvVal + a0
      stk = stk / divisor
      return Math.max(0, Math.min(1, stk))
    }

    case 'eq_index':
    default: {
      // 霍纳公式: %Stk 直接是 phi 的多项式 (0~1 输入 → 0~1 输出)
      let stk = ((a6*phi + a5)*phi + a4)*phi + a3
      stk = (stk*phi + a2)*phi + a1
      stk = stk*phi + a0
      return Math.max(0, Math.min(1, stk))
    }
  }
}

// evalStkToPhi: stk(%Stk) -> phi(Cv/Cvrated), 反解
function evalStkToPhi(stk, strokeMode, eqcv, ratedCv, fstk) {
  if (!strokeMode || strokeMode === 'linear') return stk
  if (strokeMode === 'ln_eqn') {
    const f = fstk || 50
    // stk = 1 + ln(phi)/ln(f)  →  phi = exp((stk-1)*ln(f))
    return Math.max(0, Math.min(1, Math.exp((stk - 1) * Math.log(f))))
  }
  if (['poly_cv_div100','poly_phi100_div100','poly_cv_div_angle','poly_div60','exp_formula','eq_index'].includes(strokeMode)) {
    // 二分法反解 (假设 phi->stk 单调递增)
    // 正确方向: stk2 > stk → phi 太大 → hi = phi
    let lo = 1e-6, hi = 1, phi = 0.5
    for (let i = 0; i < 100; i++) {
      phi = (lo + hi) / 2
      const stk2 = evalEqcv(phi, strokeMode, eqcv, ratedCv, fstk)
      if (stk2 > stk) hi = phi
      else lo = phi
    }
    return phi
  }
  return stk
}

function computeCvCurve(ratedCv, strokeMode, eqcv, fstk) {
  if (!ratedCv) return STANDARD_STROKES.map(s => ({ stk: s * 100, phi: s * 100, cv: 0 }))
  return STANDARD_STROKES.map(stk => {
    const phi = evalStkToPhi(stk, strokeMode, eqcv, ratedCv, fstk)
    const cv = phi * ratedCv
    return { stk: stk * 100, phi: phi * 100, cv }
  })
}

const cvCurvePoints = computed(() => {
  const m = curveInfo.stroke_mode || config.value.stroke_mode || ''
  const eq = curveInfo.eqcv || config.value.eqcv
  const fs = curveInfo.fstk || config.value.fstk
  const rc = curveInfo.rated_cv || config.value.rated_cv || 0
  return computeCvCurve(rc, m, eq, fs)
})

const strokeModeInfo = computed(() => {
  const m = curveInfo.stroke_mode || config.value.stroke_mode || ''
  const map = {
    linear: '线性特性 (Linear)',
    ln_eqn: '等百分比特性 (Equal Percentage)',
    eq_index: '指数特性 (Index Eq)',
    poly_cv_div100: '多项式 Cv/100',
    poly_phi100_div100: '多项式 φ100/100',
    exp_formula: '指数公式 (Exp)',
  }
  return map[m] || (m ? `特性模式: ${m}` : '')
})

const cvChartOption = computed(() => {
  const pts = cvCurvePoints.value
  const ratedCv = Number(curveInfo.rated_cv || config.value.rated_cv) || 1
  const activeCases = cases.value.filter(c => c.is_active !== false)
  const marks = []
  activeCases.forEach(c => {
    const r = results.value[c.id]
    if (!r) return
    const opening = r.cv_opening
    if (opening == null) return
    const stk = Math.max(0, Math.min(100, opening))
    // phi% = (cv_required / rated_cv) * 100 : 标记点的 Y 坐标应为实际需要的 Cv 百分比
    const phi_pct = r.cv_required != null ? (r.cv_required / ratedCv) * 100 : stk
    marks.push({
      name: `Case ${c.case_no}`,
      coord: [stk, Math.max(0, Math.min(100, phi_pct))],
      value: `${opening.toFixed(1)}%`,
      itemStyle: { color: '#e6a23c' },
    })
  })
  return {
    tooltip: { trigger: 'axis', formatter: (params) => {
      const p = params[0]
      if (!p) return ''
      const stkVal = p.value[0]?.toFixed(1)
      const phiVal = p.value[1]?.toFixed(1)
      const cvPoint = pts.find(pt => Math.abs(pt.stk - p.value[0]) < 1)
      const cvVal = cvPoint ? cvPoint.cv.toFixed(2) : '—'
      return `<b>Stk ${stkVal}%</b><br/>φ = ${phiVal}%<br/>Cv = ${cvVal}`
    }},
    grid: { left: 70, right: 20, top: 30, bottom: 60, containLabel: false },
    xAxis: { type: 'value', name: 'Valve Travel, %', min: 0, max: 100, splitNumber: 10 },
    yAxis: { type: 'value', name: '% of Rated Cv', min: 0, max: 100, splitNumber: 10 },
    series: [{
      type: 'line',
      smooth: true,
      data: pts.map(p => [p.stk, p.phi]),
      itemStyle: { color: '#409eff' },
      lineStyle: { width: 2 },
      symbol: 'circle',
      symbolSize: 6,
      markPoint: marks.length ? { data: marks, symbolSize: 50, label: { formatter: (p) => p.value || '' } } : undefined,
    }],
  }
})

// ---- 计算因数曲线 (FL / xT / Kc / Fd vs % 额定 Cv) ----
const FACTOR_META = [
  { key: 'fl', name: 'FL', color: '#2c3e50' },
  { key: 'xt', name: 'xT', color: '#e74c3c' },
  { key: 'kc', name: 'Kc', color: '#3498db' },
  { key: 'fd', name: 'Fd', color: '#27ae60' },
]

// 多项式 f(phi) = p0 + p1*phi + ... + p4*phi^4, 并按 value_min/max 钳制
function evalFactorPoly(c, phi) {
  if (!c) return null
  const p = [c.p0, c.p1, c.p2, c.p3, c.p4]
  if (!p.some(v => Number(v))) return c.value_min ?? null
  let v = 0
  for (let i = p.length - 1; i >= 0; i--) v = v * phi + (Number(p[i]) || 0)
  if (c.value_min != null) v = Math.max(v, c.value_min)
  if (c.value_max != null) v = Math.min(v, c.value_max)
  return v
}

const factorSeriesData = computed(() => {
  const cc = config.value.curve_coeffs || {}
  const scalar = k => {
    const n = Number(config.value[k])
    return Number.isFinite(n) ? n : null
  }
  const out = {}
  for (const m of FACTOR_META) {
    const c = m.key === 'xt' ? null : (cc[m.key] || null)
    const data = []
    for (let i = 0; i <= 100; i++) {
      const phi = i / 100
      let v
      if (m.key === 'xt') {
        // xT = 0.84 * FL^2
        const flv = cc.fl ? evalFactorPoly(cc.fl, phi) : scalar('fl')
        v = flv != null ? 0.84 * flv * flv : scalar('xt')
      } else {
        v = c ? evalFactorPoly(c, phi) : scalar(m.key)
      }
      if (v == null || !Number.isFinite(v)) continue
      data.push([i, Math.max(0, Math.min(1, v))])
    }
    out[m.key] = data
  }
  return out
})

const factorChartOption = computed(() => {
  const d = factorSeriesData.value
  const series = FACTOR_META
    .filter(m => d[m.key] && d[m.key].length)
    .map(m => ({
      name: m.name,
      type: 'line',
      smooth: true,
      showSymbol: false,
      data: d[m.key],
      lineStyle: { width: 2, color: m.color },
      itemStyle: { color: m.color },
    }))
  return {
    tooltip: { trigger: 'axis', valueFormatter: v => Number(v).toFixed(3) },
    legend: { bottom: 0, itemWidth: 14, itemHeight: 8, textStyle: { fontSize: 11 }, data: series.map(s => s.name) },
    grid: { left: 70, right: 20, top: 30, bottom: 60, containLabel: false },
    xAxis: { type: 'value', name: '% 额定 Cv', min: 0, max: 100, splitNumber: 10 },
    yAxis: { type: 'value', name: 'Sizing Indices', min: 0, max: 1, splitNumber: 5 },
    series,
  }
})

// ---- 阀门级联事件 ----
async function onValveStyleChange(skipClear = false) {
  const sc = config.value.valve_style
  if (!sc) { filterConfigs.value = {}; _curveFiltersFallback = {}; return }
  try {
    const data = await valveTypesApi.curveOptions(sc)
    filterConfigs.value = normalizeFilterConfigs(data?.filter_configs || data)
    const FALLBACK_KEY_MAP = {
      pressure_ratings: 'pressure_rating',
      trim_seat_types: 'trim_seat_type',
      flow_directions: 'flow_direction',
      trim_types: 'trim_characteristics',
    }
    if (data?.filters && typeof data.filters === 'object') {
      const fb = {}
      for (const [k, v] of Object.entries(data.filters)) {
        const targetKey = FALLBACK_KEY_MAP[k] || k
        if (!Array.isArray(v)) continue
        fb[targetKey] = v.map(o => {
          if (typeof o === 'string' || typeof o === 'number') return { value: o, label: String(o) }
          if (o.code != null) return { value: o.code, label: o.label || String(o.code) }
          return { value: o.value, label: o.label || String(o.value) }
        })
      }
      _curveFiltersFallback = fb
    } else {
      _curveFiltersFallback = {}
    }
    // 加载已有配置后不要清空 (skipClear=true 由 loadCalc 调用)
    if (skipClear) return
    // 清空下游
    config.value.nominal_dn = null
    config.value.pressure_rating = null
    config.value.nominal_trim = null
    config.value.flow_direction = null
    config.value.trim_characteristics = null
    config.value.trim_seat_type = null
  } catch (e) { console.warn('curveOptions 加载失败:', e) }
}

async function onDnChange() {
  // 清空下游
  config.value.nominal_trim = null
  config.value.flow_direction = null
  config.value.trim_characteristics = null
  config.value.trim_seat_type = null
  // 仅对无 nominal_trim 过滤器的系列 (BE/BC) 立即触发曲线参数查询
  // 有 nominal_trim 的系列 (GV/GC) 需等用户选完 trim 后再查
  const hasTrimFilter = filterConfigs.value?.nominal_trim
  if (!hasTrimFilter) await onTrimChange()
}

async function onTrimChange() {
  const sc = config.value.valve_style
  const dn = config.value.nominal_dn
  // BE/BC 球阀门芯尺寸 = 阀门口径, 无独立 nominal_trim 过滤器
  // 若 trim 为空且当前系列无 nominal_trim 过滤器, 用 dn 作为 trim
  let trim = config.value.nominal_trim
  const hasTrimFilter = filterConfigs.value?.nominal_trim
  if ((trim == null || trim === '') && !hasTrimFilter && dn) trim = dn
  if (!sc || dn == null) return
  try {
    const data = await valveTypesApi.curvesBySelection(sc, {
      nominal_dn: dn,
      nominal_trim: trim,
      trim_type: config.value.trim_seat_type || null,
      flow_direction: config.value.flow_direction || null,
      trim_characteristics: config.value.trim_characteristics || null,
      seat_type: config.value.seat_type_front || null,
      plug_size: 0,
    })
      if (data?.stroke_mode || data?.eqcv || data?.stroke_info) {
      curveInfo.stroke_mode = data.stroke_mode || data.cfg?.stroke_mode || ''
      curveInfo.eqcv = data.eqcv || data.stroke_info?.coeffs || null
      curveInfo.fstk = data.fstk ?? data.stroke_info?.fstk ?? null
      curveInfo.rated_cv = data.stroke_info?.rated_cv ?? null
      curveInfo.stroke_value = data.stroke_info?.stroke_value ?? null
      curveInfo.stroke_unit = data.stroke_info?.stroke_unit ?? null
      curveInfo.seat_type = data.seat_type ?? data.stroke_info?.seat_type ?? null
      curveInfo.fl = data.fl?.value ?? null
      curveInfo.fd = data.fd?.value ?? null
      curveInfo.xt = data.xT?.value ?? null
      curveInfo.kc = data.kc?.value ?? null
      // 同步到 config（用于保存）
      config.value.stroke_mode = curveInfo.stroke_mode
      config.value.eqcv = curveInfo.eqcv
      config.value.fstk = curveInfo.fstk
      // 自动填充到 config (el-input 需要字符串)
      if (curveInfo.rated_cv != null) config.value.rated_cv = String(curveInfo.rated_cv)
      if (curveInfo.stroke_value != null) config.value.stroke_value = String(curveInfo.stroke_value)
      if (curveInfo.stroke_unit) config.value.stroke_unit = curveInfo.stroke_unit
      if (curveInfo.seat_type) config.value.seat_type_front = curveInfo.seat_type
      if (curveInfo.fl != null) config.value.fl = curveInfo.fl
      if (curveInfo.fd != null) config.value.fd = curveInfo.fd
      if (curveInfo.xt != null) config.value.xt = curveInfo.xt
      if (curveInfo.kc != null) config.value.kc = curveInfo.kc
      // 提取开度修正因子曲线多项式系数 (FL/Kc/Fd vs φ)
      const _extractCurve = (c) => {
        if (!c || typeof c !== 'object') return null
        const out = {}
        for (const k of ['p0', 'p1', 'p2', 'p3', 'p4', 'value_min', 'value_max']) {
          if (c[k] != null) out[k] = c[k]
        }
        return Object.keys(out).length > 0 ? out : null
      }
      const cc = {}
      const flC = _extractCurve(data.fl)
      const kcC = _extractCurve(data.kc)
      const fdC = _extractCurve(data.fd)
      if (flC) cc.fl = flC
      if (kcC) cc.kc = kcC
      if (fdC) cc.fd = fdC
      config.value.curve_coeffs = Object.keys(cc).length > 0 ? cc : null
      ElMessage.success('曲线参数已自动填充')
    }
  } catch (e) {
    console.warn('curvesBySelection 加载失败:', e)
    // 曲线数据不可用时使用线性兜底
    curveInfo.stroke_mode = 'linear'
    ElMessage.warning('曲线参数加载失败，使用线性近似')
  }
}

// ---- 单位字典加载 ----
async function loadUnits() {
  try {
    const d = await unitsApi.list()
    for (const [cat, arr] of Object.entries(d.categories)) units[cat] = arr
    Object.assign(unitDefaults, d.defaults)
  } catch (e) { console.warn('单位字典加载失败:', e) }
}

// ---- 默认工况工厂 ----
function defaultCase() {
  // 若设计数据已选定阀前管道规格, 把内径/壁厚按当前所选单位预填到新 case
  let pipeDiameter = null, pipeWall = null
  const specKey = config.value?.pipe_spec_front
  if (specKey) {
    const found = pipeDataList.value.find(p => p.lookup_key === specKey)
    if (found) {
      if (found.id_mm != null) pipeDiameter = convertMmTo(found.id_mm, caseUnits.pipe_diameter)
      if (found.thk_mm != null) pipeWall = convertMmTo(found.thk_mm, caseUnits.pipe_wall)
    }
  }
  return {
    case_no: 1, case_name: '', fluid_id: fluids.value[0]?.id ?? null, fluid_name_custom: '', fluid_formula_custom: '', fluid_state_override: '',
    p1: null, p2: null, t1: null,
    flow_mass: null, flow_vol: null, flow_unit: 'mass',
    density_override: null, viscosity_override: null, molecular_weight_override: null, gamma_override: null,
    pipe_diameter: pipeDiameter, pipe_wall: pipeWall, distance: 1.0,
    mass_flow_gas: null, mass_flow_liquid: null, twophase_method: 'additive',
    density_gas: null, density_liquid: null,
    is_active: true,
  }
}

// ---- 格式化工具 ----
function fmt(v) { return v == null || v === '' ? '—' : (typeof v === 'number' ? (Math.abs(v) >= 100 ? v.toFixed(1) : v.toFixed(2)) : v) }
function fmt4(v) { return v == null ? '—' : Number(v).toFixed(4) }
function phaseText(p) { return ({liquid:'液态',gas:'气态',steam:'蒸汽',saturated:'饱和',twophase:'两相'}[p]) || p || '—' }
function phaseTag(p) { return ({liquid:'primary',gas:'warning',steam:'warning',saturated:'success',twophase:'danger'}[p]) || 'info' }
function regimeText(r) { return r || '—' }
function regimeTag(r) { return r && r.includes('阻塞') ? 'danger' : (r && r.includes('临界') ? 'danger' : (r && r.includes('闪蒸') ? 'warning' : 'success')) }
function openingClass(o) { if (o == null) return {}; if (o > 100) return {val:'val-warn'}; if (o > 90 || o < 10) return {val:'val-warn'}; return {} }
function noiseClass(n) { if (n == null) return {}; if (n > 85) return {val:'val-danger'}; if (n > 75) return {val:'val-warn'}; return {} }

// ---- 压力转 kPa 绝压 ----
function convertToKpaAbs(value, unitCode) {
  if (value == null) return null
  const u = (units.pressure || []).find(x => x.unit_code === unitCode)
  if (!u) return value
  return value * u.factor + u.offset
}
function calcDeltaP(c) {
  if (c.p1 == null || c.p2 == null) return null
  const p1 = convertToKpaAbs(c.p1, caseUnits.p1)
  const p2 = convertToKpaAbs(c.p2, caseUnits.p2)
  return (p1 - p2).toFixed(1)
}

// ---- CRUD ----
async function loadValve() { valve.value = await valvesApi.get(pid.value, vid.value) }
async function loadCalcs() {
  calcs.value = await calcApi.list(vid.value)
  if (!calcs.value.length) {
    await calcApi.create(vid.value, { version_label: 'V1', calc_standard: 'IEC60534' })
    calcs.value = await calcApi.list(vid.value)
  }
  const cur = calcs.value.find(c => c.is_current) || calcs.value[0]
  currentCid.value = cur.id
  await loadCalc()
}
async function loadCalc() {
  if (!currentCid.value) return
  const data = await calcApi.get(vid.value, currentCid.value)
  calc.value = data.calculation
  config.value = data.valve_config || defaultConfig()
  // 恢复曲线信息（从已保存的 config 内部字段）
  curveInfo.stroke_mode = config.value.stroke_mode || ''
  curveInfo.eqcv = config.value.eqcv || null
  curveInfo.fstk = config.value.fstk ?? null
  curveInfo.rated_cv = config.value.rated_cv ?? null
  curveInfo.stroke_value = config.value.stroke_value ?? null
  curveInfo.stroke_unit = config.value.stroke_unit ?? null
  curveInfo.seat_type = config.value.seat_type_front ?? null
  curveInfo.fl = config.value.fl ?? null
  curveInfo.fd = config.value.fd ?? null
  curveInfo.xt = config.value.xt ?? null
  curveInfo.kc = config.value.kc ?? null
  // curve_coeffs 已随 config 保存/恢复, 无需额外处理
  // 加载筛选器配置 (onValveStyleChange 会自动调用 curve-options API)
  // skipClear=true 防止覆盖已恢复的 config 下游字段
  if (config.value.valve_style) {
    await onValveStyleChange(true)
    // 如果有 nomina_dn, 从后端获取最新曲线参数 (rated_cv/stroke_value/eqcv/fd/fl 等)
    if (config.value.nominal_dn) {
      await onTrimChange()
    }
  }
  cases.value = (data.cases || []).map(c => ({
    ...defaultCase(),
    ...c,
  }))
  results.value = data.results || {}
  // 已保存结果中的开度可能由后端按线性假设或旧曲线系数算出, 与当前曲线不一致,
  // 加载时按当前 Cv vs 行程曲线重新插值, 保证图上开度点落在曲线上
  const ratedCvLoad = Number(curveInfo.rated_cv ?? config.value.rated_cv) || 0
  if (ratedCvLoad > 0) {
    Object.values(results.value).forEach(r => {
      if (r && r.cv_required != null) {
        r.cv_opening = computeOpeningByCurve(r.cv_required, ratedCvLoad)
      }
    })
  }
  // 从第一个 case 提取已保存的单位到 caseUnits
  if (cases.value.length > 0) {
    const c0 = cases.value[0]
    if (c0.p1_unit) caseUnits.p1 = c0.p1_unit
    if (c0.p2_unit) caseUnits.p2 = c0.p2_unit
    if (c0.t1_unit) caseUnits.t1 = c0.t1_unit
    if (c0.flow_mass_unit) caseUnits.flow_mass = c0.flow_mass_unit
    if (c0.flow_vol_unit) caseUnits.flow_vol = c0.flow_vol_unit
    if (c0.pipe_diameter_unit) caseUnits.pipe_diameter = c0.pipe_diameter_unit
    if (c0.pipe_wall_unit) caseUnits.pipe_wall = c0.pipe_wall_unit
    if (c0.distance_unit) caseUnits.distance = c0.distance_unit
    if (c0.mass_flow_gas_unit) caseUnits.mass_flow_gas = c0.mass_flow_gas_unit
    if (c0.mass_flow_liquid_unit) caseUnits.mass_flow_liquid = c0.mass_flow_liquid_unit
    if (c0.density_gas_unit) caseUnits.density_gas = c0.density_gas_unit
    if (c0.density_liquid_unit) caseUnits.density_liquid = c0.density_liquid_unit
    if (c0.density_override_unit) caseUnits.density_override = c0.density_override_unit
    if (c0.viscosity_override_unit) caseUnits.viscosity_override = c0.viscosity_override_unit
    if (c0.molecular_weight_override_unit) caseUnits.molecular_weight_override = c0.molecular_weight_override_unit
  }
}
function defaultConfig() {
  return {
    valve_style: 'GV120',
    flow_characteristic: '等百分比',
    port_diameter: 50,
    rated_cv: 80,
    fl: 0.9, xt: 0.72, fd: 0.46, flp: null, xtp: null, fp: null, kc: null, stages: 1,
    // 阀门选型字段
    nominal_dn: null,
    nominal_trim: null,
    flow_direction: null,
    trim_characteristics: null,
    trim_seat_type: null,
    pressure_rating: null,
    stroke_value: null,
    stroke_unit: null,
    rangeability: 50,
    design_pressure: null,
    design_temp: null,
    close_dp: null,
    // === 设计数据卡片（阀前/阀后分栏） ===
    pipe_spec_front: null,
    pipe_spec_back: null,
    pipe_size_front: null,
    pipe_size_back: null,
    sch_front: null,
    sch_back: null,
    pipe_material_front: null,
    pipe_material_back: null,
    // === 阀门计算数据 - 阀后字段（默认同前） ===
    nominal_dn_back: null,
    pressure_rating_back: null,
    seat_type_front: null,
    seat_type_back: null,
    // === 阀门选型数据 - 连接相关（阀前/阀后分栏） ===
    connection_type_front: null,
    connection_type_back: null,
    face_type_front: null,
    face_type_back: null,
    flange_standard_front: null,
    flange_standard_back: null,
    pipe_accessory_front: null,
    pipe_accessory_back: null,
    pipe_material_2_front: null,
    pipe_material_2_back: null,
    // === 阀门选型数据 - 阀体属性（不分栏，单一值） ===
    body_material: null,
    bonnet_material: null,
    bonnet_form: null,
    jacket_connection: null,
    packing_type: null,
    packing_material: null,
    trim_material: null,
    seat_material: null,
    sleeve_material: null,
    stem_material: null,
    balance_seal_ring: null,
    // 兼容旧字段名（已被 front/back 分栏替代）
    connection_type: null,
    face_type: null,
    // 曲线内部存储
    stroke_mode: null,
    eqcv: null,
    fstk: null,
    curve_coeffs: null,  // 开度修正因子曲线多项式系数 {fl:{p0-p4,value_min,max}, kc:..., fd:...}
  }
}
function onVersionChange() { loadCalc() }
async function newVersion() {
  const { value } = await ElMessageBox.prompt('输入版本说明(可留空)', '新建计算版本', { inputPlaceholder: '如：变更阀门类型' })
  await calcApi.create(vid.value, { version_label: value || undefined, calc_standard: 'IEC60534' })
  ElMessage.success('已新建版本')
  await loadCalcs()
}
async function setCurrent() {
  await calcApi.setCurrent(vid.value, currentCid.value)
  ElMessage.success('已设为当前版本')
  calcs.value = await calcApi.list(vid.value)
}
async function saveConfig() {
  try {
    await calcApi.saveConfig(vid.value, currentCid.value, config.value)
    ElMessage.success('配置已保存')
  } catch (e) { ElMessage.error(e.message) }
}
function onFluidChange(c, val) {
  if (val == null || val === '') return
  if (typeof val === 'number') {
    const f = fluids.value.find(x => x.id === val)
    if (f) {
      c.fluid_name_custom = ''
      c.fluid_formula_custom = f.formula || ''
      // 每次切换都覆盖
      c.molecular_weight_override = f.molecular_weight ?? c.molecular_weight_override
      c.gamma_override = f.cp_cv_ratio ?? c.gamma_override
      if (f.viscosity != null) c.viscosity_override = f.viscosity
      const is_gas = (f.default_state === 'gas')
      // 密度 & 默认单位
      if (is_gas) {
        c.density_override = f.density_gas ?? null
        caseUnits.density_override = 'kg_Nm3'
      } else {
        c.density_override = f.density_liquid ?? f.density_gas ?? null
        caseUnits.density_override = 'kg_m3'
      }
      // 流量默认单位：气体 → 标况体积流量 Nm3/h；液体 → 质量流量 kg/h
      if (is_gas) {
        c.flow_unit = 'vol'
        caseUnits.flow_vol = 'Nm3_h'
        caseUnits.flow_mass = 'kg_h'
      } else {
        c.flow_unit = 'mass'
        caseUnits.flow_mass = 'kg_h'
      }
    }
  } else if (typeof val === 'string') {
    c.fluid_name_custom = val.trim()
    c.molecular_weight_override = null
    c.gamma_override = null
    c.density_override = null
    c.viscosity_override = null
    ElMessage.warning(`已选择自定义介质 "${c.fluid_name_custom}"，请手动填写密度、粘度、摩尔质量、比热比等物性参数`)
  }
}

// 保存/计算前清洗 cases：把 string 型 fluid_id 转为 null + 同步到 fluid_name_custom
function _normalizeCasesForSave(casesArr) {
  for (const c of casesArr) {
    if (typeof c.fluid_id === 'string' && c.fluid_id.trim()) {
      c.fluid_name_custom = c.fluid_name_custom?.trim() || c.fluid_id.trim()
      c.fluid_id = null
    } else if (c.fluid_id == null && !c.fluid_name_custom?.trim()) {
      c.fluid_id = null  // 两者都空的情况交由后端校验拦截
    }
  }
}

function addCase() {
  if (cases.value.length >= MAX) return
  const no = cases.value.length ? Math.max(...cases.value.map(c => c.case_no)) + 1 : 1
  const nc = defaultCase()
  nc.case_no = no
  cases.value.push(nc)
}
function removeCase(i) {
  cases.value.splice(i, 1)
  cases.value.forEach((c, j) => c.case_no = j + 1)
}

// 将 caseUnits 复制到每个 case 的 *_unit 字段（保存前调用）
function applyUnitsToCases() {
  cases.value.forEach(c => {
    c.p1_unit = caseUnits.p1
    c.p2_unit = caseUnits.p2
    c.t1_unit = caseUnits.t1
    c.flow_mass_unit = caseUnits.flow_mass
    c.flow_vol_unit = caseUnits.flow_vol
    c.pipe_diameter_unit = caseUnits.pipe_diameter
    c.pipe_wall_unit = caseUnits.pipe_wall
    c.distance_unit = caseUnits.distance
    c.mass_flow_gas_unit = caseUnits.mass_flow_gas
    c.mass_flow_liquid_unit = caseUnits.mass_flow_liquid
    c.density_gas_unit = caseUnits.density_gas
    c.density_liquid_unit = caseUnits.density_liquid
    c.density_override_unit = caseUnits.density_override
    c.viscosity_override_unit = caseUnits.viscosity_override
    c.molecular_weight_override_unit = caseUnits.molecular_weight_override
  })
}

async function saveCasesOnly() {
  _normalizeCasesForSave(cases.value)
  const saved = await calcApi.saveCases(vid.value, currentCid.value, cases.value)
  // 用服务端返回的(含 id) 合并回原对象（保留用户选的单位）
  const savedMap = {}
  for (const s of saved) savedMap[s.case_no] = s
  cases.value = cases.value.map(c => ({ ...savedMap[c.case_no], ...c }))
}

async function saveCases() {
  if (!cases.value.length) { ElMessage.warning('请至少添加一组工况'); return }
  cases.value.forEach((c, i) => c.case_no = i + 1)
  applyUnitsToCases()
  try {
    // 保存配置 + 工况（二者都保存，确保 Valve 主表数据同步）
    await calcApi.saveConfig(vid.value, currentCid.value, config.value)
    await saveCasesOnly()
    ElMessage.success('配置与工况已保存（阀门参数已同步回写）')
  } catch (e) { ElMessage.error(e.message) }
}

// 根据 Cv vs Travel 曲线插值计算开度, 无曲线时按流量特性标准公式兜底
// @param cvRequired 所需 Cv
// @param ratedCv 额定 Cv
// @returns 开度 % (0~100)
function computeOpeningByCurve(cvRequired, ratedCv) {
  if (ratedCv <= 0 || cvRequired == null) return 0
  const pts = cvCurvePoints.value || []
  // 有效曲线判定: 至少 2 个不同的 cv 值, 且不全为 0
  const validCvs = pts.map(p => p.cv).filter(v => v > 0)
  const hasCurve = pts.length >= 2 && validCvs.length >= 1
    && Math.max(...pts.map(p => p.cv)) > 0

  if (hasCurve) {
    // 按 cv 升序, 线性插值求 stk
    const sorted = [...pts].sort((a, b) => a.cv - b.cv)
    // cvRequired 超出上限 → 100%
    if (cvRequired >= sorted[sorted.length - 1].cv) return 100
    // 低于下限 → 钳制到最小点的 stk
    if (cvRequired <= sorted[0].cv) return Math.max(0, sorted[0].stk)
    // 找相邻两点
    for (let i = 1; i < sorted.length; i++) {
      const p0 = sorted[i - 1], p1 = sorted[i]
      if (cvRequired >= p0.cv && cvRequired <= p1.cv) {
        const span = p1.cv - p0.cv || 1
        const ratio = (cvRequired - p0.cv) / span
        return p0.stk + ratio * (p1.stk - p0.stk)
      }
    }
  }

  // 无曲线 → 按流量特性标准公式
  const tc = (config.value.trim_characteristics || '').toString().toUpperCase()
  const phi = cvRequired / ratedCv
  if (tc.includes('LINEAR') || tc.includes('线性')) {
    // 线性: %Cv = %Stk
    return phi * 100
  }
  // 等百分比标准公式: phi = R^(stk/100 - 1), R=可调比 (默认50)
  // 反解: stk = (ln(phi)/ln(R) + 1) * 100
  if (phi <= 0) return 0
  const R = Number(config.value.rangeability) || 50
  const stk = (Math.log(phi) / Math.log(R) + 1) * 100
  return Math.max(0, Math.min(100, stk))
}

async function runCalc() {
  if (!cases.value.length) { ElMessage.warning('请先添加并保存工况'); return }
  cases.value.forEach((c, i) => c.case_no = i + 1)
  applyUnitsToCases()
  running.value = true
  try {
    // 先保存配置与工况，再执行计算（计算时也会回写 Valve 表）
    await calcApi.saveConfig(vid.value, currentCid.value, config.value)
    await saveCasesOnly()
    const out = await calcApi.run(vid.value, currentCid.value)
    const map = {}
    const ratedCv = curveInfo.rated_cv || config.value.rated_cv || 0
    cases.value.forEach((c, i) => {
      if (!out[i]) return
      const r = { ...out[i] }
      // 用 Cv vs Travel 曲线插值重算开度 (覆盖后端线性假设值)
      if (r.cv_required != null) {
        r.cv_opening = computeOpeningByCurve(r.cv_required, ratedCv)
      }
      map[c.id] = r
    })
    results.value = map
    calc.value.status = '已计算'
    ElMessage.success('计算完成（阀门参数已同步回写）')
  } catch (e) { ElMessage.error(e.message) }
  finally { running.value = false }
}

async function init() {
  loading.value = true
  try {
    await Promise.all([loadUnits(), loadPipeData()])
    fluids.value = await fluidsApi.list()
    valveTypes.value = await valveTypesApi.list()
    await loadValve()
    await loadCalcs()
  } catch (e) { ElMessage.error(e.message) }
  finally { loading.value = false }
}

// 曲线计算联动：stroke_mode / eqcv / fstk 变化时触发 cvCurvePoints computed 自动重算
// 已通过 cvCurvePoints computed 间接实现，无需额外 watch

// === 阀前 → 阀后 自动同步 watch ===
// 同步规则：当 back 为空 或 back 等于旧的 front 值（即 back 从未被用户手工修改过）时，front 变化自动同步到 back
function _setupFrontBackSync(frontKey, backKey) {
  watch(
    () => config.value[frontKey],
    (newVal, oldVal) => {
      if (newVal === oldVal) return
      const curBack = config.value[backKey]
      if (curBack == null || curBack === '' || curBack === oldVal) {
        config.value[backKey] = newVal
      }
    }
  )
}
// 设计数据卡片
_setupFrontBackSync('pipe_spec_front', 'pipe_spec_back')
_setupFrontBackSync('pipe_size_front', 'pipe_size_back')
_setupFrontBackSync('sch_front', 'sch_back')
_setupFrontBackSync('pipe_material_front', 'pipe_material_back')
// 阀门计算数据 - 阀座形式
_setupFrontBackSync('seat_type_front', 'seat_type_back')
// 阀门选型数据 - 连接相关
_setupFrontBackSync('connection_type_front', 'connection_type_back')
_setupFrontBackSync('face_type_front', 'face_type_back')
_setupFrontBackSync('flange_standard_front', 'flange_standard_back')
_setupFrontBackSync('pipe_accessory_front', 'pipe_accessory_back')
_setupFrontBackSync('pipe_material_2_front', 'pipe_material_2_back')

// 同步按钮：把 back 重置为 front
function syncBackToFront(frontKey, backKey) {
  config.value[backKey] = config.value[frontKey]
}

// pipe_spec_back 被同步或手动变更时, 自动填充 pipe_size_back / sch_back / pipe_wall_back
watch(() => config.value.pipe_spec_back, (val) => {
  if (!val) return
  const found = pipeDataList.value.find(p => p.lookup_key === val)
  if (found) {
    config.value.pipe_size_back = fmtImperialMetric(found.nps_label, found.dn_mm)
    if (found.schedule) config.value.sch_back = found.schedule
    config.value.pipe_wall_back = fmtImperialMetric(found.thk_in, found.thk_mm)
  }
})

watch(() => route.params.vid, (v) => { if (v) init() })
onMounted(() => { loadPublicOptions(); init() })
</script>

<style scoped>
.calc-page { display: flex; flex-direction: column; height: 100%; gap: 12px; }
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
.section-footer { margin-top: 10px; display: flex; align-items: center; gap: 10px; }
.empty-hint { text-align: center; padding: 30px 0; color: #909399; display: flex; flex-direction: column; gap: 10px; align-items: center; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 20px; }
.form-grid .form-row.full-width { grid-column: 1 / -1; }
.form-row { display: flex; align-items: center; gap: 10px; }
.form-row label { min-width: 110px; font-size: 12px; color: #606266; text-align: right; flex-shrink: 0; }
.form-row label sub { font-size: 10px; }
.unit-inline { font-size: 12px; color: #909399; }
/* 设计压力/温度/压差：单位占位使输入框宽度与上方"管道材质"阀前列对齐 */
.unit-design { flex: 1; min-width: 0; text-align: left; padding-right: 42px; }

/* 推荐 SCH 对话框 */
.sch-form { display: flex; flex-direction: column; gap: 8px; }
.sch-form-row { display: flex; align-items: center; gap: 8px; }
.sch-form-row .sch-label { min-width: 90px; font-size: 12px; color: #606266; text-align: right; }
.sch-form-row .sch-unit { font-size: 12px; color: #909399; }

.cases-table-wrapper { overflow-x: auto; }
/* 列宽策略：所有列显式固定 width，两表保持一致；table-layout:fixed 保证严格按 colgroup 分配 */
.cases-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.cases-table .col-label { width: 160px; }
.cases-table .col-case { width: 150px; }
.cases-table .col-add { width: 60px; }
.cases-table th, .cases-table td { border: 1px solid #ebeef5; padding: 4px 6px; font-size: 12px; vertical-align: middle; background: #fff; }
.cases-table .th-label { background: #f5f7fa; color: #606266; font-weight: 600; text-align: left; width: 160px; position: sticky; left: 0; z-index: 2; }
.cases-table .th-case { width: 150px; }
.cases-table .th-case { background: #ecf5ff; text-align: center; padding: 6px 4px; }
.cases-table .th-add { background: #fafafa; color: #909399; cursor: pointer; text-align: center; height: 60px; font-size: 12px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; border: 1px dashed #dcdfe6; width: 60px; }
.cases-table .th-add:hover:not(.th-add-disabled) { background: #f0f9eb; color: #67c23a; border-color: #67c23a; }
.cases-table .th-add-disabled { border-color: transparent; background: #fff; cursor: default; height: auto; min-height: 24px; }
.cases-table .td-add { width: 60px; border: 1px solid #ebeef5; background: #fff; }
.cases-table .td-add-disabled { border-color: transparent; background: #fff; }
.cases-table .td-label { background: #fafbfc; font-weight: 500; color: #606266; position: sticky; left: 0; z-index: 1; overflow: hidden; }
.cases-table .td-label .lbl { font-size: 12px; }
.cases-table .val-delta { text-align: center; background: #f0f9ff; color: #409eff; font-weight: 600; white-space: nowrap; }
.cases-table .sep-line { font-size: 12px; color: #909399; background: #fafafa; letter-spacing: 1px; }
.cases-table tr.section-sep td { text-align: center; padding: 4px; font-size: 11px; border-top: 2px solid #e4e7ed; border-bottom: 1px solid #ebeef5; }
.cases-table tr.section-sep.clickable td.sep-line-clickable { cursor: pointer; user-select: none; transition: background .2s; }
.cases-table tr.section-sep.clickable:hover td.sep-line-clickable { background: #f0f9ff; color: #409eff; border-top-color: #409eff; }
.cases-table .sep-line .collapse-icon { display: inline-flex; align-items: center; margin-right: 6px; transition: transform .25s; }
.cases-table .sep-line .collapse-icon .rotate { transform: rotate(90deg); }
.cases-table .sep-line .collapse-hint { margin-left: 10px; font-size: 11px; }

.case-header { display: flex; align-items: center; justify-content: space-between; gap: 4px; }
.case-no { font-weight: 700; color: #409eff; font-size: 13px; }
.case-actions { display: flex; align-items: center; gap: 2px; }
.case-name-input { margin-top: 4px; }

/* 参数名 + 单位下拉框（同行水平排列，不超出列宽） */
.label-with-unit { display: flex; flex-direction: row; align-items: center; justify-content: flex-end; gap: 4px; width: 100%; box-sizing: border-box; overflow: hidden; }
.label-with-unit .lbl { font-size: 12px; flex: 0 0 auto; margin-right: auto; /* 标签靠左，单位选择器靠右 */ }
.label-with-unit .unit-select { width: 84px !important; flex-shrink: 0; /* 加宽以容纳 kg/kmol 等较长单位 */ }

.unit-badge { font-size: 11px; color: #909399; margin-left: 4px; }

.cases-table :deep(.el-input-number), .cases-table :deep(.el-select), .cases-table :deep(.el-input) { width: 100%; }

/* 结果表 — 列宽与工艺工况表严格一致（col-label 160px, col-case 150px, col-add 60px 占位列） */
.result-table-wrapper { overflow-x: auto; }
.result-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.result-table .col-label { width: 160px; }
.result-table .col-case { width: 150px; }
.result-table .col-add { width: 60px; }
.result-table th, .result-table td { border: 1px solid #ebeef5; padding: 5px 8px; font-size: 12px; vertical-align: middle; }
.result-table .th-label { background: #f5f7fa; text-align: left; font-weight: 600; color: #606266; width: 160px; position: sticky; left: 0; z-index: 2; }
.result-table .th-case { width: 150px; background: #ecf5ff; text-align: center; font-weight: 600; color: #303133; }
.result-table .th-add-placeholder { width: 60px; background: #fafafa; padding: 0; border: 1px solid transparent; }
.result-table .td-add-placeholder { width: 60px; background: #fff; padding: 0; border: 1px solid transparent; }
.result-table .case-sub { font-weight: 400; color: #909399; font-size: 11px; }
.result-table .td-label { background: #fafbfc; font-weight: 500; color: #606266; width: 160px; position: sticky; left: 0; z-index: 1; overflow: hidden; }
.result-table .val-strong { font-weight: 700; color: #1a73e8; font-size: 13px; text-align: center; }
.result-table .val-warn { color: #e6a23c; font-weight: 600; }
.result-table .val-danger { color: #f56c6c; font-weight: 700; font-size: 13px; text-align: center; }
.result-table .regime-detail { font-size: 11px; color: #909399; }
.result-table tr.section-sep td { text-align: center; padding: 4px; font-size: 11px; font-weight: 600; color: #409eff; border-top: 2px solid #e4e7ed; border-bottom: 1px solid #ebeef5; background: #f0f9ff; }
.result-table tbody tr:hover td { background: #f5f7fa; }

.warnings-list { display: flex; flex-direction: column; gap: 6px; }
.warning-item { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 4px; font-size: 13px; }
.warning-item.danger { background: #fef0f0; color: #f56c6c; border-left: 3px solid #f56c6c; }
.warning-item.warn { background: #fdf6ec; color: #e6a23c; border-left: 3px solid #e6a23c; }
.warning-item.info { background: #f4f4f5; color: #909399; border-left: 3px solid #909399; }

.col-form::-webkit-scrollbar, .col-result::-webkit-scrollbar { width: 8px; }
.col-form::-webkit-scrollbar-thumb, .col-result::-webkit-scrollbar-thumb { background: #dcdfe6; border-radius: 4px; }
.col-form::-webkit-scrollbar-track, .col-result::-webkit-scrollbar-track { background: transparent; }

/* 底部曲线图：Cv vs 行程 与 计算因数 并排 */
.charts-row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; }
.charts-row .chart-card { padding: 14px 12px; }
.chart-card .calc-chart { width: 100%; height: 320px; }

/* ===== 设计数据 / 选型数据 分栏（阀前 | 阀后）样式 ===== */
.pipe-header-row { margin-bottom: 2px; }
.pipe-col-label { flex: 1; text-align: center; font-size: 12px; font-weight: 600; color: #606266; background: #ecf5ff; border-radius: 3px; padding: 2px 0; }
.pipe-col-sync { width: 32px; flex-shrink: 0; }

/* 有分栏的 form-row：label + 阀前控件 + 阀后控件 + 同步按钮 */
.form-row .el-select, .form-row .el-input, .form-row .el-input-number { flex: 1; min-width: 0; }
.form-row .el-button.link { flex-shrink: 0; width: 32px; padding: 0; }

/* 子分组（连接相关 / 阀体属性） */
.form-sub-group { margin-bottom: 14px; padding: 8px 10px; background: #fafbfc; border-radius: 4px; border-left: 3px solid #409eff; }
.form-sub-group + .form-sub-group { border-left-color: #67c23a; }
.form-sub-title { font-size: 13px; font-weight: 600; color: #303133; margin-bottom: 8px; }
</style>
