<template>
  <div>
    <h2 style="margin-bottom: 20px">✅ 标记还款</h2>

    <!-- Unpaid bills list -->
    <el-card shadow="hover">
      <template #header>当前未还账单</template>

      <el-table :data="unpaidBills" stripe style="width: 100%">
        <el-table-column prop="bank" label="银行" width="120" />
        <el-table-column prop="card_last4" label="卡号" width="120">
          <template #default="{ row }">{{ row.card_last4 ? '****' + row.card_last4 : '—' }}</template>
        </el-table-column>
        <el-table-column prop="bill_month" label="账单月份" width="120" />
        <el-table-column prop="amount" label="金额" width="140">
          <template #default="{ row }">
            <span v-if="row.amount < 0" style="color: #67c23a">-¥{{ format(row.amount) }} <el-tag size="small" type="success" effect="plain">溢缴款</el-tag></span>
            <span v-else>¥{{ format(row.amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="due_date_full" label="到期日" width="140">
          <template #default="{ row }">{{ row.due_date_full || '—' }}</template>
        </el-table-column>
        <!-- Hidden bill_month for markPaid API -->
        <el-table-column prop="bill_id" width="1" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="confirmPay(row)">标记已还</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="unpaidBills.length === 0" style="text-align: center; padding: 40px; color: #a0aec0">
        🎉 所有账单已还清！
      </div>
    </el-card>

    <!-- Mark paid dialog -->
    <el-dialog v-model="dialogVisible" title="确认还款" width="400px">
      <div v-if="payTarget">
        <p>银行: <strong>{{ payTarget.bank }}</strong></p>
        <p>卡号: {{ payTarget.card_last4 ? '****' + payTarget.card_last4 : '—' }}</p>
        <p>账单月份: <strong>{{ payTarget.bill_month }}</strong></p>
        <p>金额: <strong v-if="payTarget.amount < 0" style="color: #67c23a">-¥{{ format(payTarget.amount) }}（溢缴款）</strong>
          <strong v-else style="color: #e53e3e">¥{{ format(payTarget.amount) }}</strong></p>
      </div>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="doPay" :loading="paying">确认还款</el-button>
      </template>
    </el-dialog>

    <!-- Success message -->
    <el-alert v-if="paySuccess" title="✅ 已标记还款成功" type="success" :closable="false" style="margin-top: 16px" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getDashboard, markPaid } from '@/api.js'

const unpaidBills = ref([])
const dialogVisible = ref(false)
const payTarget = ref(null)
const paying = ref(false)
const paySuccess = ref(false)

onMounted(loadUnpaid)

async function loadUnpaid() {
  const res = await getDashboard()
  unpaidBills.value = res.data.unpaid_cards || []
}

function confirmPay(row) {
  payTarget.value = row
  dialogVisible.value = true
}

async function doPay() {
  if (!payTarget.value) return
  paying.value = true

  try {
    await markPaid(payTarget.value.bank, payTarget.value.bill_month, payTarget.value.bill_id)
    ElMessage.success('标记还款成功')
    paySuccess.value = true
    dialogVisible.value = false
    await loadUnpaid()
    setTimeout(() => { paySuccess.value = false }, 3000)
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '操作失败')
  } finally {
    paying.value = false
  }
}

function format(n) {
  if (n == null) return '0.00'
  return Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
</script>
