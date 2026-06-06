import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export function getDashboard() {
  return api.get('/dashboard')
}

export function getCalendar(year, month) {
  const params = {}
  if (year) params.year = year
  if (month) params.month = month
  return api.get('/calendar', { params })
}

export function getReport(type, value, q) {
  const params = { type }
  if (value) params.value = value
  if (q) params.q = q
  return api.get('/report', { params })
}

export function getHistory(params = {}) {
  return api.get('/history', { params })
}

export function getSuggestions() {
  return api.get('/suggestions')
}

export function markPaid(bank, bill_month, bill_id) {
  const data = { bank, bill_month }
  if (bill_id) data.bill_id = bill_id
  return api.post('/pay', data)
}

export function getCards() {
  return api.get('/cards')
}

// ── Annual Fees / 年费管理 ──────────────────────

export function getAnnualFees(card_id = null) {
  const params = {}
  if (card_id) params.card_id = card_id
  return api.get('/annual_fees', { params })
}

export function getUpcomingAnnualFees(days = 30) {
  return api.get('/annual_fees/upcoming', { params: { days } })
}

export function createAnnualFee(data) {
  return api.post('/annual_fees', data)
}

export function updateAnnualFee(id, data) {
  return api.put(`/annual_fees/${id}`, data)
}

export function deleteAnnualFee(id) {
  return api.delete(`/annual_fees/${id}`)
}
