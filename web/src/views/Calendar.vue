<template>
  <div>
    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px">
      <h2 style="margin: 0">📅 还款日历</h2>
      <el-date-picker
        v-model="currentDate"
        type="month"
        placeholder="选择月份"
        @change="loadCalendar"
        style="width: 200px"
      />
    </div>

    <!-- Calendar grid -->
    <el-card shadow="hover">
      <el-table :data="calendarEntries" stripe style="width: 100%">
        <el-table-column prop="due_date" label="日期" width="140" fixed>
          <template #default="{ row }">
            <span :style="{ fontWeight: row.is_today ? 'bold' : 'normal', color: row.is_today ? '#e53e3e' : '' }">
              {{ row.due_date }}
              <span v-if="row.is_today" style="color: #e53e3e"> 🔴今天</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="bank" label="银行" width="100" />
        <el-table-column prop="holder_name" label="持卡人" width="80">
          <template #default="{ row }">{{ row.holder_name || '—' }}</template>
        </el-table-column>
        <el-table-column prop="card_last4" label="卡号" width="100">
          <template #default="{ row }">{{ row.card_last4 ? '****' + row.card_last4 : '—' }}</template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="140" sortable>
          <template #default="{ row }">¥{{ format(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="days_until" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_overdue ? 'danger' : row.days_until === 0 ? 'danger' : row.days_until <= 3 ? 'warning' : 'success'" size="small">
              <span v-if="row.is_overdue">逾期 {{ Math.abs(row.days_until) }}天</span>
              <span v-else-if="row.days_until === 0">今天</span>
              <span v-else>{{ row.days_until }}天后</span>
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <!-- Summary -->
      <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid #eee; display: flex; justify-content: space-between">
        <span style="color: #718096">共 {{ calendarEntries.length }} 笔待还</span>
        <span style="font-weight: bold; color: #e53e3e">💰 总额: ¥{{ format(totalAmount) }}</span>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import dayjs from 'dayjs'
import { getCalendar } from '@/api.js'

const currentDate = ref(new Date())
const calendarEntries = ref([])

async function loadCalendar() {
  const d = dayjs(currentDate.value)
  const res = await getCalendar(d.year(), d.month() + 1)
  calendarEntries.value = res.data.entries
}

const totalAmount = computed(() => {
  return calendarEntries.value.reduce((sum, e) => sum + (e.amount > 0 ? e.amount : 0), 0)
})

onMounted(loadCalendar)

function format(n) {
  if (n == null) return '0.00'
  return Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>
