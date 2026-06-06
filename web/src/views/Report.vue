<template>
  <div>
    <h2 style="margin-bottom: 20px">📋 账单报表</h2>

    <!-- Period selector -->
    <div style="margin-bottom: 20px">
      <el-radio-group v-model="periodType" @change="loadReport">
        <el-radio-button value="month">月度</el-radio-button>
        <el-radio-button value="quarter">季度</el-radio-button>
        <el-radio-button value="year">年度</el-radio-button>
      </el-radio-group>

      <template v-if="periodType === 'month'">
        <el-date-picker
          v-model="monthValue"
          type="month"
          placeholder="选择月份"
          @change="loadReport"
          style="margin-left: 16px; width: 200px"
        />
      </template>

      <template v-if="periodType === 'quarter'">
        <el-select v-model="quarterYear" @change="loadReport" placeholder="选择季度" style="margin-left: 16px; width: 150px">
          <el-option v-for="y in years" :key="y" :label="y + '年'" :value="y" />
        </el-select>
        <el-select v-model="quarterNum" @change="loadReport" placeholder="Q" style="margin-left: 8px; width: 100px">
          <el-option v-for="q in [1,2,3,4]" :key="q" :label="'Q' + q" :value="q" />
        </el-select>
      </template>

      <template v-if="periodType === 'year'">
        <el-select v-model="yearValue" @change="loadReport" placeholder="选择年份" style="margin-left: 16px; width: 150px">
          <el-option v-for="y in years" :key="y" :label="y + '年'" :value="y" />
        </el-select>
      </template>
    </div>

    <!-- Summary -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="8">
        <el-card shadow="hover">
          <div style="text-align: center">
            <div style="font-size: 24px; font-weight: bold; color: #e53e3e">¥{{ format(data.total) }}</div>
            <div style="color: #718096; margin-top: 4px">总应还</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div style="text-align: center">
            <div style="font-size: 24px; font-weight: bold; color: #3182ce">¥{{ format(data.min_total) }}</div>
            <div style="color: #718096; margin-top: 4px">最低还款</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div style="text-align: center">
            <div style="font-size: 24px; font-weight: bold; color: #38a169">¥{{ format(data.total - data.min_total) }}</div>
            <div style="color: #718096; margin-top: 4px">可差额</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>各银行应还金额</template>
          <v-chart :option="barOption" autoresize style="height: 320px" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>占比分布</template>
          <v-chart :option="pieOption" autoresize style="height: 320px" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Bank months detail -->
    <el-card shadow="hover">
      <template #header>各卡明细</template>
      <el-table :data="detailRows" stripe size="small">
        <el-table-column prop="bank" label="银行" />
        <el-table-column prop="holder_name" label="持卡人" width="80">
          <template #default="{ row }">{{ row.holder_name || '—' }}</template>
        </el-table-column>
        <el-table-column prop="card" label="卡号" width="100" />
        <el-table-column prop="month" label="期数" width="100" />
        <el-table-column prop="amount" label="应还金额" width="120">
          <template #default="{ row }">
            <span v-if="row.is_overpayment" style="color: #67c23a">-¥{{ format(row.amount) }} <el-tag size="small" type="success" effect="plain">溢缴款</el-tag></span>
            <span v-else>¥{{ format(row.amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="min_pay" label="最低还款" width="120">
          <template #default="{ row }">
            <span v-if="row.is_overpayment">—</span>
            <span v-else>¥{{ format(row.min_pay) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Bank summary -->
    <el-card shadow="hover" style="margin-top: 16px">
      <template #header>银行汇总</template>
      <el-table :data="data.bank_summary" stripe>
        <el-table-column prop="bank" label="银行" />
        <el-table-column prop="total" label="总应还" width="140">
          <template #default="{ row }">¥{{ format(row.total) }}</template>
        </el-table-column>
        <el-table-column prop="min_total" label="最低还款" width="140">
          <template #default="{ row }">¥{{ format(row.min_total) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import dayjs from 'dayjs'
import { getReport } from '@/api.js'

use([
  CanvasRenderer,
  BarChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
])

const periodType = ref('month')
const monthValue = ref(new Date())
const yearValue = ref(dayjs().year())
const quarterYear = ref(dayjs().year())
const quarterNum = ref(Math.ceil((dayjs().month() + 1) / 3))

const years = ref([dayjs().year() - 1, dayjs().year(), dayjs().year() + 1])
const data = ref({ bank_months: {}, bank_summary: [], total: 0, min_total: 0 })

// Bar chart option
const barOption = computed(() => {
  const summary = data.value.bank_summary || []
  if (!summary.length) return {}
  return {
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const p = params[0]
        return `<b>${p.name}</b><br/>应还: ¥${format(p.value)}`
      },
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: summary.map(s => s.bank),
      axisLabel: { interval: 0, fontSize: 11 },
    },
    yAxis: { type: 'value', axisLabel: { formatter: v => '¥' + (v >= 10000 ? (v / 10000).toFixed(1) + '万' : v) } },
    series: [{
      type: 'bar',
      data: summary.map(s => s.total),
      itemStyle: {
        color: (params) => {
          const colors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399',
                         '#5470c6', '#fac858', '#ee6666', '#73c0de', '#3ba272',
                         '#fc8452', '#9a60b4', '#ea7ccc']
          return colors[params.dataIndex % colors.length]
        },
      },
      label: { show: true, position: 'top', fontSize: 10, formatter: p => '¥' + format(p.value) },
    }],
  }
})

// Pie chart option
const pieOption = computed(() => {
  const summary = data.value.bank_summary || []
  if (!summary.length) return {}
  return {
    tooltip: {
      trigger: 'item',
      formatter: (p) => `${p.name}<br/>¥${format(p.value)} (${p.percent}%)`,
    },
    legend: { orient: 'vertical', left: 'left', top: 'center' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: true,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      data: summary.map(s => ({ name: s.bank, value: s.total })),
    }],
  }
})

async function loadReport() {
  let type = periodType.value
  let params = { type }

  if (type === 'month') {
    params.value = dayjs(monthValue.value).format('YYYY-MM')
  } else if (type === 'quarter') {
    params.value = String(quarterYear.value)
    params.q = quarterNum.value
  } else if (type === 'year') {
    params.value = String(yearValue.value)
  }

  const res = await getReport(type, params.value, params.q)
  data.value = res.data
}

// watch monthValue to trigger reload when user picks a month from the picker
// (el-date-picker @change doesn't fire for month-type panel selection)
watch(monthValue, () => {
  if (periodType.value === 'month') loadReport()
})

const detailRows = computed(() => {
  const rows = []
  const card_detail = data.value.card_detail || {}
  for (const [key, months] of Object.entries(card_detail)) {
    const parts = key.split('|||')
    const bank = parts[0]
    const holder_name = parts[1] || ''
    const card = parts[2] || '—'
    for (const m of months) {
      rows.push({ bank, holder_name, card, ...m })
    }
  }
  return rows.sort((a, b) => a.bank.localeCompare(b.bank) || a.card.localeCompare(b.card) || a.month.localeCompare(b.month))
})

onMounted(loadReport)

function format(n) {
  if (n == null) return '0.00'
  return Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>
