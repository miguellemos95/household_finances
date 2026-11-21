const MONTH_PATTERN = /^[1-9]\d{3}-(0[1-9]|1[0-2])$/;

function pad(value: number): string {
  return String(value).padStart(2, '0');
}

function firstDay(month: string): Date {
  const [year, monthNumber] = month.split('-').map(Number);
  return new Date(year, monthNumber - 1, 1);
}

export function isMonth(value: string): boolean {
  return MONTH_PATTERN.test(value);
}

export function toMonth(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}`;
}

export function toIsoDate(date: Date): string {
  return `${toMonth(date)}-${pad(date.getDate())}`;
}

export function shiftMonth(month: string, offset: number): string {
  const date = firstDay(month);
  date.setMonth(date.getMonth() + offset);
  return toMonth(date);
}

export function formatMonth(month: string): string {
  return new Intl.DateTimeFormat('en', { month: 'long', year: 'numeric' }).format(firstDay(month));
}
