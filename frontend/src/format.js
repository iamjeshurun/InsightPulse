export const ASPECT_NAMES = {
  account_access: 'Account access',
  credit_reporting: 'Credit reporting',
  debt_collection: 'Debt collection',
  fees_interest: 'Fees & interest',
  fraud_security: 'Fraud & security',
  loan_servicing: 'Loan servicing',
  other: 'Other',
  payments: 'Payments',
}

export const label = (value) =>
  ASPECT_NAMES[value] || (value || '—').replaceAll('_', ' ').replace(/^\w/, (letter) => letter.toUpperCase())

export const percent = (value, digits = 0) => `${(value * 100).toFixed(digits)}%`

export const decimal = (value, digits = 2) => Number(value).toFixed(digits)

export function longDate(iso) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}
