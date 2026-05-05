<template>
  <div>
    <h2 style="margin-bottom: 20px">📜 历史还款记录</h2>

    <!-- Filters -->
    <div style="display: flex; gap: 12px; margin-bottom: 20px; align-items: center">
      <el-select v-model="selectedYear" @change="loadHistory" placeholder="年份" clearable style="width: 120px">
        <el-option v-for="y in yearOptions" :key="y" :label="y" :value="y" />
      </el-select>
      <el-select v-model="selectedMonth" @change="loadHistory" placeholder="月份" clearable style="width: 100px">
        <el-option v-for="m in monthOptions" :key="m" :label="m + '月'" :value="m" />
      </el-select>
      <el-select v-model="selectedBank" @change="loadHistory" placeholder="全部银行" clearable style="width: 200px">
        <el-option v-for="bank in allBanks" :key="bank" :label="bank" :value="bank" />
      </el-select>
    </div>

    <!-- Grand total -->
    <div style="margin-bottom: 20px; padding: 16px; background: #f0fff4; border-radius: 8px; display: flex; align-items: center">
      <span style="font-size: 16px; color: #276749">💰 累计还款总额:</span>
      <span style="font-size: 24px; font-weight: bold; color: #276749; margin-left: 12px">¥{{ format(grandTotal) }}</span>
    </div>

    <!-- Per bank tables -->
    <el-collapse v-model="activeBanks">
      <el-collapse-item v-for="(info, bank) in historyData.by_bank" :key="bank" :name="bank">
        <template #title>
          <span style="font-weight: bold; font-size: 16px">{{ bank }}</span>
          <el-tag size="small" style="margin-left: 12px">{{ info.count }} 笔</el-tag>
          <span style="margin-left: 8px; color: #718096">累计 ¥{{ format(info.total) }}</span>
        </template>

        <el-table :data="info.records" stripe size="small">
          <el-table-column prop="bill_month" label="账单月份" width="120" />
          <el-table-column prop="card_last4" label="卡号末四位" width="120">
            <template #default="{ row }">{{ row.card_last4 ? '****' + row.card_last4 : '—' }}</template>
          </el-table-column>
          <el-table-column prop="amount" label="金额" width="160">
            <template #default="{ row }">
              ¥{{ format(row.amount) }}
              <el-tag v-if="row.amount < 0" size="small" type="warning" effect="plain" style="margin-left: 6px">溢缴款</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="pay_date" label="还款时间">
            <template #default="{ row }">{{ row.pay_date || '—' }}</template>
          </el-table-column>
        </el-table>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { getHistory } from '@/api.js'

const selectedYear = ref('')
const selectedMonth = ref('')
const selectedBank = ref('')
const historyData = ref({ by_bank: {}, grand_total: 0 })
const activeBanks = ref([])

// Available years from data
const availableYears = computed(() => {
  const years = new Set()
  for (const bank in historyData.value.by_bank) {
    for (const r of historyData.value.by_bank[bank].records) {
      if (r.bill_month) years.add(r.bill_month.split('-')[0])
    }
  }
  return [...years].sort().reverse()
})

const yearOptions = computed(() => {
  const all = ['']
  for (let y = new Date().getFullYear(); y >= 2024; y--) all.push(String(y))
  return all
})

const monthOptions = computed(() => {
  const all = ['']
  for (let m = 1; m <= 12; m++) all.push(m)
  return all
})

const allBanks = computed(() => Object.keys(historyData.value.by_bank))
const grandTotal = computed(() => historyData.value.grand_total)

async function loadHistory() {
  const params = {}
  if (selectedBank.value) params.bank = selectedBank.value
  if (selectedYear.value) params.year = selectedYear.value
  if (selectedMonth.value) params.month = selectedMonth.value
  const res = await getHistory(params)
  historyData.value = res.data
  activeBanks.value = Object.keys(res.data.by_bank)
}

onMounted(loadHistory)

function format(n) {
  if (n == null) return '0.00'
  const abs = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return n < 0 ? '-' + abs : abs
}
</script>
