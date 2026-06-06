<template>
  <div>
    <h2>💰 年费管理</h2>

    <!-- 年费列表 -->
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>年费记录</span>
          <el-button type="primary" @click="openAddDialog">+ 新增年费</el-button>
        </div>
      </template>

      <el-table :data="fees" stripe style="width: 100%">
        <el-table-column prop="bank" label="银行" width="120" />
        <el-table-column prop="card_last4" label="卡号末四位" width="120">
          <template #default="{ row }">
            {{ row.card_last4 ? '****' + row.card_last4 : '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="holder_name" label="持卡人" width="100" />
        <el-table-column prop="amount" label="年费金额" width="100">
          <template #default="{ row }">
            ¥{{ row.amount?.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="waive_condition" label="减免条件" min-width="150" />
        <el-table-column label="收费日期" width="100">
          <template #default="{ row }">
            {{ row.charge_month }}月{{ row.charge_day }}日
          </template>
        </el-table-column>
        <el-table-column label="每年" width="60" align="center">
          <template #default="{ row }">
            {{ row.is_recurring ? '🔄' : '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_first_year" label="首年" width="60" align="center">
          <template #default="{ row }">
            {{ row.is_first_year ? '✅' : '❌' }}
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="150" show-overflow-tooltip />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="editFee(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteFee(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑对话框 -->
    <el-dialog
      v-model="showDialog"
      :title="editingFee ? '编辑年费记录' : '新增年费记录'"
      width="500px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="选择卡片">
          <el-select 
            v-model="form.card_id" 
            placeholder="选择卡片" 
            style="width: 100%"
            @change="onCardChange"
          >
            <el-option
              v-for="card in cards"
              :key="card.id"
              :label="`${card.bank} - ****${card.card_last4 || '未知'}`"
              :value="card.id"
            />
            <el-option value="new">➕ 添加新卡</el-option>
          </el-select>
        </el-form-item>

        <!-- 新卡信息（选择"添加新卡"时显示） -->
        <template v-if="form.card_id === 'new'">
          <el-form-item label="银行">
            <el-input v-model="newCard.bank" placeholder="如：招商银行" />
          </el-form-item>
          <el-form-item label="卡号末四位">
            <el-input v-model="newCard.card_last4" placeholder="如：6670" />
          </el-form-item>
          <el-form-item label="持卡人">
            <el-input v-model="newCard.holder_name" placeholder="如：周君明" />
          </el-form-item>
        </template>

        <el-form-item label="年费金额">
          <el-input-number v-model="form.amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="减免条件">
          <el-input v-model="form.waive_condition" placeholder="如：年刷6次免" />
        </el-form-item>
        <el-form-item label="收费日期">
          <div style="display: flex; gap: 10px; align-items: center">
            <el-select v-model="form.charge_month" placeholder="月" style="width: 100px">
              <el-option
                v-for="m in 12"
                :key="m"
                :label="m + '月'"
                :value="m"
              />
            </el-select>
            <span>月</span>
            <el-select v-model="form.charge_day" placeholder="日" style="width: 100px">
              <el-option
                v-for="d in 31"
                :key="d"
                :label="d + '日'"
                :value="d"
              />
            </el-select>
            <span>日</span>
          </div>
        </el-form-item>
        <el-form-item label="每年重复">
          <el-switch v-model="form.is_recurring" active-text="是" inactive-text="否" />
        </el-form-item>
        <el-form-item label="是否首年">
          <el-switch v-model="form.is_first_year" active-text="是" inactive-text="否" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="待收费" value="pending" />
            <el-option label="已减免" value="waived" />
            <el-option label="已收费" value="charged" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="saveFee">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getAnnualFees, createAnnualFee, updateAnnualFee, deleteAnnualFee, getCards } from '../api.js'

const fees = ref([])
const cards = ref([])
const showDialog = ref(false)
const editingFee = ref(null)

const form = ref({
  card_id: null,
  amount: 0,
  waive_condition: '',
  charge_month: null,
  charge_day: null,
  is_first_year: false,
  is_recurring: true,
  status: 'pending',
  notes: '',
})

const newCard = ref({
  bank: '',
  card_last4: '',
  holder_name: '',
})

const getStatusType = (status) => {
  const types = { pending: 'warning', waived: 'success', charged: 'danger' }
  return types[status] || 'info'
}

const getStatusText = (status) => {
  const texts = { pending: '待收费', waived: '已减免', charged: '已收费' }
  return texts[status] || status
}

const loadFees = async () => {
  try {
    const res = await getAnnualFees()
    fees.value = res.data.fees
  } catch (err) {
    console.error('加载年费失败:', err)
  }
}

const loadCards = async () => {
  try {
    const res = await getCards()
    cards.value = res.data.cards
  } catch (err) {
    console.error('加载卡片失败:', err)
  }
}

const openAddDialog = () => {
  editingFee.value = null
  resetForm()
  showDialog.value = true
}

const editFee = (fee) => {
  editingFee.value = fee
  form.value = {
    card_id: fee.card_id,
    amount: fee.amount,
    waive_condition: fee.waive_condition || '',
    charge_month: fee.charge_month,
    charge_day: fee.charge_day,
    is_first_year: fee.is_first_year,
    is_recurring: fee.is_recurring,
    status: fee.status,
    notes: fee.notes || '',
  }
  newCard.value = { bank: '', card_last4: '', holder_name: '' }
  showDialog.value = true
}

const onCardChange = () => {
  if (form.value.card_id !== 'new') {
    newCard.value = { bank: '', card_last4: '', holder_name: '' }
  }
}

const saveFee = async () => {
  try {
    // 校验：必须选月日
    if (!form.value.charge_month || !form.value.charge_day) {
      alert('请选择收费日期（月 + 日）')
      return
    }
    // 校验：金额必须 > 0
    if (!form.value.amount || form.value.amount <= 0) {
      alert('请输入年费金额')
      return
    }

    const data = {
      ...form.value,
    }

    // 如果是新卡
    if (form.value.card_id === 'new') {
      if (!newCard.value.bank) {
        alert('请输入银行名称')
        return
      }
      data.new_card = {
        bank: newCard.value.bank,
        card_last4: newCard.value.card_last4 || null,
        holder_name: newCard.value.holder_name || null,
      }
      data.card_id = null // 新卡时 card_id 必须为 null
    }

    if (editingFee.value) {
      await updateAnnualFee(editingFee.value.id, data)
    } else {
      await createAnnualFee(data)
    }
    showDialog.value = false
    editingFee.value = null
    resetForm()
    await loadFees()
    await loadCards() // 重新加载卡片列表
  } catch (err) {
    console.error('保存年费失败:', err)
    alert('保存失败: ' + (err.response?.data?.error || err.message))
  }
}

const deleteFee = async (id) => {
  if (!confirm('确定要删除这条年费记录吗？')) return
  try {
    await deleteAnnualFee(id)
    await loadFees()
  } catch (err) {
    console.error('删除年费失败:', err)
    alert('删除失败: ' + (err.response?.data?.error || err.message))
  }
}

const resetForm = () => {
  form.value = {
    card_id: null,
    amount: 0,
    waive_condition: '',
    charge_month: null,
    charge_day: null,
    is_first_year: false,
    is_recurring: true,
    status: 'pending',
    notes: '',
  }
  newCard.value = { bank: '', card_last4: '', holder_name: '' }
}

onMounted(async () => {
  await Promise.all([loadFees(), loadCards()])
})
</script>

<style scoped>
h2 {
  margin-top: 0;
  color: #1d2b55;
}
</style>
