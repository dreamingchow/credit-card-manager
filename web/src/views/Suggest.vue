<template>
  <div>
    <h2 style="margin-bottom: 20px">💡 还款计划建议</h2>

    <!-- Overall health -->
    <el-row :gutter="16" style="margin-bottom: 20px">
      <el-col :span="8">
        <el-card shadow="hover">
          <div style="text-align: center">
            <div style="font-size: 24px; font-weight: bold; color: #3182ce">¥{{ format(suggestions.overall_avg) }}</div>
            <div style="color: #718096; margin-top: 4px">月均消费</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div style="text-align: center">
            <div style="font-size: 24px; font-weight: bold; color: #e53e3e">¥{{ format(suggestions.unpaid_total) }}</div>
            <div style="color: #718096; margin-top: 4px">待还总额</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <div style="text-align: center">
            <div style="font-size: 24px; font-weight: bold; color: #3182ce">¥{{ format(monthlyCashFlow) }}</div>
            <div style="color: #718096; margin-top: 4px">建议每月预留</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Bank suggestions -->
    <el-card shadow="hover">
      <template #header>各卡建议</template>

      <div v-for="bank in suggestions.banks" :key="bank.bank" style="margin-bottom: 16px; padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px">
        <div style="font-weight: bold; font-size: 15px; margin-bottom: 8px">
          {{ bank.bank }}
          <el-tag v-if="bank.has_unpaid" type="danger" size="small" style="margin-left: 8px">⏳ 有待还</el-tag>
          <el-tag v-else type="success" size="small" style="margin-left: 8px">✅ 无待还</el-tag>
        </div>

        <div style="display: flex; gap: 24px; color: #718096; font-size: 13px; margin-bottom: 8px">
          <span>月均消费: ¥{{ format(bank.avg_monthly) }}</span>
          <span>还款次数: {{ bank.paid_count }}</span>
          <span>累计已还: ¥{{ format(bank.total_paid) }}</span>
        </div>

        <!-- Unpaid bills -->
        <div v-if="bank.has_unpaid" style="margin-top: 8px">
          <el-table :data="bank.unpaid" stripe size="small">
            <el-table-column prop="month" label="账单月份" width="100" />
            <el-table-column prop="amount" label="金额" width="120">
              <template #default="{ row }">¥{{ format(row.amount) }}</template>
            </el-table-column>
          </el-table>

          <!-- Suggestion -->
          <div style="margin-top: 8px; padding: 8px 12px; background: #ebf8ff; border-radius: 6px; font-size: 13px; color: #2b6cb0">
            💡 {{ bank.avg_monthly > 1000 ? '建议全额还款（大额账单避免分期手续费）' : '可根据现金流选择最低还款或全额还款' }}
          </div>
        </div>
      </div>
    </el-card>

    <!-- Cash flow ranking -->
    <el-card shadow="hover" style="margin-top: 16px">
      <template #header>📅 现金流规划建议</template>
      <p style="color: #718096; margin-bottom: 12px">按月均消费排序（优先预留大额卡）:</p>
      <el-table :data="rankedBanks" stripe size="small">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="bank" label="银行" />
        <el-table-column prop="avg_monthly" label="月均消费" width="140">
          <template #default="{ row }">¥{{ format(row.avg_monthly) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { getSuggestions } from '@/api.js'

const suggestions = ref({ overall_avg: 0, unpaid_count: 0, unpaid_total: 0, banks: [] })

onMounted(async () => {
  const res = await getSuggestions()
  suggestions.value = res.data
})

const monthlyCashFlow = computed(() => {
  return suggestions.value.banks.reduce((sum, b) => sum + b.avg_monthly, 0)
})

const rankedBanks = computed(() => {
  return [...suggestions.value.banks].sort((a, b) => b.avg_monthly - a.avg_monthly)
})

function format(n) {
  if (n == null) return '0.00'
  return Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>
