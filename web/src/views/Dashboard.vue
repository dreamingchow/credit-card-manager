<template>
  <div>
    <h2 style="margin-bottom: 20px">💳 总负债仪表盘</h2>

    <!-- Top stats cards -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="8">
        <el-card shadow="hover">
          <div style="text-align: center">
            <div style="font-size: 32px; font-weight: bold; color: #e53e3e">{{ dashboard.unpaid_count }}</div>
            <div style="color: #718096; margin-top: 4px">待还笔数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div style="text-align: center">
            <div style="font-size: 32px; font-weight: bold; color: #e53e3e">¥{{ format(dashboard.unpaid_total) }}</div>
            <div style="color: #718096; margin-top: 4px">待还总额</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div style="text-align: center">
            <div style="font-size: 32px; font-weight: bold; color: #3182ce">¥{{ format(overallAvg) }}</div>
            <div style="color: #718096; margin-top: 4px">月均消费</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts row 1: 待还分布 + Top3 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>🚨 待还分布</template>
          <v-chart :option="donutOption" autoresize style="height: 280px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>Top 3 最大待还</template>
          <el-table :data="top3Unpaid" stripe size="small">
            <el-table-column prop="bank" label="银行" />
            <el-table-column prop="card_last4" label="卡号" width="80">
              <template #default="{ row }">
                {{ row.card_last4 ? '****' + row.card_last4 : '—' }}
              </template>
            </el-table-column>
            <el-table-column prop="amount" label="金额" width="120">
              <template #default="{ row }">
                <span v-if="row.amount < 0" style="color: #67c23a">-¥{{ format(row.amount) }} <el-tag size="small" type="success" effect="plain">溢缴款</el-tag></span>
                <span v-else>¥{{ format(row.amount) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="due_date_full" label="到期日" width="120">
              <template #default="{ row }">{{ row.due_date_full || '—' }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts row 2: 消费趋势 + 月均排名 -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>📈 近6月消费趋势</template>
          <v-chart :option="trendOption" autoresize style="height: 280px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>🏦 各银行月均消费</template>
          <v-chart :option="barOption" autoresize style="height: 280px" />
        </el-card>
      </el-col>
    </el-row>

    <!-- Bank stats table -->
    <el-card shadow="hover">
      <template #header>📊 各银行还款统计</template>
      <el-table :data="dashboard.bank_stats" stripe>
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="bank" label="银行" />
        <el-table-column prop="avg_monthly" label="月均消费" width="140">
          <template #default="{ row }">¥{{ format(row.avg_monthly) }}</template>
        </el-table-column>
        <el-table-column prop="paid_count" label="还款次数" width="100" />
        <el-table-column prop="total_paid" label="累计已还" width="140">
          <template #default="{ row }">¥{{ format(row.total_paid) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart, LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
} from 'echarts/components'
import { getDashboard, getSuggestions } from '@/api.js'

use([
  CanvasRenderer,
  BarChart,
  PieChart,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
])

const dashboard = ref({ unpaid_count: 0, unpaid_total: 0, unpaid_cards: [], monthly_trend: [], bank_stats: [] })
const overallAvg = ref(0)

onMounted(async () => {
  const [dashRes, sugRes] = await Promise.all([getDashboard(), getSuggestions()])
  dashboard.value = dashRes.data
  overallAvg.value = sugRes.data.overall_avg
})

const top3Unpaid = computed(() => {
  const cards = dashboard.value.unpaid_cards || []
  return cards.slice().sort((a, b) => b.amount - a.amount).slice(0, 3)
})

const trendData = computed(() => {
  const t = dashboard.value.monthly_trend || []
  return t.slice().reverse()
})

// Donut chart: unpaid distribution by bank
const donutOption = computed(() => {
  const cards = dashboard.value.unpaid_cards || []
  if (!cards.length) return {}
  const byBank = {}
  for (const c of cards) {
    byBank[c.bank] = (byBank[c.bank] || 0) + c.amount
  }
  const data = Object.entries(byBank).map(([name, value]) => ({ name, value }))
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
      data: data,
    }],
  }
})

// Line chart: monthly trend
const trendOption = computed(() => {
  const t = trendData.value
  if (!t.length) return {}
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: t.map(d => d.month), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', axisLabel: { formatter: v => (v >= 10000 ? (v / 10000).toFixed(1) + '万' : v) } },
    series: [{
      type: 'line',
      data: t.map(d => d.total),
      smooth: true,
      areaStyle: { opacity: 0.15 },
      itemStyle: { color: '#e53e3e' },
      markPoint: {
        data: [{ type: 'max', name: '最高' }],
      },
    }],
  }
})

// Bar chart: monthly avg by bank (top 10)
const barOption = computed(() => {
  const stats = dashboard.value.bank_stats || []
  if (!stats.length) return {}
  // Sort by avg_monthly desc, take top 10
  const top = stats.slice().sort((a, b) => b.avg_monthly - a.avg_monthly).slice(0, 10)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: top.map(s => s.bank),
      axisLabel: { interval: 0, fontSize: 11 },
    },
    yAxis: { type: 'value', axisLabel: { formatter: v => (v >= 10000 ? (v / 10000).toFixed(1) + '万' : v) } },
    series: [{
      type: 'bar',
      data: top.map(s => s.avg_monthly),
      itemStyle: {
        color: (params) => {
          const colors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399',
                         '#5470c6', '#fac858', '#ee6666', '#73c0de', '#3ba272']
          return colors[params.dataIndex % colors.length]
        },
      },
      label: { show: true, position: 'top', fontSize: 10, formatter: p => '¥' + format(p.value) },
    }],
  }
})

function format(n) {
  if (n == null) return '0.00'
  return Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>
