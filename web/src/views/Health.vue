<template>
  <div style="padding: 20px">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px">
      <h2 style="margin: 0; color: #333">🩺 健康记录</h2>
      <button class="no-print" @click="handlePrint" style="padding: 8px 20px; border: 2px solid #3498db; border-radius: 6px; background: #fff; color: #3498db; cursor: pointer; font-size: 14px; font-weight: bold; transition: all 0.2s"
        onmouseover="this.style.background='#3498db'; this.style.color='#fff'"
        onmouseout="this.style.background='#fff'; this.style.color='#3498db'">
        🖨️ 打印
      </button>
    </div>

    <!-- 天数选择器 -->
    <div style="margin-bottom: 20px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap">
      <span style="color: #666; font-size: 14px">显示范围：</span>
      <button v-for="opt in rangeOptions" :key="opt.value"
        @click="setRange(opt.value)"
        :style="{ padding: '6px 16px', borderRadius: '20px', border: selectedRange === opt.value ? '2px solid #3498db' : '2px solid #ddd', background: selectedRange === opt.value ? '#3498db' : '#fff', color: selectedRange === opt.value ? '#fff' : '#666', cursor: 'pointer', fontSize: '13px', fontWeight: selectedRange === opt.value ? 'bold' : 'normal', transition: 'all 0.2s' }">
        {{ opt.label }}
      </button>
      <div style="display: flex; align-items: center; gap: 4px; margin-left: 4px">
        <input v-model="customDays" type="number" min="1" max="365" placeholder="自定义"
          @keyup.enter="applyCustomRange"
          style="width: 70px; padding: 5px 8px; border: 2px solid #ddd; border-radius: 20px; font-size: 13px; text-align: center; outline: none"
          onfocus="this.style.borderColor='#3498db'"
          onblur="this.style.borderColor='#ddd'" />
        <span style="color: #999; font-size: 13px">天</span>
      </div>
    </div>

    <!-- 血压图表 -->
    <div v-if="displayData.length > 0" class="screen-chart" style="background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px">
      <h3 style="margin-top: 0; color: #555">📈 血压趋势</h3>
      <div style="position: relative; width: 100%; height: 350px">
        <canvas ref="bpChartRef"></canvas>
      </div>
    </div>

    <!-- 心率图表 -->
    <div v-if="displayData.length > 0" class="screen-chart" style="background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 20px">
      <h3 style="margin-top: 0; color: #555">💓 心率趋势</h3>
      <div style="position: relative; width: 100%; height: 280px">
        <canvas ref="hrChartRef"></canvas>
      </div>
    </div>

    <!-- 血压数据表格 -->
    <div v-if="bpData.length > 0" style="background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1)">
      <h3 style="margin-top: 0; color: #555">血压记录</h3>
      <table style="width: 100%; border-collapse: collapse">
        <thead>
          <tr style="background: #f5f7fa">
            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e0e0e0">日期</th>
            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e0e0e0">时段</th>
            <th style="padding: 12px; text-align: center; border-bottom: 2px solid #e0e0e0">收缩压</th>
            <th style="padding: 12px; text-align: center; border-bottom: 2px solid #e0e0e0">舒张压</th>
            <th style="padding: 12px; text-align: center; border-bottom: 2px solid #e0e0e0">心率</th>
            <th style="padding: 12px; text-align: center; border-bottom: 2px solid #e0e0e0">状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, idx) in bpData" :key="idx" :style="{ background: idx % 2 === 0 ? '#fff' : '#f9f9f9' }">
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0">{{ item.date }}</td>
            <td style="padding: 10px; border-bottom: 1px solid #e0e0e0">{{ item.period }}</td>
            <td style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0">{{ item.systolic }}</td>
            <td style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0">{{ item.diastolic }}</td>
            <td style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0">{{ item.pulse }}</td>
            <td style="padding: 10px; text-align: center; border-bottom: 1px solid #e0e0e0">
              <span :style="{ color: getStatusColor(item.systolic, item.diastolic), fontWeight: 'bold' }">
                {{ getStatusText(item.systolic, item.diastolic) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 统计摘要 -->
      <div v-if="stats.systolic" style="margin-top: 20px; padding: 15px; background: #f0f9ff; border-radius: 8px; border-left: 4px solid #3498db">
        <h4 style="margin-top: 0; color: #2c3e50">📊 统计摘要</h4>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px">
          <div>
            <div style="color: #7f8c8d; font-size: 14px">平均收缩压</div>
            <div style="font-size: 24px; font-weight: bold; color: #e74c3c">{{ stats.systolic.avg }} <span style="font-size: 14px; color: #999">mmHg</span></div>
            <div style="font-size: 12px; color: #999">范围: {{ stats.systolic.min }} - {{ stats.systolic.max }}</div>
          </div>
          <div>
            <div style="color: #7f8c8d; font-size: 14px">平均舒张压</div>
            <div style="font-size: 24px; font-weight: bold; color: #3498db">{{ stats.diastolic.avg }} <span style="font-size: 14px; color: #999">mmHg</span></div>
            <div style="font-size: 12px; color: #999">范围: {{ stats.diastolic.min }} - {{ stats.diastolic.max }}</div>
          </div>
          <div>
            <div style="color: #7f8c8d; font-size: 14px">平均心率</div>
            <div style="font-size: 24px; font-weight: bold; color: #2ecc71">{{ stats.pulse.avg }} <span style="font-size: 14px; color: #999">次/分</span></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 打印专用区域（屏幕隐藏，打印时显示） -->
    <div id="print-area" style="display:none">
      <h1 style="text-align:center; margin: 0 0 20px; font-size: 22px; color: #333">健康记录</h1>
      <div style="margin-bottom: 30px">
        <h2 style="margin: 0 0 10px; font-size: 16px; color: #555">📈 血压趋势</h2>
        <img id="print-bp-img" style="width:100%; height: 320px; object-fit: contain" />
      </div>
      <div>
        <h2 style="margin: 0 0 10px; font-size: 16px; color: #555">💓 心率趋势</h2>
        <img id="print-hr-img" style="width:100%; height: 280px; object-fit: contain" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import Chart from 'chart.js/auto'
import { LinearScale, CategoryScale, LineElement, PointElement, Tooltip, Legend, Filler } from 'chart.js'

// ── 正常区间标注插件 ──
const normalRangePlugin = {
  id: 'normalRange',
  afterDraw(chart) {
    try {
      const { ctx: c, chartArea, scales } = chart
      if (!chartArea || !scales?.y) return
      
      const yScale = scales.y
      const firstLabel = chart.data.datasets?.[0]?.label || ''
      
      if (firstLabel.includes('收缩压') || firstLabel.includes('舒张压')) {
        // 血压图：正常区间底色 + 虚线边界
        const y60 = yScale.getPixelForValue(60)
        const y80 = yScale.getPixelForValue(80)
        const y90 = yScale.getPixelForValue(90)
        const y120 = yScale.getPixelForValue(120)
        
        if (y60 == null || y80 == null || y90 == null || y120 == null) return
        
        c.save()
        
        // 舒张压正常范围底色 (60-80)
        const greenH = Math.max(y60 - y80, 1)
        if (greenH > 0 && chartArea.width > 0) {
          c.fillStyle = 'rgba(46, 204, 113, 0.1)'
          c.fillRect(chartArea.left, y80, chartArea.width, greenH)
        }
        
        // 收缩压正常范围底色 (90-120)
        const blueH = Math.max(y90 - y120, 1)
        if (blueH > 0 && chartArea.width > 0) {
          c.fillStyle = 'rgba(52, 152, 219, 0.06)'
          c.fillRect(chartArea.left, y120, chartArea.width, blueH)
        }
        
        // 舒张压正常范围虚线 (60-80)
        c.strokeStyle = 'rgba(46, 204, 113, 0.5)'
        c.lineWidth = 1
        c.setLineDash([4, 4])
        c.beginPath(); c.moveTo(chartArea.left, y60); c.lineTo(chartArea.right, y60); c.stroke()
        c.beginPath(); c.moveTo(chartArea.left, y80); c.lineTo(chartArea.right, y80); c.stroke()
        
        // 收缩压正常范围虚线 (90-120)
        c.strokeStyle = 'rgba(52, 152, 219, 0.4)'
        c.setLineDash([6, 3])
        c.beginPath(); c.moveTo(chartArea.left, y90); c.lineTo(chartArea.right, y90); c.stroke()
        c.beginPath(); c.moveTo(chartArea.left, y120); c.lineTo(chartArea.right, y120); c.stroke()
        
        // 标注文字
        c.setLineDash([])
        c.font = '10px sans-serif'
        c.fillStyle = 'rgba(46, 204, 113, 0.7)'
        c.fillText('舒张压正常(60-80)', chartArea.left + 5, (y60 + y80) / 2 - 3)
        c.fillStyle = 'rgba(52, 152, 219, 0.7)'
        c.fillText('收缩压正常(90-120)', chartArea.left + 5, (y90 + y120) / 2 - 3)
        
        c.restore()
      } else if (firstLabel.includes('心率')) {
        // 心率图：正常区间底色 + 虚线边界
        const y60 = yScale.getPixelForValue(60)
        const y100 = yScale.getPixelForValue(100)
        
        if (y60 == null || y100 == null) return
        
        c.save()
        
        // 心率正常范围底色 (60-100)
        const greenH = Math.max(y60 - y100, 1)
        if (greenH > 0 && chartArea.width > 0) {
          c.fillStyle = 'rgba(46, 204, 113, 0.1)'
          c.fillRect(chartArea.left, y100, chartArea.width, greenH)
        }
        
        // 虚线边界
        c.strokeStyle = 'rgba(46, 204, 113, 0.5)'
        c.lineWidth = 1
        c.setLineDash([4, 4])
        c.beginPath(); c.moveTo(chartArea.left, y60); c.lineTo(chartArea.right, y60); c.stroke()
        c.beginPath(); c.moveTo(chartArea.left, y100); c.lineTo(chartArea.right, y100); c.stroke()
        
        // 标注文字
        c.setLineDash([])
        c.font = '10px sans-serif'
        c.fillStyle = 'rgba(46, 204, 113, 0.7)'
        c.fillText('心率正常(60-100)', chartArea.left + 5, (y60 + y100) / 2 - 3)
        
        c.restore()
      }
    } catch(e) {
      console.warn('normalRangePlugin error:', e)
    }
  }
}

// ── 数据点标注插件 ──
const dataLabelPlugin = {
  id: 'dataLabels',
  afterDatasetsDraw(chart) {
    try {
      const { ctx: c } = chart
      c.save()
      
      chart.data.datasets.forEach((dataset, i) => {
        const meta = chart.getDatasetMeta(i)
        if (!meta.hidden && meta.data) {
          const color = i === 0 ? '#E74C3C' : (i === 1 ? '#3498DB' : '#2ECC71')
          meta.data.forEach((point, idx) => {
            const val = dataset.data[idx]
            if (val == null || !point) return
            c.font = 'bold 10px sans-serif'
            c.textAlign = 'center'
            c.fillStyle = color
            c.fillText(val, point.x, point.y - 10)
          })
        }
      })
      
      c.restore()
    } catch(e) {
      console.warn('dataLabelPlugin error:', e)
    }
  }
}

Chart.register(LinearScale, CategoryScale, LineElement, PointElement, Tooltip, Legend, Filler, normalRangePlugin, dataLabelPlugin)

const bpData = ref([])
const selectedRange = ref(7) // 默认最近7天
const customDays = ref('') // 自定义天数输入
const bpChartRef = ref(null)
const hrChartRef = ref(null)
let bpChartInstance = null
let hrChartInstance = null

const rangeOptions = [
  { label: '最近3天', value: 3 },
  { label: '最近7天', value: 7 },
  { label: '最近15天', value: 15 },
  { label: '最近30天', value: 30 },
  { label: '全部', value: 0 }
]

// 当前显示的数据（根据范围过滤）
const displayData = ref([])

// 获取血压数据
async function fetchBloodPressure() {
  try {
    const res = await fetch('/api/health/blood-pressure')
    const json = await res.json()
    // API returns array directly, not {data: [...]}
    bpData.value = Array.isArray(json) ? json : (json.data || [])
    updateCharts()
  } catch (e) {
    console.error('获取血压数据失败:', e)
  }
}

// 设置范围
function setRange(days) {
  selectedRange.value = days
  customDays.value = '' // 清除自定义输入
  updateCharts()
}

// 应用自定义天数
function applyCustomRange() {
  const days = parseInt(customDays.value)
  if (days > 0 && days <= 365) {
    selectedRange.value = days
    updateCharts()
  }
}

// 过滤数据
function getFilteredData() {
  if (selectedRange.value === 0) return bpData.value
  const cutoff = new Date()
  cutoff.setDate(cutoff.getDate() - selectedRange.value)
  return bpData.value.filter(d => new Date(d.date) >= cutoff)
}

// 更新图表
function updateCharts() {
  displayData.value = getFilteredData()
  nextTick(() => {
    setTimeout(() => {
      drawBpChart()
      drawHrChart()
    }, 150)
  })
}

// ── 绘制血压图表 ──
function drawBpChart() {
  if (!bpChartRef.value || displayData.value.length === 0) return
  
  if (bpChartInstance) bpChartInstance.destroy()

  const labels = displayData.value.map(d => `${d.date} ${d.period}`)
  const systolic = displayData.value.map(d => d.systolic)
  const diastolic = displayData.value.map(d => d.diastolic)

  const ctx = bpChartRef.value.getContext('2d')
  
  bpChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: '收缩压 (高压)',
          data: systolic,
          borderColor: '#E74C3C',
          backgroundColor: 'rgba(231, 76, 60, 0.08)',
          borderWidth: 2.5,
          pointRadius: 6,
          pointBackgroundColor: '#E74C3C',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          tension: 0.3,
          fill: false,
        },
        {
          label: '舒张压 (低压)',
          data: diastolic,
          borderColor: '#3498DB',
          backgroundColor: 'rgba(52, 152, 219, 0.08)',
          borderWidth: 2.5,
          pointRadius: 6,
          pointBackgroundColor: '#3498DB',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          tension: 0.3,
          fill: false,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { usePointStyle: true, padding: 20 } },
        tooltip: {
          backgroundColor: 'rgba(0,0,0,0.8)',
          padding: 12,
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y} mmHg`
          }
        },
        // 正常区间标注插件

      },
      scales: {
        y: {
          min: 40,
          max: 160,
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: '#666', stepSize: 20 }
        },
        x: {
          grid: { display: false },
          ticks: { color: '#666', maxRotation: 45 }
        }
      }
    }
  })
}

// ── 绘制心率图表 ──
function drawHrChart() {
  if (!hrChartRef.value || displayData.value.length === 0) return
  
  if (hrChartInstance) hrChartInstance.destroy()

  const labels = displayData.value.map(d => `${d.date} ${d.period}`)
  const pulse = displayData.value.map(d => d.pulse > 0 ? d.pulse : null)

  const ctx = hrChartRef.value.getContext('2d')
  
  hrChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: '心率',
        data: pulse,
        borderColor: '#2ECC71',
        backgroundColor: 'rgba(46, 204, 113, 0.1)',
        borderWidth: 2.5,
        pointRadius: 6,
        pointBackgroundColor: '#2ECC71',
        pointBorderColor: '#fff',
        pointBorderWidth: 2,
        tension: 0.3,
        fill: false,
        spanGaps: false, // 空值不连线
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'top', labels: { usePointStyle: true, padding: 20 } },
        tooltip: {
          backgroundColor: 'rgba(0,0,0,0.8)',
          padding: 12,
          callbacks: {
            label: (ctx) => ctx.parsed.y !== null ? `心率: ${ctx.parsed.y} 次/分` : null
          }
        },

      },
      scales: {
        y: {
          min: 40,
          max: 120,
          grid: { color: 'rgba(0,0,0,0.06)' },
          ticks: { color: '#666', stepSize: 20 }
        },
        x: {
          grid: { display: false },
          ticks: { color: '#666', maxRotation: 45 }
        }
      }
    }
  })
}

// 计算统计
function calcStats(data) {
  if (data.length === 0) return {}
  
  const s = data.map(d => d.systolic)
  const di = data.map(d => d.diastolic)
  const p = data.filter(d => d.pulse > 0).map(d => d.pulse)
  
  const avg = arr => Math.round(arr.reduce((a, b) => a + b, 0) / arr.length * 10) / 10
  const min = arr => Math.min(...arr)
  const max = arr => Math.max(...arr)
  
  return {
    systolic: { avg: avg(s), min: min(s), max: max(s) },
    diastolic: { avg: avg(di), min: min(di), max: max(di) },
    pulse: p.length > 0 ? { avg: avg(p) } : {}
  }
}

const stats = ref(calcStats(bpData.value))

// 状态颜色
function getStatusColor(s, di) {
  if (s < 90 || di < 60) return '#3498db'
  if (s <= 120 && di <= 80) return '#2ecc71'
  if (s <= 140 && di <= 90) return '#f39c12'
  return '#e74c3c'
}

function getStatusText(s, di) {
  if (s < 90 || di < 60) return '偏低'
  if (s <= 120 && di <= 80) return '✅ 理想'
  if (s <= 140 && di <= 90) return '⚠️ 偏高'
  return '🔴 高'
}

// 数据变化时更新图表
watch([bpData, selectedRange], () => {
  stats.value = calcStats(bpData.value)
  updateCharts()
})

onMounted(() => {
  fetchBloodPressure()
})

// 打印：把图表转成图片放入打印区域
function handlePrint() {
  const printArea = document.getElementById('print-area')
  if (!printArea) return

  // 把屏幕图表隐藏，打印区域显示
  document.querySelectorAll('.screen-chart').forEach(el => el.style.display = 'none')
  printArea.style.display = 'block'

  // 把 canvas 转成图片
  if (bpChartInstance) {
    const bpImg = document.getElementById('print-bp-img')
    bpImg.src = bpChartInstance.toBase64Image('image/png', 1)
  }
  if (hrChartInstance) {
    const hrImg = document.getElementById('print-hr-img')
    hrImg.src = hrChartInstance.toBase64Image('image/png', 1)
  }

  // 等图片加载完再打印
  setTimeout(() => {
    window.print()
    // 打印后恢复屏幕显示
    setTimeout(() => {
      printArea.style.display = 'none'
      document.querySelectorAll('.screen-chart').forEach(el => el.style.display = '')
    }, 500)
  }, 300)
}
</script>
