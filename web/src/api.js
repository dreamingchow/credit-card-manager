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

export function getReport(type, value) {
  const params = { type }
  if (value) params.value = value
  return api.get('/report', { params })
}

export function getHistory(params = {}) {
  return api.get('/history', { params })
}

export function getSuggestions() {
  return api.get('/suggestions')
}

export function markPaid(bank, bill_month) {
  return api.post('/pay', { bank, bill_month })
}
