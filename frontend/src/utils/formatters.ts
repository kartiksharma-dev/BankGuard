/**
 * Currency and Number Formatting Utilities
 * Standardized for Indian Rupee (INR) representation across BankGuard.
 */

export const inrFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * Format a numeric amount into Indian Rupee (INR) currency format.
 * Example: 123456.78 -> ₹1,23,456.78
 */
export function formatCurrencyINR(amount: number | null | undefined): string {
  if (typeof amount !== 'number' || isNaN(amount)) {
    return '₹0.00';
  }
  return inrFormatter.format(amount);
}
