import { ValidatorFn } from '@angular/forms';

const AMOUNT_PATTERN = /^\d{1,10}(\.\d{1,2})?$/;

export const AMOUNT_HINT =
  'Enter an amount greater than 0 with up to 2 decimals, for example 12.50.';

// Amounts stay as text end to end so no binary floating point touches a money value.
export function parseAmount(value: string): string | null {
  const amount = value.trim();
  return AMOUNT_PATTERN.test(amount) && /[1-9]/.test(amount) ? amount : null;
}

export const amountValidator: ValidatorFn = (control) =>
  parseAmount(String(control.value ?? '')) === null ? { amount: true } : null;
